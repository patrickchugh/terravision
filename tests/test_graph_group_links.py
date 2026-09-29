"""Peerings in graph files draw as a line between the two network boxes.

Issue #220: a graph file carries no attributes, so the peering's two ends
were never found. Azure hid the peering, AWS drew it as an icon inside one
VPC and GCP as a generic box, and none drew the line. The graph says both
ends: the network that lists the peering, and the network the peering lists.
"""

import json

import pytest
from click.testing import CliRunner

from terravision.terravision import cli

PEERINGS = {
    "aws": ("aws_vpc", "aws_subnet", "aws_instance", "aws_vpc_peering_connection"),
    "azure": (
        "azurerm_virtual_network",
        "azurerm_subnet",
        "azurerm_linux_virtual_machine",
        "azurerm_virtual_network_peering",
    ),
    "gcp": (
        "google_compute_network",
        "google_compute_subnetwork",
        "google_compute_instance",
        "google_compute_network_peering",
    ),
}


def _peered(provider):
    network, subnet, vm, peering = PEERINGS[provider]
    return {
        f"{network}.a": [f"{subnet}.a", f"{peering}.a_to_b"],
        f"{subnet}.a": [f"{vm}.a"],
        f"{network}.b": [f"{subnet}.b"],
        f"{subnet}.b": [f"{vm}.b"],
        f"{peering}.a_to_b": [f"{network}.b"],
    }


@pytest.mark.parametrize("provider", sorted(PEERINGS))
def test_peering_in_a_graph_file_draws_a_line(tmp_path, provider):
    source = tmp_path / "peered.tvg.json"
    source.write_text(json.dumps(_peered(provider)))
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(source),
            "--format",
            "dot",
            "--outfile",
            str(tmp_path / "peered"),
        ],
    )
    assert result.exit_code == 0, result.output
    [dot] = tmp_path.glob("peered*.dot")
    text = dot.read_text()
    links = [e for e in text.split("];") if "_grouplink=1" in e]
    assert len(links) == 1, "one line between the two networks"
    assert "ltail=" in links[0] and "lhead=" in links[0]
    peering = PEERINGS[provider][3]
    assert f'tf_resource_name="{peering}.a_to_b"' not in text, "no icon as well"


def _validator():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).parents[1]
        / "skills/terravision-cloud-diagrams/scripts/validate_graph.py"
    )
    spec = importlib.util.spec_from_file_location("validate_graph", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("provider", sorted(PEERINGS))
def test_validator_accepts_a_listed_peering(provider):
    validator = _validator()
    graph = _peered(provider)
    assert validator.validate(graph) == []
    assert not [w for w in validator.warnings(graph) if "peering" in w]


def test_validator_warns_about_a_peering_that_cannot_be_drawn():
    graph = _peered("azure")
    graph["azurerm_virtual_network_peering.a_to_b"] = []
    [warning] = [w for w in _validator().warnings(graph) if "peering" in w]
    assert "is drawn as a line between two azurerm_virtual_network boxes" in warning


def _draw_dot(tmp_path, graph):
    source = tmp_path / "graph.tvg.json"
    source.write_text(json.dumps(graph))
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(source),
            "--format",
            "dot",
            "--outfile",
            str(tmp_path / "graph"),
        ],
    )
    assert result.exit_code == 0, result.output
    [dot] = tmp_path.glob("graph*.dot")
    return dot.read_text(), result.output


def test_peering_to_a_network_outside_the_diagram_keeps_its_icon(tmp_path):
    """A peering to another account's VPC has no second box to draw a line
    to; its icon is all that shows the peering exists."""
    graph = _peered("aws")
    graph["aws_vpc_peering_connection.a_to_b"] = []
    text, _ = _draw_dot(tmp_path, graph)
    assert "_grouplink=1" not in text
    assert 'tf_resource_name="aws_vpc_peering_connection.a_to_b"' in text


def test_a_hidden_peering_that_cannot_be_drawn_is_reported(tmp_path):
    """Azure never draws peerings as icons, so an undrawable one is named."""
    graph = _peered("azure")
    graph["azurerm_virtual_network_peering.a_to_b"] = []
    _, output = _draw_dot(tmp_path, graph)
    assert "azurerm_virtual_network_peering.a_to_b is not drawn" in output


