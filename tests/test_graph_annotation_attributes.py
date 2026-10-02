"""Annotation files for graph (.tvg.json) sources, and CIDR labels.

A graph is drawn as written, so its annotation file may use every section
except those that change its structure (add, remove, disconnect). ``connect``
only labels arrows the graph has; ``update`` only sets attributes on nodes it
has, such as the CIDR range shown in a network or subnet box. The same CIDR
labels work in Terraform mode, where an annotation wins over the plan.
"""

import copy
import json
from pathlib import Path

import pytest
import yaml

from modules import mcp_service
from modules.annotations import (
    GRAPH_ANNOTATION_KEYS,
    apply_attribute_updates,
    load_graph_annotations,
)
from modules.helpers import TerravisionError, get_cidr_label
from modules.mcp_service import McpServiceError

AWS_GRAPH = {
    "tv_aws_users.users": ["aws_alb.api~1", "aws_alb.api~2"],
    "aws_vpc.main": ["aws_subnet.public~1", "aws_subnet.public~2"],
    "aws_subnet.public~1": ["aws_alb.api~1"],
    "aws_subnet.public~2": ["aws_alb.api~2"],
    "aws_alb.api~1": ["aws_ecs_fargate.app~1"],
    "aws_alb.api~2": ["aws_ecs_fargate.app~2"],
    "aws_ecs_fargate.app~1": ["aws_dynamodb_table.orders"],
    "aws_ecs_fargate.app~2": ["aws_dynamodb_table.orders"],
}
AZURE_GRAPH = {
    "azurerm_virtual_network.hub": ["azurerm_subnet.app~1"],
    "azurerm_subnet.app~1": ["azurerm_linux_virtual_machine.vm~1"],
}
GCP_GRAPH = {
    "google_compute_network.vpc": ["google_compute_subnetwork.web~1"],
    "google_compute_subnetwork.web~1": ["google_compute_instance.vm~1"],
}
REPLAY = Path(__file__).parent / "json" / "bastion-tfdata.json"
VPC = "module.private-vpc.aws_vpc.main_vpc"
SUBNET = "module.private-vpc.aws_subnet.public_subnets[0]~1"


def _write(tmp_path, annotations, name="a.yml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(annotations))
    return str(path)


def _compile(tmp_path, graph, annotations):
    """Compile a graph file with an --annotate file, as draw does."""
    from terravision.terravision import compile_tfdata

    (tmp_path / "g.tvg.json").write_text(json.dumps(graph))
    return compile_tfdata(
        str(tmp_path / "g.tvg.json"),
        [],
        "default",
        False,
        annotate=_write(tmp_path, annotations),
    )


def _draw(tmp_path, monkeypatch, graph, annotations):
    """Run terravision draw on a graph file; return (result, dot text)."""
    from click.testing import CliRunner

    from terravision.terravision import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / "g.tvg.json").write_text(json.dumps(graph))
    _write(tmp_path, annotations)
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", "g.tvg.json", "--annotate", "a.yml", "--format", "dot"],
    )
    dot = tmp_path / "architecture.dot.dot"
    return result, dot.read_text() if dot.exists() else ""


# ── Sections a graph file takes ──────────────────────────────────────


@pytest.mark.parametrize(
    "section, value",
    [
        ("format", "0.3"),
        ("title", "Orders"),
        ("fontsize", 30),
        ("iconsize", 150),
        ("flows", {"o": {"steps": [{"resource": "aws_alb.api~1"}]}}),
        ("connect", {"aws_alb.api~1": [{"aws_ecs_fargate.app~1": "Routes"}]}),
        ("update", {"aws_vpc.main": {"cidr_block": "10.0.0.0/16"}}),
        ("generated_by", {"backend": "ollama", "model": "llama3"}),
    ],
)
def test_graph_files_take_every_non_structural_section(tmp_path, section, value):
    assert section in GRAPH_ANNOTATION_KEYS
    loaded = load_graph_annotations(_write(tmp_path, {section: value}), AWS_GRAPH)
    assert loaded[section] == value


@pytest.mark.parametrize("section", ["add", "remove", "disconnect"])
def test_graph_files_refuse_structural_changes(tmp_path, section):
    path = _write(tmp_path, {section: {"aws_sqs_queue.q": []}})
    with pytest.raises(TerravisionError) as e:
        load_graph_annotations(path, AWS_GRAPH)
    message = str(e.value)
    assert f"has {section}, which a graph file does not take" in message
    assert "change the graph itself instead" in message
    assert section not in GRAPH_ANNOTATION_KEYS


