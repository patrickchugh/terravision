"""Exported graphs list each node in its innermost container only (#232).

A resource with a vpc_id in a subnet is linked from both its subnet and its
VPC. The Graph Format says a node sits in one container, so the export
drops the VPC's listing and keeps the subnet's.
"""

from modules import graphmaker


def _tfdata(graphdict):
    return {"graphdict": graphdict, "provider_detection": {"primary_provider": "aws"}}


def test_outer_listing_is_dropped():
    graph = {
        "aws_vpc.main": ["aws_subnet.a", "aws_instance.web", "aws_internet_gateway.gw"],
        "aws_subnet.a": ["aws_instance.web"],
        "aws_instance.web": ["aws_s3_bucket.logs"],
        "aws_internet_gateway.gw": [],
        "aws_s3_bucket.logs": [],
    }
    tfdata = _tfdata(graph)
    exported = graphmaker.innermost_listings(tfdata)
    assert exported["aws_vpc.main"] == ["aws_subnet.a", "aws_internet_gateway.gw"]
    assert exported["aws_subnet.a"] == ["aws_instance.web"]
    assert exported["aws_instance.web"] == ["aws_s3_bucket.logs"]
    # the graph used for drawing is left as it was
    assert "aws_instance.web" in tfdata["graphdict"]["aws_vpc.main"]


def test_nesting_through_several_boxes():
    graph = {
        "aws_vpc.main": ["tv_aws_az.a", "aws_lb.app"],
        "tv_aws_az.a": ["aws_subnet.a"],
        "aws_subnet.a": ["aws_lb.app"],
        "aws_lb.app": [],
    }
    exported = graphmaker.innermost_listings(_tfdata(graph))
    assert exported["aws_vpc.main"] == ["tv_aws_az.a"]
    assert exported["aws_subnet.a"] == ["aws_lb.app"]


def test_sibling_boxes_are_left_alone():
    """Two subnets that are not nested: not this rule's business."""
    graph = {
        "aws_subnet.a": ["aws_instance.web"],
        "aws_subnet.b": ["aws_instance.web"],
        "aws_instance.web": [],
    }
    exported = graphmaker.innermost_listings(_tfdata(graph))
    assert exported == graph
