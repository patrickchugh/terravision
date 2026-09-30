"""Each VPC gets its own availability zone boxes.

The zone box's name says only which zone it is (us-east-1a), so two VPCs with
subnets in the same zone shared one box, listed in both VPCs: one VPC was
drawn around the other's subnets, or squashed to a sliver. With
one_per_parent, each VPC gets its own numbered copy of the box.
"""

from modules.resource_transformers import insert_intermediate_node


def _zone(subnet, metadata):
    return f"aws_az.availability_zone_{metadata['az']}~1"


def _tfdata(subnets_by_vpc):
    graphdict, meta_data = {}, {}
    for vpc, subnets in subnets_by_vpc.items():
        graphdict[vpc] = [name for name, _ in subnets]
        for name, az in subnets:
            graphdict[name] = []
            meta_data[name] = {"az": az}
    return {"graphdict": graphdict, "meta_data": meta_data}


def _insert(tfdata, one_per_parent):
    return insert_intermediate_node(
        tfdata,
        "aws_vpc",
        "aws_subnet",
        _zone,
        create_if_missing=True,
        one_per_parent=one_per_parent,
    )["graphdict"]


TWO_VPCS = {
    "aws_vpc.prod": [("aws_subnet.prod_a", "1a"), ("aws_subnet.prod_b", "1b")],
    "aws_vpc.dev": [("aws_subnet.dev_a", "1a"), ("aws_subnet.dev_a2", "1a")],
}


def test_each_vpc_gets_its_own_zone_boxes():
    graph = _insert(_tfdata(TWO_VPCS), one_per_parent=True)
    prod_zones = graph["aws_vpc.prod"]
    dev_zones = graph["aws_vpc.dev"]
    assert not set(prod_zones) & set(dev_zones)
    # the dev VPC's two subnets in 1a share the dev VPC's 1a box
    [dev_1a] = dev_zones
    assert sorted(graph[dev_1a]) == ["aws_subnet.dev_a", "aws_subnet.dev_a2"]
    # the copy is labelled like the original: same name before the ~
    [prod_1a] = [z for z in prod_zones if "1a" in z]
    assert dev_1a.split("~")[0] == prod_1a.split("~")[0]
    assert dev_1a != prod_1a


def test_every_zone_box_sits_in_one_vpc():
    graph = _insert(_tfdata(TWO_VPCS), one_per_parent=True)
    zones = [n for n in graph if n.startswith("aws_az.")]
    for zone in zones:
        owners = [v for v in ("aws_vpc.prod", "aws_vpc.dev") if zone in graph[v]]
        assert len(owners) == 1, zone


def test_without_one_per_parent_the_zone_box_is_shared():
    """The old behaviour, still used where a provider has not opted in."""
    graph = _insert(_tfdata(TWO_VPCS), one_per_parent=False)
    assert "aws_az.availability_zone_1a~1" in graph["aws_vpc.prod"]
    assert "aws_az.availability_zone_1a~1" in graph["aws_vpc.dev"]


def test_aws_subnets_opt_in():
    from modules.config.resource_handler_configs_aws import RESOURCE_HANDLER_CONFIGS

    [insert] = [
        t
        for t in RESOURCE_HANDLER_CONFIGS["aws_subnet"]["transformations"]
        if t["operation"] == "insert_intermediate_node"
    ]
    assert insert["params"]["one_per_parent"] is True


def test_gcp_region_and_zone_boxes_opt_in():
    """GCP's zone box sat in two subnetworks at once, so one subnetwork's VM
    was drawn inside the other's (expected-gcp-us8-vpc.json)."""
    from modules.config.resource_handler_configs_gcp import RESOURCE_HANDLER_CONFIGS

    inserts = [
        t
        for config in RESOURCE_HANDLER_CONFIGS.values()
        for t in config.get("transformations", [])
        if t["operation"] == "insert_intermediate_node"
    ]
    assert inserts
    assert all(t["params"].get("one_per_parent") is True for t in inserts)


def test_a_numbered_copy_is_labelled_like_the_original():
    from modules.helpers import pretty_name

    for original in (
        "tv_gcp_zone.us_central1_a",
        "tv_gcp_region.us_central1",
        "aws_az.availability_zone_us_east_1a~1",
    ):
        copy = original.split("~")[0] + "~2"
        assert pretty_name(copy, is_group=True) == pretty_name(original, is_group=True)