def test_graph_files_refuse_unknown_sections(tmp_path):
    with pytest.raises(TerravisionError, match="labels, which is not an annotation"):
        load_graph_annotations(_write(tmp_path, {"labels": {}}), AWS_GRAPH)


@pytest.mark.parametrize(
    "update", [[], {}, {"aws_vpc.main": "10.0.0.0/16"}, {"aws_vpc.main": {}}]
)
def test_malformed_updates_are_refused(tmp_path, update):
    with pytest.raises(TerravisionError, match="update"):
        load_graph_annotations(_write(tmp_path, {"update": update}), AWS_GRAPH)


def test_draw_refuses_add_with_a_clear_error(tmp_path, monkeypatch):
    result, dot = _draw(
        tmp_path, monkeypatch, AWS_GRAPH, {"add": {"aws_sqs_queue.q": {}}}
    )
    assert result.exit_code == 1
    assert "change the graph itself instead" in result.output
    assert dot == ""


# ── update reaches the CIDR label ────────────────────────────────────


def test_update_puts_cidr_ranges_in_aws_labels(tmp_path, monkeypatch):
    result, dot = _draw(
        tmp_path,
        monkeypatch,
        AWS_GRAPH,
        {
            "update": {
                "aws_vpc.main": {"cidr_block": "10.0.0.0/16"},
                "aws_subnet.public~1": {"cidr_block": "10.0.1.0/24"},
                "aws_subnet.public~2": {"cidr_block": "10.0.2.0/24"},
            }
        },
    )
    assert result.exit_code == 0, result.output
    assert "VPC Main (10.0.0.0/16)" in dot
    assert "Subnet Public (10.0.1.0/24)" in dot
    assert "Subnet Public (10.0.2.0/24)" in dot
    assert "WARNING" not in result.output


def test_update_puts_list_cidr_ranges_in_azure_labels(tmp_path, monkeypatch):
    result, dot = _draw(
        tmp_path,
        monkeypatch,
        AZURE_GRAPH,
        {
            "update": {
                "azurerm_virtual_network.hub": {
                    "address_space": ["10.1.0.0/16", "10.2.0.0/16"]
                },
                "azurerm_subnet.app~1": {"address_prefixes": ["10.1.1.0/24"]},
            }
        },
    )
    assert result.exit_code == 0, result.output
    assert "VNET Hub (10.1.0.0/16, 10.2.0.0/16)" in dot
    assert "Subnet App (10.1.1.0/24)" in dot


def test_update_puts_cidr_ranges_in_gcp_labels(tmp_path, monkeypatch):
    result, dot = _draw(
        tmp_path,
        monkeypatch,
        GCP_GRAPH,
        {
            "update": {
                "google_compute_subnetwork.web~1": {"ip_cidr_range": "10.8.0.0/20"}
            }
        },
    )
    assert result.exit_code == 0, result.output
    assert "Subnet Web (10.8.0.0/20)" in dot


def test_update_reaches_meta_data(tmp_path):
    tfdata = _compile(
        tmp_path,
        AWS_GRAPH,
        {"update": {"aws_subnet.public~1": {"cidr_block": "10.0.1.0/24"}}},
    )
    assert tfdata["meta_data"]["aws_subnet.public~1"]["cidr_block"] == "10.0.1.0/24"
    assert "cidr_block" not in tfdata["meta_data"].get("aws_subnet.public~2", {})
    assert get_cidr_label("aws_subnet.public~1", tfdata) == "10.0.1.0/24"


# ── Numbered copies, wildcards and unknown nodes ─────────────────────


def test_a_name_without_a_number_sets_every_copy():
    tfdata = {"graphdict": copy.deepcopy(AWS_GRAPH)}
    warnings = apply_attribute_updates(
        tfdata, {"aws_subnet.public": {"tier": "public"}}
    )
    assert warnings == []
    for n in ("aws_subnet.public~1", "aws_subnet.public~2"):
        assert tfdata["meta_data"][n]["tier"] == "public"


def test_wildcards_match_as_for_terraform():
    tfdata = {"graphdict": copy.deepcopy(AWS_GRAPH)}
    assert apply_attribute_updates(tfdata, {"aws_subnet*": {"tier": "x"}}) == []
    assert set(tfdata["meta_data"]) == {"aws_subnet.public~1", "aws_subnet.public~2"}


