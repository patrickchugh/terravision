"""The diagram title clears every box, including those outside the cloud.

shiftLabel.gvpr placed the title above the tallest node and the cloud box,
but not above boxes drawn outside the cloud. A tv_aws_onprem data centre
whose customer gateway connects into AWS is laid out above the cloud box,
so the title was drawn across the data centre's caption.
"""

import json
import re

from click.testing import CliRunner

from terravision.terravision import cli

GRAPH = {
    "tv_aws_onprem.datacentre": ["aws_customer_gateway.router"],
    "aws_customer_gateway.router": ["aws_vpn_connection.vpn"],
    "aws_vpc.main": ["aws_subnet.private~1"],
    "aws_subnet.private~1": ["aws_instance.app~1"],
    "aws_vpn_connection.vpn": ["aws_vpn_gateway.vgw"],
    "aws_vpn_gateway.vgw": ["aws_instance.app~1"],
}


def _laid_out_dot(tmp_path, monkeypatch) -> str:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "graph.tvg.json"
    source.write_text(json.dumps(GRAPH))
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", str(source), "--format", "dot", "--outfile", "out"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    [dot] = list(tmp_path.glob("out*.dot"))
    return dot.read_text()


def _top_level_box_tops(dot: str):
    """Top edge (largest y) of each cluster directly under the root graph."""
    tops = []
    depth = 0
    in_top_cluster = False
    for line in dot.splitlines():
        stripped = line.strip()
        if stripped.startswith("subgraph") and stripped.endswith("{"):
            depth += 1
            in_top_cluster = depth == 1 and "cluster" in stripped
            continue
        if stripped == "}":
            depth -= 1
            in_top_cluster = False
            continue
        if in_top_cluster:
            match = re.search(r'bb="([\d.]+),([\d.]+),([\d.]+),([\d.]+)"', stripped)
            if match:
                tops.append(float(match.group(4)))
                in_top_cluster = False
    return tops


def _title_y(dot: str) -> float:
    title = dot[dot.index("_titlenode=1") :]
    return float(re.search(r'pos="[\d.]+,([\d.]+)', title).group(1))


def test_title_sits_above_an_on_premises_box(tmp_path, monkeypatch):
    dot = _laid_out_dot(tmp_path, monkeypatch)
    tops = _top_level_box_tops(dot)
    # the AWS Cloud box and the data centre box
    assert len(tops) == 2
    # the title's text centres on pos and is about 80pt tall at fontsize 56
    assert _title_y(dot) - 40 > max(tops)
