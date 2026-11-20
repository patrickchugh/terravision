"""Two-way links and hidden types in exported graphs (issue #304).

A graph exported from Terraform must pass the skill's validator and redraw
the way Terraform drew it: a pair of nodes listing each other is one line
with an arrowhead at each end, drawn once, and plumbing TerraVision hides
(route tables, firewall policies) is not reported as an unknown type.
"""

import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "terravision" / "terravision.py"
HYBRID = ROOT / "tests" / "fixtures" / "aws_terraform" / "hybrid_network"


def _validator():
    path = ROOT / "skills/terravision-cloud-diagrams/scripts/validate_graph.py"
    spec = importlib.util.spec_from_file_location("validate_graph", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(args, cwd):
    result = subprocess.run(
        [str(CLI), *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def _arrows(svg: Path) -> list:
    """(edge title, arrowheads) for every arrow in a rendered SVG."""
    text = svg.read_text(encoding="utf-8")
    return [
        (title, body.count("<polygon"))
        for title, body in re.findall(
            r'class="edge">\s*<title>(.*?)</title>(.*?)</g>', text, re.S
        )
    ]


def test_validator_accepts_two_way_links_and_hidden_types():
    graph = {
        "aws_ec2_transit_gateway.hub": [
            "aws_ec2_transit_gateway_vpc_attachment.app",
            "aws_ec2_transit_gateway_route_table.spokes",
        ],
        "aws_ec2_transit_gateway_vpc_attachment.app": ["aws_ec2_transit_gateway.hub"],
        "aws_ec2_transit_gateway_route_table.spokes": ["aws_ec2_transit_gateway.hub"],
    }
    assert _validator().warnings(graph) == []


def test_validator_still_reports_types_it_does_not_know():
    warnings = _validator().warnings({"aws_lamda_function.x": []})
    assert any(w.startswith("Unknown type 'aws_lamda_function'") for w in warnings)


def test_two_way_pair_in_a_graph_file_is_one_line_with_two_heads(tmp_path):
    graph = {
        "aws_lambda_function.a": ["aws_sqs_queue.q"],
        "aws_sqs_queue.q": ["aws_lambda_function.a"],
    }
    (tmp_path / "g.tvg.json").write_text(json.dumps(graph))
    _run(
        ["draw", "--source", "g.tvg.json", "--format", "svg", "--outfile", "d"],
        tmp_path,
    )
    assert [heads for _, heads in _arrows(tmp_path / "d.dot.svg")] == [2]


def test_exported_hybrid_network_passes_and_redraws_the_same(tmp_path):
    common = ["--planfile", str(HYBRID / "plan.json")]
    common += ["--graphfile", str(HYBRID / "graph.dot")]
    _run(
        ["graphdata", "--source", str(HYBRID), *common, "--outfile", "g.tvg.json"],
        tmp_path,
    )
    graph = json.loads((tmp_path / "g.tvg.json").read_text())
    assert _validator().warnings(graph) == []

    fmt = ["--format", "svg"]
    _run(["draw", "--source", str(HYBRID), *common, *fmt, "--outfile", "tf"], tmp_path)
    _run(["draw", "--source", "g.tvg.json", *fmt, "--outfile", "js"], tmp_path)
    from_terraform = _arrows(next(tmp_path.glob("tf*.svg")))
    from_export = _arrows(tmp_path / "js.dot.svg")

    # No pair of nodes is joined twice: two-way links are drawn once
    for arrows in (from_terraform, from_export):
        pairs = [frozenset(re.split(r"->|--", t)) for t, _ in arrows]
        assert len(pairs) == len(set(pairs))
    assert len(from_terraform) == len(from_export)
    two_headed = [heads for _, heads in from_export if heads == 2]
    assert len(two_headed) >= 10
