"""Groups nest as the graph says, whatever order their types are drawn in.

draw_objects() walks a provider's group types in a fixed order
(AWS_GROUP_NODES) and drew every group it met straight into the cloud box. A
group whose parent type comes later in that order was drawn at the top level,
and the parent then skipped it as already drawn: a VPC listed in
tv_aws_region or aws_account came out beside the box rather than inside it,
leaving the box empty or squashed to a sliver. Graphviz itself nests clusters
to any depth; the limit was in TerraVision's draw loop.
"""

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from modules import drawing
from terravision.terravision import cli

_TD_TEXT = re.compile(r"<TD>([^<]+)</TD>|<FONT[^>]*>([^<]+)</FONT>")


def _draw_dot(graph, tmp_path, monkeypatch) -> str:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "graph.tvg.json"
    source.write_text(json.dumps(graph))
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", str(source), "--format", "dot", "--outfile", "out"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    [dot] = list(tmp_path.glob("out*.dot"))
    return dot.read_text()


def _containers(dot: str):
    """Map each node label to the labels of the boxes around it, outermost first.

    Walks the laid-out DOT by its braces: every subgraph opens a level, and a
    cluster's caption is the first label inside it.
    """
    stack = []  # one entry per open brace: cluster caption, or None
    awaiting_caption = False
    placed = {}
    for line in dot.splitlines():
        stripped = line.strip()
        if stripped.startswith("subgraph") and stripped.endswith("{"):
            stack.append(None)
            awaiting_caption = "cluster" in stripped
            continue
        if stripped == "}":
            if stack:
                stack.pop()
            awaiting_caption = False
            continue
        if not stripped.startswith("label="):
            continue
        if awaiting_caption:
            texts = [a or b for a, b in _TD_TEXT.findall(stripped)]
            stack[-1] = texts[-1] if texts else ""
            awaiting_caption = False
        elif stripped.startswith('label="'):
            label = stripped[len('label="') :].rstrip('",')
            placed[label] = [c for c in stack if c]
    return placed


def test_vpc_nests_inside_region(tmp_path, monkeypatch):
    graph = {
        "tv_aws_region.us_east_1": ["aws_vpc.primary", "aws_s3_bucket.assets"],
        "aws_vpc.primary": ["tv_aws_az.a"],
        "tv_aws_az.a": ["aws_subnet.app~1"],
        "aws_subnet.app~1": ["aws_instance.app~1"],
    }
    placed = _containers(_draw_dot(graph, tmp_path, monkeypatch))
    assert placed["EC2 App"] == [
        "AWS Cloud",
        "Us East 1",
        "VPC Primary",
        "Availability Zone A",
        "Subnet App",
    ]
    assert placed["S3 Bucket Assets"] == ["AWS Cloud", "Us East 1"]


def test_vpc_nests_inside_account(tmp_path, monkeypatch):
    graph = {
        "aws_account.production": ["aws_vpc.production"],
        "aws_vpc.production": ["tv_aws_az.a"],
        "tv_aws_az.a": ["aws_subnet.private~1"],
        "aws_subnet.private~1": ["aws_lambda_function.api~1"],
    }
    placed = _containers(_draw_dot(graph, tmp_path, monkeypatch))
    assert placed["Lambda API"][:3] == [
        "AWS Cloud",
        "Account Production",
        "VPC Production",
    ]


def test_two_regions_each_hold_their_own_vpc(tmp_path, monkeypatch):
    graph = {
        "tv_aws_region.us_east_1": ["aws_vpc.primary"],
        "tv_aws_region.eu_west_1": ["aws_vpc.dr"],
        "aws_vpc.primary": ["aws_subnet.primary~1"],
        "aws_vpc.dr": ["aws_subnet.dr~1"],
        "aws_subnet.primary~1": ["aws_rds_aurora.primary~1"],
        "aws_subnet.dr~1": ["aws_rds_aurora.dr~1"],
        "aws_rds_aurora.primary~1": ["aws_rds_aurora.dr~1"],
    }
    placed = _containers(_draw_dot(graph, tmp_path, monkeypatch))
    assert placed["RDS Aurora Primary"][1:3] == ["Us East 1", "VPC Primary"]
    assert placed["RDS Aurora Dr"][1:3] == ["Eu West 1", "VPC Dr"]


@pytest.fixture
def aws_groups(monkeypatch):
    monkeypatch.setattr(drawing, "GROUP_NODES", ["aws_vpc", "tv_aws_region"])
    monkeypatch.setattr(drawing, "avl_classes", ["aws_vpc", "tv_aws_region"])


