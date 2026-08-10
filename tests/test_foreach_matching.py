"""Cross-provider regression tests for `for_each` instance matching.

Terraform expands `count` into positionally numbered nodes (``aws_subnet.this[0]~1``)
but expands `for_each` into string-keyed nodes (``aws_subnet.this["web"]``).
Relationship detection matched on the *base* address, so a reference like
``${aws_vpc.this[each.key].id}`` matched every instance of ``aws_vpc.this`` at
once. Every VPC then claimed every subnet, each subnet ended up with several
candidate parent groups, and the renderer could not nest anything - the symptom
being a diagram of unconnected icons.

These fixtures are deliberately minimal and cover all three providers, because
the matching logic is provider-neutral and the bug was originally reported
against Azure only. `count` behaviour is asserted here too, so a future change
to key matching cannot silently regress positional matching.
"""

import copy

import pytest

from modules import graphmaker

# ---------------------------------------------------------------------------
# Fixtures: one parent resource with two for_each instances, one child resource
# with two for_each instances, each child belonging to exactly one parent.
# ---------------------------------------------------------------------------

AWS_CASE = {
    "provider": "aws",
    "parents": ['aws_vpc.this["prod"]', 'aws_vpc.this["dev"]'],
    "children": ['aws_subnet.this["prod-web"]', 'aws_subnet.this["dev-web"]'],
    # meta_data holds the HCL reference (what merge_metadata leaves behind)
    "child_reference": {"vpc_id": "${aws_vpc.this[each.value.vpc].id}"},
    # original_metadata holds the plan-resolved values
    "resolved": {
        'aws_vpc.this["prod"]': {"id": "vpc-0prod", "cidr_block": "10.0.0.0/16"},
        'aws_vpc.this["dev"]': {"id": "vpc-0dev", "cidr_block": "10.1.0.0/16"},
        'aws_subnet.this["prod-web"]': {"id": "subnet-0a", "vpc_id": "vpc-0prod"},
        'aws_subnet.this["dev-web"]': {"id": "subnet-0b", "vpc_id": "vpc-0dev"},
    },
    "expected_children": {
        'aws_vpc.this["prod"]': 'aws_subnet.this["prod-web"]',
        'aws_vpc.this["dev"]': 'aws_subnet.this["dev-web"]',
    },
}

AZURE_CASE = {
    "provider": "azure",
    "parents": [
        'azurerm_virtual_network.this["security"]',
        'azurerm_virtual_network.this["apps"]',
    ],
    "children": [
        'azurerm_subnet.this["security.mgmt01"]',
        'azurerm_subnet.this["apps.web"]',
    ],
    "child_reference": {
        "virtual_network_name": "${azurerm_virtual_network.this[each.value.vnet].name}"
    },
    # Azure has no id on a fresh plan, but names are known - this case therefore
    # exercises name matching rather than id matching.
    "resolved": {
        'azurerm_virtual_network.this["security"]': {"name": "VNET.security"},
        'azurerm_virtual_network.this["apps"]': {"name": "VNET.apps"},
        'azurerm_subnet.this["security.mgmt01"]': {
            "name": "SUBNET.security.mgmt01",
            "virtual_network_name": "VNET.security",
        },
        'azurerm_subnet.this["apps.web"]': {
            "name": "SUBNET.apps.web",
            "virtual_network_name": "VNET.apps",
        },
    },
    "expected_children": {
        'azurerm_virtual_network.this["security"]': 'azurerm_subnet.this["security.mgmt01"]',
        'azurerm_virtual_network.this["apps"]': 'azurerm_subnet.this["apps.web"]',
    },
}

GCP_CASE = {
    "provider": "gcp",
    "parents": [
        'google_compute_network.this["prod"]',
        'google_compute_network.this["dev"]',
    ],
    "children": [
        'google_compute_subnetwork.this["prod-web"]',
        'google_compute_subnetwork.this["dev-web"]',
    ],
    "child_reference": {"network": "${google_compute_network.this[each.value.net].id}"},
    "resolved": {
        'google_compute_network.this["prod"]': {
            "name": "net-prod",
            "id": "projects/p/global/networks/net-prod",
        },
        'google_compute_network.this["dev"]': {
            "name": "net-dev",
            "id": "projects/p/global/networks/net-dev",
        },
        'google_compute_subnetwork.this["prod-web"]': {
            "name": "sub-prod-web",
            "network": "projects/p/global/networks/net-prod",
        },
        'google_compute_subnetwork.this["dev-web"]': {
            "name": "sub-dev-web",
            "network": "projects/p/global/networks/net-dev",
        },
    },
    "expected_children": {
        'google_compute_network.this["prod"]': 'google_compute_subnetwork.this["prod-web"]',
        'google_compute_network.this["dev"]': 'google_compute_subnetwork.this["dev-web"]',
    },
}

ALL_CASES = [
    pytest.param(AWS_CASE, id="aws"),
    pytest.param(AZURE_CASE, id="azure"),
    pytest.param(GCP_CASE, id="gcp"),
]


def _build_tfdata(case, resolved=True):
    """Assemble the minimal tfdata that add_relations() needs."""
    nodes = case["parents"] + case["children"]
    meta_data = {}
    for parent in case["parents"]:
        meta_data[parent] = dict(case["resolved"][parent])
    for child in case["children"]:
        # The unresolved HCL reference is what triggers the fan-out
        meta_data[child] = dict(case["child_reference"])

    original_metadata = (
        copy.deepcopy(case["resolved"]) if resolved else {n: {} for n in nodes}
    )

    return {
        "graphdict": {n: [] for n in nodes},
        "node_list": list(nodes),
        "meta_data": meta_data,
        "original_metadata": original_metadata,
        "hidden": [],
        "provider_detection": {
            "primary_provider": case["provider"],
            "providers": [case["provider"]],
        },
    }