_LINK_AND_BOXES = r"""
BEG_G {
  graph_t a, b, c;
  for (a = fstsubg($G); a; a = nxtsubg(a)) {
    printf("box|%s|%s\n", a.name, a.bb);
    for (b = fstsubg(a); b; b = nxtsubg(b)) {
      printf("box|%s|%s\n", b.name, b.bb);
      for (c = fstsubg(b); c; c = nxtsubg(c)) printf("box|%s|%s\n", c.name, c.bb);
    }
  }
}
E[_grouplink=="1"] { printf("link|%s|%s|%s|%s\n", ltail, lhead, pos, xlp); }
"""


def _gvpr(tmp_path, script, dot):
    import subprocess

    path = tmp_path / "query.gvpr"
    path.write_text(script)
    return subprocess.run(
        ["gvpr", "-f", str(path), str(dot)], capture_output=True, text=True, check=True
    ).stdout


def _on_border(point, bb):
    x, y = point
    x0, y0, x1, y1 = bb
    inside_x = x0 - 1 <= x <= x1 + 1
    inside_y = y0 - 1 <= y <= y1 + 1
    return (inside_x and min(abs(y - y0), abs(y - y1)) < 1) or (
        inside_y and min(abs(x - x0), abs(x - x1)) < 1
    )


@pytest.mark.parametrize("provider", sorted(PEERINGS))
def test_peering_line_runs_from_border_to_border(tmp_path, provider):
    """neato ignores lhead/ltail, so the line ran from icon to icon straight
    through both boxes; it now joins the two boxes' facing borders."""
    _draw_dot(tmp_path, _peered(provider))
    [dot] = tmp_path.glob("graph*.dot")
    boxes, links = {}, []
    for line in _gvpr(tmp_path, _LINK_AND_BOXES, dot).splitlines():
        kind, *rest = line.split("|")
        if kind == "box":
            boxes[rest[0]] = tuple(float(v) for v in rest[1].split(","))
        else:
            links.append(rest)
    [(tail, head, pos, xlp)] = links
    points = dict(
        (p.split(",")[0], tuple(float(v) for v in p.split(",")[1:]))
        for p in pos.split()
        if p[:2] in ("s,", "e,")
    )
    assert _on_border(points["s"], boxes[tail])
    assert _on_border(points["e"], boxes[head])
    # the badge sits between the two boxes, not inside either
    badge = tuple(float(v) for v in xlp.split(","))
    low, high = sorted([points["s"][1], points["e"][1]])
    assert low <= badge[1] <= high


def test_peering_line_slides_off_a_box_label(tmp_path):
    """A peered VNet inside a resource group: the straight line down from it
    would cross the resource group's name at the bottom of its box."""
    from pathlib import Path

    layout = tmp_path / "layout.dot"
    layout.write_text(
        """digraph G {
  graph [bb="0,0,1400,1600"];
  subgraph cluster_rg { graph [bb="100,700,1300,1500"];
    subgraph cluster_vnet { graph [bb="200,800,1200,1400"];
      a [pos="600,1000", width=1, height=1]; }
  }
  subgraph cluster_down { graph [bb="100,100,1300,500"];
    b [pos="600,300", width=1, height=1]; }
  lbl [_clusterlabel="1", _clusterid="cluster_rg", _labelposition="bottom-left",
       pos="0,0", width="8", height="1"];
  a -> b [_grouplink="1", ltail="cluster_vnet", lhead="cluster_down"];
}"""
    )
    import subprocess

    script = Path(__file__).parents[1] / "shiftLabel.gvpr"
    shifted = subprocess.run(
        ["gvpr", "-c", "-q", "-f", str(script), str(layout)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    (tmp_path / "shifted.dot").write_text(shifted)
    out = _gvpr(
        tmp_path,
        'N[_clusterlabel=="1"]{ printf("label|%s|%s\\n", pos, width); }'
        ' E[_grouplink=="1"]{ printf("link|%s\\n", pos); }',
        tmp_path / "shifted.dot",
    )
    rows = dict(line.split("|", 1) for line in out.splitlines())
    label_x = float(rows["label"].split(",")[0])
    half_width = float(rows["label"].split("|")[1]) * 72 / 2
    line_x = float(rows["link"].split()[0].split(",")[1])
    assert not label_x - half_width <= line_x <= label_x + half_width