def test_an_update_for_a_missing_node_is_a_warning(tmp_path, monkeypatch):
    result, dot = _draw(
        tmp_path,
        monkeypatch,
        AWS_GRAPH,
        {
            "update": {
                "aws_subnet.private~1": {"cidr_block": "10.0.9.0/24"},
                "aws_vpc.main": {"cidr_block": "10.0.0.0/16"},
            }
        },
    )
    assert result.exit_code == 0, result.output
    assert "The update for aws_subnet.private~1 is not applied" in result.output
    assert "VPC Main (10.0.0.0/16)" in dot
    assert "aws_subnet.private" not in dot


def test_an_update_never_adds_a_node(tmp_path):
    tfdata = _compile(
        tmp_path, AWS_GRAPH, {"update": {"aws_sqs_queue.new": {"label": "x"}}}
    )
    assert "aws_sqs_queue.new" not in tfdata["graphdict"]
    assert "aws_sqs_queue.new" not in tfdata["meta_data"]


# ── connect, and edge_labels under update, never add an arrow ────────


def test_labels_never_add_an_arrow(tmp_path, monkeypatch):
    annotations = {
        "connect": {"tv_aws_users.users": [{"aws_dynamodb_table.orders": "Nope"}]},
        "update": {
            "aws_alb.api~1": {
                "edge_labels": [
                    {"aws_ecs_fargate.app~1": "Routes"},
                    {"aws_dynamodb_table.orders": "Nope either"},
                ]
            }
        },
    }
    tfdata = _compile(tmp_path, AWS_GRAPH, annotations)
    assert tfdata["graphdict"]["tv_aws_users.users"] == AWS_GRAPH["tv_aws_users.users"]
    assert tfdata["graphdict"]["aws_alb.api~1"] == AWS_GRAPH["aws_alb.api~1"]

    result, dot = _draw(tmp_path, monkeypatch, AWS_GRAPH, annotations)
    assert result.exit_code == 0, result.output
    assert result.output.count("there is no arrow between them") == 2
    assert "Routes" in dot
    assert "Nope" not in dot


# ── Terraform mode: annotations and the plan ─────────────────────────


def _replay(tmp_path, annotations):
    from terravision.terravision import compile_tfdata

    data = json.loads(REPLAY.read_text())
    data["annotations"] = annotations
    path = tmp_path / "tfdata.json"
    path.write_text(json.dumps(data))
    return compile_tfdata(str(path), [], "default", False)


def test_terraform_plan_cidr_is_used_without_annotations(tmp_path):
    tfdata = _replay(tmp_path, {})
    assert get_cidr_label(VPC, tfdata) == "172.68.0.0/16"
    assert get_cidr_label(SUBNET, tfdata) == "172.68.0.0/24"


def test_terraform_update_wins_over_the_plan(tmp_path):
    tfdata = _replay(tmp_path, {"update": {VPC: {"cidr_block": "10.0.0.0/16"}}})
    assert get_cidr_label(VPC, tfdata) == "10.0.0.0/16"
    assert get_cidr_label(SUBNET, tfdata) == "172.68.0.0/24"


def test_terraform_added_subnet_shows_its_cidr(tmp_path):
    tfdata = _replay(
        tmp_path, {"add": {"aws_subnet.external": {"cidr_block": "10.9.0.0/24"}}}
    )
    assert get_cidr_label("aws_subnet.external", tfdata) == "10.9.0.0/24"


def _tfdata(plan, meta, update=None):
    return {
        "graphdict": {},
        "original_metadata": {"aws_subnet.a": plan} if plan is not None else {},
        "meta_data": {"aws_subnet.a": meta, "aws_subnet.a~2": dict(meta)},
        "annotations": {"update": update} if update else {},
    }


