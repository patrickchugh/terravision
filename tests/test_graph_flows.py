"""Flows on graph (.tvg.json) sources: numbered step badges and a legend.

A graph is drawn as written, so an annotation file for one may only label the
drawing (title, flows, sizes). Flow steps that would draw no badge are
reported instead of silently dropped.
"""

import json

import pytest

from modules.annotations import check_flows, flow_warnings
from modules.helpers import TerravisionError

GRAPH = {
    "tv_aws_users.users": ["aws_cloudfront_distribution.cdn"],
    "aws_cloudfront_distribution.cdn": ["aws_alb.api~1"],
    "aws_vpc.main": ["aws_subnet.public~1", "aws_subnet.private~1"],
    "aws_subnet.public~1": ["aws_alb.api~1"],
    "aws_subnet.private~1": ["aws_ecs_fargate.app~1"],
    "aws_alb.api~1": ["aws_ecs_fargate.app~1"],
    "aws_ecs_fargate.app~1": ["aws_dynamodb_table.orders"],
}


def _flow(*resources):
    return {
        "order": {
            "description": "A customer places an order",
            "steps": [{"resource": r, "detail": f"step {r}"} for r in resources],
        }
    }


# ── Shape ────────────────────────────────────────────────────────────


def test_valid_flows_pass():
    flows = _flow("tv_aws_users.users", "aws_alb.api~1 -> aws_ecs_fargate.app~1")
    assert check_flows(flows) is flows


@pytest.mark.parametrize(
    "flows, problem",
    [
        ([], "non-empty object"),
        ({}, "non-empty object"),
        ({"order": "steps"}, "must be an object"),
        ({"order": {"steps": []}}, "non-empty list of steps"),
        ({"order": {"stops": [{"resource": "a.b"}]}}, "unknown keys ['stops']"),
        ({"order": {"steps": ["aws_alb.api"]}}, "step 1 of flow 'order' must be"),
        ({"order": {"steps": [{"detail": "x"}]}}, "needs a resource"),
        ({"order": {"steps": [{"resource": "a.b", "node": "x"}]}}, "['node']"),
        ({"order": {"steps": [{"resource": "a.b", "detail": 3}]}}, "must be a string"),
        ({"order": {"description": 1, "steps": [{"resource": "a.b"}]}}, "string"),
    ],
)
def test_malformed_flows_are_refused(flows, problem):
    with pytest.raises(TerravisionError, match="Invalid flows") as e:
        check_flows(flows)
    assert problem in str(e.value)


# ── Steps that draw no badge ─────────────────────────────────────────


def test_steps_on_drawn_nodes_and_arrows_have_no_warnings():
    flows = _flow(
        "tv_aws_users.users",
        "aws_cloudfront_distribution.cdn -> aws_alb.api~1",
        "aws_ecs_fargate.app~1 -> aws_alb.api~1",  # against the arrow: fine
        "aws_dynamodb_table.orders",
    )
    assert flow_warnings(flows, GRAPH) == []


def test_steps_that_draw_no_badge_are_reported():
    flows = _flow(
        "aws_alb.api",
        "aws_vpc.main",
        "aws_lambda_function.missing",
        "tv_aws_users.users -> aws_dynamodb_table.orders",
        "aws_alb.api -> aws_ecs_fargate.app~1",
    )
    warnings = flow_warnings(flows, GRAPH)
    assert warnings == [
        "Step 1 of flow 'order' draws no badge: aws_alb.api has numbered "
        "copies; name one, such as aws_alb.api~1.",
        "Step 2 of flow 'order' draws no badge: aws_vpc.main is a container; "
        "name a node inside it.",
        "Step 3 of flow 'order' draws no badge: aws_lambda_function.missing "
        "is not in the graph.",
        "Step 4 of flow 'order' draws no badge: there is no arrow between "
        "tv_aws_users.users and aws_dynamodb_table.orders.",
        "Step 5 of flow 'order' draws no badge: aws_alb.api has numbered "
        "copies; name one, such as aws_alb.api~1.",
    ]


def test_step_numbers_continue_across_flows():
    flows = {**_flow("tv_aws_users.users"), "later": {"steps": [{"resource": "x.y"}]}}
    assert flow_warnings(flows, GRAPH)[0].startswith("Step 2 of flow 'later'")


# ── terravision draw --annotate on a graph file ──────────────────────


def _draw(tmp_path, monkeypatch, annotations):
    import yaml
    from click.testing import CliRunner

    from terravision.terravision import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / "g.tvg.json").write_text(json.dumps(GRAPH))
    (tmp_path / "a.yml").write_text(yaml.safe_dump(annotations))
    return CliRunner().invoke(
        cli,
        ["draw", "--source", "g.tvg.json", "--annotate", "a.yml", "--format", "dot"],
    )


def test_draw_takes_flows_for_a_graph_file(tmp_path, monkeypatch):
    flows = _flow(
        "tv_aws_users.users",
        "aws_alb.api~1 -> aws_ecs_fargate.app~1",
        "aws_ecs_fargate.app~1 -> aws_alb.api~1",
        "aws_alb.api",
    )
    result = _draw(tmp_path, monkeypatch, {"title": "Order Platform", "flows": flows})
    assert result.exit_code == 0, result.output
    assert "Step 4 of flow 'order' draws no badge" in result.output
    dot = (tmp_path / "architecture.dot.dot").read_text()
    assert 'label="Order Platform"' in dot
    assert "step aws_alb.api~1 -&gt; aws_ecs_fargate.app~1" in dot  # legend
    # Steps 2 and 3 run both ways along one arrow and share its badge.
    from modules.drawing import _badge_image

    for n in ("1", "2", "3"):
        assert str(_badge_image(n, "#E74C3C")) in dot
    # The arrow's badge holds circles 2 and 3 together.
    two, three = (str(_badge_image(n, "#E74C3C")) for n in ("2", "3"))
    assert any(two in line and three in line for line in dot.splitlines())


