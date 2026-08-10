"""Tests for expand_shared_children() across AWS, Azure and GCP.

A node can only be drawn inside one cluster. When several group nodes point at
the same child - three subnets sharing one route table - only the first group
ends up containing it, and the rest are left with no member of their own. An
empty cluster has nothing anchoring it inside its parent, so the layout engine
drops it anywhere on the canvas: subnets float outside their VNET and overlap.

The transformer clones the shared child per parent (child~1, child~2, ...).
These tests are parametrised across all three providers deliberately: the
for_each matching bug survived for months precisely because every fixture
exercised one provider and one expansion style.
"""

import copy

import pytest

from modules.resource_transformers import expand_shared_children


AWS_CASE = {
    "provider": "aws",
    "parent_pattern": "aws_subnet.",
    "child_pattern": "aws_route_table.",
    "parents": ["aws_subnet.web", "aws_subnet.app", "aws_subnet.db"],
    "shared_child": "aws_route_table.private",
    "referrer": "aws_route.default",
}

AZURE_CASE = {
    "provider": "azure",
    "parent_pattern": "azurerm_subnet.",
    "child_pattern": "azurerm_route_table.",
    "parents": [
        'azurerm_subnet.generic["apps.web"]',
        'azurerm_subnet.generic["apps.db"]',
        'azurerm_subnet.generic["apps.mgmt"]',
    ],
    "shared_child": 'azurerm_route_table.generic["apps.rt_apps"]',
    "referrer": "azurerm_route.default_to_firewall",
}

GCP_CASE = {
    "provider": "gcp",
    "parent_pattern": "google_compute_subnetwork.",
    "child_pattern": "google_compute_route.",
    "parents": [
        "google_compute_subnetwork.web",
        "google_compute_subnetwork.app",
        "google_compute_subnetwork.db",
    ],
    "shared_child": "google_compute_route.egress",
    "referrer": "google_compute_router.nat",
}

ALL_CASES = [
    pytest.param(AWS_CASE, id="aws"),
    pytest.param(AZURE_CASE, id="azure"),
    pytest.param(GCP_CASE, id="gcp"),
]


def _tfdata(case, sharing_parents=None):
    """Build a graph where *sharing_parents* all point at the same child."""
    owners = case["parents"] if sharing_parents is None else sharing_parents
    child = case["shared_child"]
    graphdict = {p: ([child] if p in owners else []) for p in case["parents"]}
    graphdict[child] = []
    graphdict[case["referrer"]] = [child]
    return {
        "graphdict": graphdict,
        "meta_data": {child: {"name": "shared", "provider": case["provider"]}},
        "original_metadata": {child: {"name": "shared"}},
    }


def _run(case, tfdata):
    return expand_shared_children(
        tfdata, case["parent_pattern"], case["child_pattern"]
    )["graphdict"]


@pytest.mark.parametrize("case", ALL_CASES)
def test_each_sharing_parent_gets_its_own_copy(case):
    """Every parent ends up with a member, so no cluster is left empty."""
    graphdict = _run(case, _tfdata(case))

    child = case["shared_child"]
    for index, parent in enumerate(sorted(case["parents"]), start=1):
        assert graphdict[parent] == [
            f"{child}~{index}"
        ], f"{parent} should own exactly its own numbered copy of {child}"


@pytest.mark.parametrize("case", ALL_CASES)
def test_original_shared_child_is_not_left_orphaned(case):
    """Nothing may still point at the un-numbered original.

    It would survive as a copy belonging to no group and be drawn loose.
    """
    graphdict = _run(case, _tfdata(case))

    child = case["shared_child"]
    for node, children in graphdict.items():
        assert child not in children, f"{node} still points at the shared original"


@pytest.mark.parametrize("case", ALL_CASES)
def test_other_referrers_are_moved_onto_the_first_copy(case):
    """A route pointing at its route table must follow the clone."""
    graphdict = _run(case, _tfdata(case))

    assert graphdict[case["referrer"]] == [f"{case['shared_child']}~1"]


@pytest.mark.parametrize("case", ALL_CASES)
def test_metadata_is_copied_to_every_clone(case):
    """Clones need their own metadata or they render as unknown nodes."""
    tfdata = expand_shared_children(
        _tfdata(case), case["parent_pattern"], case["child_pattern"]
    )

    for index in range(1, len(case["parents"]) + 1):
        clone = f"{case['shared_child']}~{index}"
        assert tfdata["meta_data"][clone]["name"] == "shared"
        assert tfdata["original_metadata"][clone]["name"] == "shared"


@pytest.mark.parametrize("case", ALL_CASES)
def test_unshared_child_is_left_alone(case):
    """One owner is not sharing, so cloning would be pure noise."""
    only_one = [case["parents"][0]]
    before = copy.deepcopy(_tfdata(case, sharing_parents=only_one))
    graphdict = _run(case, _tfdata(case, sharing_parents=only_one))

    assert graphdict == before["graphdict"]


@pytest.mark.parametrize("case", ALL_CASES)
def test_already_numbered_child_is_left_alone(case):
    """count/for_each instances are numbered upstream; do not renumber them."""
    tfdata = _tfdata(case)
    child = case["shared_child"]
    numbered = f"{child}~1"
    tfdata["graphdict"][numbered] = tfdata["graphdict"].pop(child)
    for parent in case["parents"]:
        tfdata["graphdict"][parent] = [numbered]
    tfdata["graphdict"][case["referrer"]] = [numbered]

    graphdict = _run(case, tfdata)

    assert f"{child}~1~1" not in graphdict
    for parent in case["parents"]:
        assert graphdict[parent] == [numbered]