@pytest.mark.parametrize(
    "plan, meta, update, expected",
    [
        # The plan beats meta_data, which may hold a variable's default.
        ({"cidr_block": "10.0.1.0/24"}, {"cidr_block": "192.168.0.0/24"}, None,
         "10.0.1.0/24"),
        # No CIDR in the plan: meta_data (written by add:) is used.
        (None, {"cidr_block": "10.0.5.0/24"}, None, "10.0.5.0/24"),
        ({"cidr_block": True}, {"cidr_block": "10.0.5.0/24"}, None, "10.0.5.0/24"),
        # Raw HCL is never shown.
        ({"cidr_block": True}, {"cidr_block": "${cidrsubnet(var.cidr, 8, 1)}"},
         None, ""),
        ({}, {"cidr_block": "${var.prefix}/24"}, None, ""),
        # An explicit update wins over the plan.
        ({"cidr_block": "10.0.1.0/24"}, {}, {"aws_subnet.a": {"cidr_block":
         "10.7.0.0/24"}}, "10.7.0.0/24"),
        # A wildcard update applies, an exact name beats it.
        ({"cidr_block": "10.0.1.0/24"}, {}, {"aws_subnet*": {"cidr_block":
         "10.6.0.0/24"}}, "10.6.0.0/24"),
        ({}, {}, {"aws_subnet*": {"cidr_block": "10.6.0.0/24"}, "aws_subnet.a":
         {"cidr_block": "10.7.0.0/24"}}, "10.7.0.0/24"),
    ],
)  # fmt: skip
def test_cidr_label_precedence(plan, meta, update, expected):
    assert get_cidr_label("aws_subnet.a", _tfdata(plan, meta, update)) == expected


def test_a_base_name_update_reaches_numbered_copies():
    tfdata = _tfdata({}, {}, {"aws_subnet.a": {"cidr_block": "10.7.0.0/24"}})
    assert get_cidr_label("aws_subnet.a~2", tfdata) == "10.7.0.0/24"


# ── MCP render_graph attributes ──────────────────────────────────────


@pytest.fixture
def outdir(tmp_path):
    saved_dir, saved_rendered = mcp_service._OUTPUT_DIR, set(mcp_service._RENDERED)
    mcp_service._RENDERED.clear()
    mcp_service.set_output_dir(str(tmp_path))
    yield tmp_path
    mcp_service._OUTPUT_DIR = saved_dir
    mcp_service._RENDERED.clear()
    mcp_service._RENDERED.update(saved_rendered)


ATTRIBUTES = {
    "aws_vpc.main": {"cidr_block": "10.0.0.0/16"},
    "aws_subnet.public~1": {"cidr_block": "10.0.1.0/24"},
    "aws_subnet.missing~1": {"cidr_block": "10.0.9.0/24"},
}


def test_render_graph_attributes_label_networks_and_are_saved(outdir):
    result = mcp_service.run_render_graph(
        AWS_GRAPH, outfile="cidr", attributes=ATTRIBUTES, preview=False
    )
    svg = Path(result["files"]["svg"]).read_text()
    assert "VPC Main (10.0.0.0/16)" in svg
    assert "Subnet Public (10.0.1.0/24)" in svg
    assert result["warnings"] == [
        "The update for aws_subnet.missing~1 is not applied: aws_subnet.missing~1 "
        "is not in the graph. Name a node the graph has, such as "
        "aws_subnet.public~1."
    ]
    saved = yaml.safe_load(Path(result["files"]["annotations"]).read_text())
    assert saved["update"] == ATTRIBUTES
    # The graph file is unchanged: attributes never add a node.
    assert "aws_subnet.missing~1" not in json.loads(
        Path(result["files"]["graph"]).read_text()
    )


def test_saved_attributes_redraw_with_the_cli(outdir, monkeypatch):
    from click.testing import CliRunner

    from terravision.terravision import cli

    result = mcp_service.run_render_graph(
        AWS_GRAPH, outfile="again", attributes=ATTRIBUTES, preview=False
    )
    monkeypatch.chdir(outdir)
    run = CliRunner().invoke(
        cli,
        ["draw", "--source", result["files"]["graph"], "--annotate",
         result["files"]["annotations"], "--format", "dot", "--outfile", "cli"],
    )  # fmt: skip
    assert run.exit_code == 0, run.output
    assert "Subnet Public (10.0.1.0/24)" in (outdir / "cli.dot.dot").read_text()


@pytest.mark.parametrize(
    "attributes",
    [["aws_vpc.main"], {"aws_vpc.main": "10.0.0.0/16"}, {"aws_vpc.main": {}}],
)
def test_malformed_attributes_leave_no_files(outdir, attributes):
    with pytest.raises(McpServiceError, match="attributes"):
        mcp_service.run_render_graph(AWS_GRAPH, outfile="bad", attributes=attributes)
    assert list(outdir.iterdir()) == []


def test_render_graph_tool_takes_attributes():
    pytest.importorskip("mcp")
    import asyncio

    from modules.mcp_server import build_server

    tools = asyncio.run(build_server().list_tools())
    spec = next(t for t in tools if t.name == "render_graph").input_schema
    attributes = spec["properties"]["attributes"]
    assert "CIDR" in attributes["description"]
    assert "attributes" not in spec.get("required", [])