@pytest.mark.parametrize(
    "annotations, message",
    [
        ({"add": {"aws_sqs_queue.q": {}}}, "has add, which a graph file"),
        ({"disconnect": {}, "remove": []}, "has disconnect, remove"),
        ({"format": "9.9", "title": "x"}, "unsupported format '9.9'"),
        ({"flows": {"order": {"steps": []}}}, "Invalid flows"),
    ],
)
def test_draw_refuses_annotations_that_change_a_graph(
    tmp_path, monkeypatch, annotations, message
):
    result = _draw(tmp_path, monkeypatch, annotations)
    assert result.exit_code == 1
    assert message in result.output
    assert not (tmp_path / "architecture.dot.dot").exists()


# ── Edge labels ──────────────────────────────────────────────────────


def test_edge_labels_to_connect():
    from modules.annotations import edge_labels_to_connect

    assert edge_labels_to_connect({"a.x -> b.y": "Reads", "a.x -> c.z": "Writes"}) == {
        "a.x": [{"b.y": "Reads"}, {"c.z": "Writes"}]
    }
    for bad in ([], {}, {"a.x": "no arrow"}, {"a.x -> b.y": 3}):
        with pytest.raises(TerravisionError, match="edge_labels"):
            edge_labels_to_connect(bad)


def test_edge_labels_label_existing_arrows_only():
    from modules.annotations import apply_edge_labels

    tfdata = {"graphdict": {k: list(v) for k, v in GRAPH.items()}}
    warnings = apply_edge_labels(
        tfdata,
        {
            "aws_alb.api~1": [{"aws_ecs_fargate.app~1": "Routes requests"}],
            # Written against the arrow: stored on the drawn direction.
            "aws_dynamodb_table.orders": [{"aws_ecs_fargate.app~1": "Returns rows"}],
            "tv_aws_users.users": [{"aws_dynamodb_table.orders": "Nope"}],
            "aws_vpc.main": [{"aws_subnet.public~1": "Box"}],
        },
    )
    meta = tfdata["meta_data"]
    assert meta["aws_alb.api~1"]["edge_labels"] == [
        {"aws_ecs_fargate.app~1": "Routes requests"}
    ]
    assert meta["aws_ecs_fargate.app~1"]["edge_labels"] == [
        {"aws_dynamodb_table.orders": "Returns rows"}
    ]
    assert tfdata["graphdict"] == GRAPH  # nothing added
    assert len(warnings) == 2
    assert "there is no arrow between them" in warnings[0]
    assert "arrows to containers are not drawn" in warnings[1]


def test_draw_labels_arrows_from_connect(tmp_path, monkeypatch):
    result = _draw(
        tmp_path,
        monkeypatch,
        {
            "connect": {
                "aws_ecs_fargate.app~1": [
                    {"aws_dynamodb_table.orders": "Writes orders"}
                ],
                "aws_ecs_fargate.app~2": [{"aws_sqs_queue.new": "Would add an arrow"}],
            }
        },
    )
    assert result.exit_code == 0, result.output
    assert "no arrow between them" in result.output
    dot = (tmp_path / "architecture.dot.dot").read_text()
    assert "Writes orders" in dot
    assert "aws_sqs_queue" not in dot


# ── Badges in draw.io, and badges beside edge labels ─────────────────


def _render(tmp_path, monkeypatch, fmt, annotations):
    import yaml
    from click.testing import CliRunner

    from terravision.terravision import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / "g.tvg.json").write_text(json.dumps(GRAPH))
    (tmp_path / "a.yml").write_text(yaml.safe_dump(annotations))
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", "g.tvg.json", "--annotate", "a.yml", "--format", fmt],
    )
    assert result.exit_code == 0, result.output


FLOW_AND_LABEL = {
    "flows": _flow("aws_alb.api~1", "aws_alb.api~1 -> aws_ecs_fargate.app~1"),
    "connect": {"aws_alb.api~1": [{"aws_ecs_fargate.app~1": "Routes requests"}]},
}


def test_an_edge_keeps_its_label_beside_its_badge(tmp_path, monkeypatch):
    """Edge labels are xlabels too; the badge used to replace the label."""
    from modules.drawing import _badge_image

    _render(tmp_path, monkeypatch, "dot", FLOW_AND_LABEL)
    dot = (tmp_path / "architecture.dot.dot").read_text()
    badge = str(_badge_image("2", "#E74C3C"))
    assert any(badge in l and "Routes requests" in l for l in dot.splitlines())


def test_drawio_draws_step_badges_on_their_cells(tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET

    _render(tmp_path, monkeypatch, "drawio", FLOW_AND_LABEL)
    root = ET.parse(tmp_path / "architecture.drawio").getroot()
    cells = {c.get("id"): c for c in root.iter("mxCell")}
    badges = [c for c in cells.values() if (c.get("style") or "").startswith("ellipse")]
    assert sorted(c.get("value") for c in badges) == ["1", "2"]
    parents = {c.get("value"): cells[c.get("parent")] for c in badges}
    # Step 1 sits on the ALB's node cell, step 2 on the arrow it labels.
    assert parents["1"].get("vertex") == "1"
    assert parents["2"].get("edge") == "1"
    assert parents["2"].get("value") == "Routes requests"
    for c in badges:
        assert c.find("mxGeometry").get("relative") == "1"
