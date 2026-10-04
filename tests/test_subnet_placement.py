"""Placement of resources whose subnets are only known at apply time.

TerraVision plans against empty local state, so no subnet has an id yet. Two
handlers used to lose their way because of that:

* ``expand_autoscaling_groups_to_subnets`` matched subnets by id and treated an
  unknown id as a wildcard, so an autoscaling group set to
  ``aws_subnet.private[*].id`` was copied into the public and data subnets too.
  It now expands into the subnets the expression names, and falls back to id
  matching only when no subnet resource is named.
* ``move_to_vpc_parent`` (used for DB subnet groups and Lambda functions) runs
  before availability zone boxes are inserted, so it looked for an AZ between
  subnet and VPC, found none, and left the resource unlinked from both. RDS
  instances were drawn outside the VPC. It now accepts a VPC that is the
  subnet's direct parent.
"""

import pytest

from modules import resource_handlers_aws as aws
from modules import resource_transformers as transformers


def _tfdata(graphdict, meta_data):
    return {
        "graphdict": graphdict,
        "meta_data": meta_data,
        "original_metadata": {},
        "node_list": list(graphdict),
        "hidden": [],
    }


SUBNETS = [
    "aws_subnet.public[0]~1",
    "aws_subnet.public[1]~2",
    "aws_subnet.private[0]~1",
    "aws_subnet.private[1]~2",
    "aws_subnet.data[0]~1",
    "aws_subnet.data[1]~2",
]


@pytest.mark.parametrize(
    "expression",
    [
        pytest.param("${aws_subnet.private[*].id}", id="count-splat"),
        pytest.param("${[for s in aws_subnet.private : s.id]}", id="for-expression"),
        pytest.param(
            ["${aws_subnet.private[0].id}", "${aws_subnet.private[1].id}"],
            id="explicit-list",
        ),
    ],
)
def test_autoscaling_group_expands_only_into_named_subnets(expression):
    graphdict = {s: ["aws_autoscaling_group.app"] for s in SUBNETS}
    graphdict["aws_autoscaling_group.app"] = ["aws_launch_template.app"]
    graphdict["aws_launch_template.app"] = []
    meta_data = {s: {"id": True} for s in SUBNETS}  # "known after apply"
    meta_data["aws_autoscaling_group.app"] = {"vpc_zone_identifier": expression}
    meta_data["aws_launch_template.app"] = {}

    result = aws.expand_autoscaling_groups_to_subnets(_tfdata(graphdict, meta_data))

    placed = {
        s: [c for c in children if "aws_autoscaling_group" in c]
        for s, children in result["graphdict"].items()
        if s.startswith("aws_subnet")
    }
    assert placed["aws_subnet.private[0]~1"] == ["aws_autoscaling_group.app~1"]
    assert placed["aws_subnet.private[1]~2"] == ["aws_autoscaling_group.app~2"]
    for subnet in SUBNETS:
        if "private" not in subnet:
            assert placed[subnet] == [], f"{subnet} should hold no autoscaling group"
    assert (
        "aws_launch_template.app~1"
        in result["graphdict"]["aws_autoscaling_group.app~1"]
    )


def test_autoscaling_group_falls_back_to_id_matching_when_no_subnet_is_named():
    """A data source or a resolved id list names no subnet resource: keep the
    old behaviour rather than expanding into nothing."""
    graphdict = {s: ["aws_autoscaling_group.app"] for s in SUBNETS}
    graphdict["aws_autoscaling_group.app"] = []
    meta_data = {s: {"id": True} for s in SUBNETS}
    meta_data["aws_autoscaling_group.app"] = {
        "vpc_zone_identifier": "${data.aws_subnets.private.ids}"
    }

    result = aws.expand_autoscaling_groups_to_subnets(_tfdata(graphdict, meta_data))

    expanded = [
        n for n in result["graphdict"] if n.startswith("aws_autoscaling_group.app~")
    ]
    assert len(expanded) == len(SUBNETS)


def test_subnets_named_by_matches_module_prefixed_nodes():
    subnets = [
        "module.vpc.aws_subnet.private[0]~1",
        "module.vpc.aws_subnet.public[0]~1",
    ]
    assert aws._subnets_named_by(
        subnets, ["${module.vpc.aws_subnet.private[*].id}"]
    ) == ["module.vpc.aws_subnet.private[0]~1"]
    assert aws._subnets_named_by(subnets, ["subnet-0123456789"]) == []


@pytest.mark.parametrize(
    "with_az", [False, True], ids=["subnet-under-vpc", "subnet-under-az"]
)
def test_move_to_vpc_parent_finds_vpc_with_or_without_az(with_az):
    if with_az:
        graphdict = {
            "aws_vpc.main": ["aws_az.availability_zone_eu_west_1a~1"],
            "aws_az.availability_zone_eu_west_1a~1": ["aws_subnet.data[0]~1"],
        }
    else:
        graphdict = {"aws_vpc.main": ["aws_subnet.data[0]~1"]}
    graphdict.update(
        {
            "aws_subnet.data[0]~1": ["aws_db_subnet_group.main"],
            "aws_db_subnet_group.main": ["aws_db_instance.primary"],
            "aws_db_instance.primary": [],
        }
    )

    result = transformers.move_to_vpc_parent(
        _tfdata(graphdict, {}), resource_pattern="aws_db_subnet_group"
    )

    assert "aws_db_subnet_group.main" in result["graphdict"]["aws_vpc.main"]
    assert "aws_db_subnet_group.main" not in result["graphdict"]["aws_subnet.data[0]~1"]
