"""The footer and flow legend start below every node, however tall the legend.

shiftLabel.gvpr placed the legend's centre a fixed distance below the
lowest node's centre. A node outside the cloud (the internet, below an
internet gateway) reaches lower than its centre, and a legend with many
steps rises far above its own centre, so the legend was drawn over the
internet icon in the multi-account network example.
"""

import json
import re

import yaml
from click.testing import CliRunner

from terravision.terravision import cli

GRAPH = {
    "tv_aws_users.users": ["aws_alb.web"],
    "aws_vpc.main": ["aws_subnet.public~1", "aws_internet_gateway.igw"],
    "aws_subnet.public~1": ["aws_alb.web"],
    "aws_alb.web": ["aws_internet_gateway.igw"],
    "aws_internet_gateway.igw": ["tv_aws_internet.internet"],
}
# Twelve steps make a legend several times taller than the footer
ANNOTATIONS = {
    "format": "0.3",
    "flows": {
        f"flow_{i}": {
            "description": f"Flow {i}",
            "steps": [
                {"resource": "tv_aws_users.users -> aws_alb.web", "detail": "In"},
                {
                    "resource": "aws_alb.web -> aws_internet_gateway.igw",
                    "detail": "Out",
                },
                {
                    "resource": "aws_internet_gateway.igw -> tv_aws_internet.internet",
                    "detail": "Internet",
                },
            ],
        }
        for i in range(4)
    },
}


def _nodes(tmp_path, monkeypatch):
    """Each laid-out node's attributes, from the DOT output."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "graph.tvg.json").write_text(json.dumps(GRAPH))
    (tmp_path / "flows.yml").write_text(yaml.safe_dump(ANNOTATIONS))
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", "graph.tvg.json", "--annotate", "flows.yml",
         "--format", "dot", "--outfile", "out"],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    [dot] = list(tmp_path.glob("out*.dot"))
    nodes = []
    for block in re.findall(r'^\t"[^"]+"\t\[(.*?)\];', dot.read_text(), re.M | re.S):
        pos = re.search(r'\bpos="([\d.]+),([\d.]+)!?"', block)
        height = re.search(r"\bheight=([\d.]+)", block)
        if pos and height:
            y, half = float(pos.group(2)), float(height.group(1)) * 72.0 / 2.0
            nodes.append({"block": block, "top": y + half, "bottom": y - half})
    return nodes


def test_footer_and_legend_start_below_every_node(tmp_path, monkeypatch):
    nodes = _nodes(tmp_path, monkeypatch)
    row = [
        n
        for n in nodes
        if "_legendnode=1" in n["block"] or "_footernode=1" in n["block"]
    ]
    others = [n for n in nodes if n not in row and "_titlenode=1" not in n["block"]]
    assert len(row) == 2, "expected a footer and a legend"
    internet = [n for n in others if "tv_aws_internet.internet" in n["block"]]
    assert internet, "the internet node is drawn"
    lowest = min(n["bottom"] for n in others)
    for node in row:
        assert node["top"] < lowest
    # The two share a row: their tops line up
    assert abs(row[0]["top"] - row[1]["top"]) < 2.0