@pytest.mark.parametrize("case", ALL_CASES)
def test_foreach_parent_claims_only_its_own_children(case):
    """A for_each parent must connect to its own instance children only."""
    tfdata = graphmaker.add_relations(_build_tfdata(case))
    graphdict = tfdata["graphdict"]

    for parent, own_child in case["expected_children"].items():
        others = [c for c in case["children"] if c != own_child]
        assert (
            own_child in graphdict[parent]
        ), f"{parent} lost its real child {own_child}"
        for foreign in others:
            assert foreign not in graphdict[parent], (
                f"{parent} wrongly claimed {foreign} - this is the fan-out that "
                "stops the renderer nesting anything"
            )


@pytest.mark.parametrize("case", ALL_CASES)
def test_foreach_falls_back_to_instance_key_when_unresolved(case):
    """Greenfield plans have no resolved ids/names - keys must still discriminate.

    Child keys here are hierarchical (``apps.web`` under parent key ``apps``),
    which is a common convention but only a fallback: it ranks below id and
    name matching.
    """
    tfdata = graphmaker.add_relations(_build_tfdata(case, resolved=False))
    graphdict = tfdata["graphdict"]

    for parent, own_child in case["expected_children"].items():
        for foreign in [c for c in case["children"] if c != own_child]:
            assert (
                foreign not in graphdict[parent]
            ), f"{parent} wrongly claimed {foreign} with no resolved metadata"


def test_ambiguous_match_connects_to_nothing():
    """When no signal resolves the instance, link to none rather than all.

    One wrong parent breaks nesting for the whole diagram; one missing edge
    costs a single line.
    """
    nodes = [
        'aws_vpc.this["a"]',
        'aws_vpc.this["b"]',
        'aws_subnet.this["orphan"]',
    ]
    tfdata = {
        "graphdict": {n: [] for n in nodes},
        "node_list": list(nodes),
        "meta_data": {
            'aws_vpc.this["a"]': {},
            'aws_vpc.this["b"]': {},
            'aws_subnet.this["orphan"]': {"vpc_id": "${aws_vpc.this[each.key].id}"},
        },
        "original_metadata": {n: {} for n in nodes},
        "hidden": [],
        "provider_detection": {"primary_provider": "aws", "providers": ["aws"]},
    }

    graphdict = graphmaker.add_relations(tfdata)["graphdict"]

    claimed = [p for p in ('aws_vpc.this["a"]', 'aws_vpc.this["b"]') if graphdict[p]]
    assert not claimed, f"ambiguous reference should link to nothing, got {claimed}"


@pytest.mark.parametrize(
    "attribute, value, expected_links",
    [
        # A splat expands to every instance - it is a value, and one-to-many
        # by definition
        pytest.param("subnet_ids", "${aws_subnet.this[*].id}", 2, id="splat"),
        # depends_on expresses creation ORDER, not architecture. Terraform does
        # wait on all instances, but "build that first" is not "I am attached
        # to it" - honouring it produced fan-outs of 20+ nodes on real infra.
        pytest.param("depends_on", "aws_subnet.this", 0, id="depends_on"),
    ],
)
def test_one_to_many_references(attribute, value, expected_links):
    """Splats keep every instance; depends_on is not an architectural link."""
    nodes = [
        'aws_subnet.this["a"]',
        'aws_subnet.this["b"]',
        "aws_instance.app",
    ]
    tfdata = {
        "graphdict": {n: [] for n in nodes},
        "node_list": list(nodes),
        "meta_data": {
            'aws_subnet.this["a"]': {"id": "subnet-a"},
            'aws_subnet.this["b"]': {"id": "subnet-b"},
            "aws_instance.app": {attribute: [value]},
        },
        "original_metadata": {n: {} for n in nodes},
        "hidden": [],
        "provider_detection": {"primary_provider": "aws", "providers": ["aws"]},
    }

    graphdict = graphmaker.add_relations(tfdata)["graphdict"]

    linked = [n for n in nodes[:2] if "aws_instance.app" in graphdict[n]]
    assert len(linked) == expected_links, f"got {linked}"


def test_count_instances_still_match_positionally():
    """Regression guard: key matching must not disturb `count` behaviour."""
    nodes = [
        "aws_subnet.this[0]~1",
        "aws_subnet.this[1]~2",
        "aws_route_table_association.this[0]~1",
        "aws_route_table_association.this[1]~2",
    ]
    tfdata = {
        "graphdict": {n: [] for n in nodes},
        "node_list": list(nodes),
        "meta_data": {
            "aws_subnet.this[0]~1": {"id": "subnet-0", "cidr_block": "10.0.0.0/24"},
            "aws_subnet.this[1]~2": {"id": "subnet-1", "cidr_block": "10.0.1.0/24"},
            "aws_route_table_association.this[0]~1": {
                "subnet_id": "${aws_subnet.this[count.index].id}"
            },
            "aws_route_table_association.this[1]~2": {
                "subnet_id": "${aws_subnet.this[count.index].id}"
            },
        },
        "original_metadata": {},
        "hidden": [],
        "provider_detection": {"primary_provider": "aws", "providers": ["aws"]},
    }

    graphdict = graphmaker.add_relations(tfdata)["graphdict"]

    assert "aws_route_table_association.this[1]~2" not in graphdict.get(
        "aws_subnet.this[0]~1", []
    )
    assert "aws_route_table_association.this[0]~1" not in graphdict.get(
        "aws_subnet.this[1]~2", []
    )