def test_a_group_waits_for_its_undrawn_parent(aws_groups):
    tfdata = {
        "graphdict": {
            "tv_aws_region.a": ["aws_vpc.main"],
            "aws_vpc.main": ["aws_instance.web"],
        },
        "hidden": [],
    }
    assert drawing._waits_for_parent_group("aws_vpc.main", tfdata, [])
    # once the parent has been drawn there is nothing left to wait for
    assert not drawing._waits_for_parent_group(
        "aws_vpc.main", tfdata, ["tv_aws_region.a"]
    )
    assert not drawing._waits_for_parent_group("tv_aws_region.a", tfdata, [])


def test_a_containment_cycle_still_draws(aws_groups):
    """GKE graphs list a cluster in its node pool and the pool in the cluster."""
    tfdata = {
        "graphdict": {
            "tv_aws_region.a": ["aws_vpc.main", "aws_instance.web"],
            "aws_vpc.main": ["tv_aws_region.a"],
        },
        "hidden": [],
    }
    assert not drawing._waits_for_parent_group("aws_vpc.main", tfdata, [])
    assert not drawing._waits_for_parent_group("tv_aws_region.a", tfdata, [])


def test_a_hidden_or_empty_parent_does_not_hold_a_group_back(aws_groups):
    tfdata = {
        "graphdict": {
            "tv_aws_region.a": ["aws_vpc.main"],
            "aws_vpc.main": ["aws_instance.web"],
        },
        "hidden": ["tv_aws_region"],
    }
    assert not drawing._waits_for_parent_group("aws_vpc.main", tfdata, [])


def test_logical_group_draws_inside_the_box_holding_its_members(tmp_path, monkeypatch):
    """Azure's Shared Services group lands inside the resource group.

    The resource group lists the registry and Key Vault too, so it drew first
    and claimed them, leaving the Shared Services box empty off to one side.
    """
    graph = {
        "azurerm_resource_group.app": [
            "azurerm_virtual_network.main",
            "azurerm_container_registry.images",
            "azurerm_key_vault.secrets",
        ],
        "azurerm_virtual_network.main": ["azurerm_subnet.app"],
        "azurerm_subnet.app": ["azurerm_linux_virtual_machine.web"],
        "azurerm_group.shared_services": [
            "azurerm_container_registry.images",
            "azurerm_key_vault.secrets",
        ],
    }
    clusters = _cluster_path(_draw_dot(graph, tmp_path, monkeypatch))
    for label in ("ACR Images", "Key Vault Secrets"):
        assert [c.split(".")[0] for c in clusters[label][-2:]] == [
            "cluster_ResourceGroupCluster",
            "cluster_SharedServicesGroup",
        ]


def _cluster_path(dot: str):
    """Map each node label to the cluster subgraphs around it, outermost first.

    Uses cluster names, not captions, which works for providers such as
    Azure that draw a box caption as a separate label node.
    """
    stack, placed = [], {}
    for line in dot.splitlines():
        stripped = line.strip()
        if stripped.startswith("subgraph") and stripped.endswith("{"):
            stack.append(stripped.split('"')[1] if '"' in stripped else "")
        elif stripped == "}" and stack:
            stack.pop()
        elif stripped.startswith('label="'):
            placed.setdefault(stripped[7:].split('"')[0], [c for c in stack if c])
    return placed


def test_logical_group_with_members_in_no_box_stays_top_level(aws_groups):
    """A shared-services group whose members no box lists is left alone."""
    tfdata = {
        "graphdict": {
            "aws_group.shared_services": ["aws_ecr_repository.images"],
            "aws_vpc.main": ["aws_subnet.app"],
            "aws_subnet.app": ["aws_instance.web"],
        },
        "hidden": [],
    }
    assert drawing._adopting_container("aws_group.shared_services", tfdata) is None


def test_a_node_with_no_icon_class_stays_in_its_box(tmp_path, monkeypatch):
    """A type with no icon of its own draws generic, but inside its subnet."""
    graph = {
        "aws_vpc.main": ["aws_subnet.app"],
        "aws_subnet.app": ["aws_instance.web", "aws_made_up_service.widget"],
    }
    placed = _containers(_draw_dot(graph, tmp_path, monkeypatch))
    widget = next(label for label in placed if label.startswith("Made Up Service"))
    assert placed[widget] == placed["EC2 Web"]
