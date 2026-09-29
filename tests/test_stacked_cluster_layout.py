"""Boxes stacked in rows keep their size and do not overlap (issue #218).

Arrows between resources in different resource groups put the boxes in two
rows with a thin gap. Growing each box downwards for its bottom label made
the upper row hang over the lower one, and the overlap fix then cut boxes
narrower than their contents: a VNet stuck out of its resource group. The
lower row now moves down instead.
"""

import json
import subprocess

from click.testing import CliRunner

from terravision.terravision import cli

HUB_AND_SPOKES = {
    "azurerm_resource_group.hub": ["azurerm_virtual_network.hub"],
    "azurerm_virtual_network.hub": ["azurerm_subnet.firewall"],
    "azurerm_subnet.firewall": ["azurerm_firewall.hub"],
    "azurerm_resource_group.spoke_a": ["azurerm_virtual_network.spoke_a"],
    "azurerm_virtual_network.spoke_a": ["azurerm_subnet.app_a"],
    "azurerm_subnet.app_a": ["azurerm_linux_virtual_machine.app_a"],
    "azurerm_resource_group.spoke_b": ["azurerm_virtual_network.spoke_b"],
    "azurerm_virtual_network.spoke_b": ["azurerm_subnet.app_b"],
    "azurerm_subnet.app_b": ["azurerm_linux_virtual_machine.app_b"],
    "azurerm_linux_virtual_machine.app_a": ["azurerm_firewall.hub"],
    "azurerm_linux_virtual_machine.app_b": ["azurerm_firewall.hub"],
}

# Every cluster's name, its parent cluster's name and its bounding box
_BOXES = r"""
BEG_G {
  graph_t a, b, c, d;
  for (a = fstsubg($G); a; a = nxtsubg(a)) {
    printf("%s|-|%s\n", a.name, a.bb);
    for (b = fstsubg(a); b; b = nxtsubg(b)) {
      printf("%s|%s|%s\n", b.name, a.name, b.bb);
      for (c = fstsubg(b); c; c = nxtsubg(c)) {
        printf("%s|%s|%s\n", c.name, b.name, c.bb);
        for (d = fstsubg(c); d; d = nxtsubg(d))
          printf("%s|%s|%s\n", d.name, c.name, d.bb);
      }
    }
  }
}
"""


def _boxes(tmp_path, graph=HUB_AND_SPOKES):
    source = tmp_path / "hub.tvg.json"
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
            str(tmp_path / "hub"),
        ],
    )
    assert result.exit_code == 0, result.output
    [dot] = tmp_path.glob("hub*.dot")
    script = tmp_path / "boxes.gvpr"
    script.write_text(_BOXES)
    out = subprocess.run(
        ["gvpr", "-f", str(script), str(dot)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    boxes = {}
    for line in out.splitlines():
        name, parent, bb = line.split("|")
        boxes[name] = (parent, tuple(float(v) for v in bb.split(",")))
    return boxes


def _inside(inner, outer):
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


TWO_SUBNET_HUB = dict(
    HUB_AND_SPOKES,
    **{
        "azurerm_virtual_network.hub": [
            "azurerm_subnet.firewall",
            "azurerm_subnet.management",
        ],
        "azurerm_subnet.management": ["azurerm_linux_virtual_machine.jumpbox"],
    },
)


def test_each_box_contains_the_boxes_inside_it(tmp_path):
    boxes = _boxes(tmp_path)
    nested = [(n, p) for n, (p, _) in boxes.items() if p != "-"]
    assert any("VNetGroup" in n for n, _ in nested)
    for name, parent in nested:
        assert _inside(boxes[name][1], boxes[parent][1]), f"{name} outside {parent}"


def test_resource_groups_do_not_overlap(tmp_path):
    boxes = _boxes(tmp_path)
    groups = [bb for n, (_, bb) in boxes.items() if "ResourceGroupCluster" in n]
    assert len(groups) == 3
    for i, a in enumerate(groups):
        for b in groups[i + 1 :]:
            assert not _overlap(a, b)


_LOGO_AND_FOOTER = r"""
N[_footernode=="1"] { printf("footer|%s|%s\n", pos, height); }
N[_clusterlabel=="1" && match(_clusterid, "AZUREGroup") >= 0] {
  printf("logo|%s|%s\n", pos, height);
}
"""


def test_the_provider_logo_stays_clear_of_the_footer(tmp_path):
    """The Azure logo hangs from the cloud box's bottom edge, so it moves
    down with the rows; the footer has to move with it."""
    _boxes(tmp_path)  # draws hub*.dot
    [dot] = tmp_path.glob("hub*.dot")
    script = tmp_path / "logo.gvpr"
    script.write_text(_LOGO_AND_FOOTER)
    out = subprocess.run(
        ["gvpr", "-f", str(script), str(dot)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    found = {}
    for line in out.splitlines():
        kind, pos, height = line.split("|")
        y = float(pos.rstrip("!").split(",")[1])
        half = float(height) * 72 / 2
        found[kind] = (y - half, y + half)  # (bottom, top); y grows upwards
    logo_bottom, _ = found["logo"]
    _, footer_top = found["footer"]
    assert footer_top < logo_bottom


def test_a_moved_box_takes_all_its_inner_boxes(tmp_path):
    """gvpr shares a function's local variables between recursive calls, so
    moving a box with two inner boxes moved only the first of them."""
    boxes = _boxes(tmp_path, TWO_SUBNET_HUB)
    subnets = [n for n in boxes if "SubnetGroup" in n]
    assert len(subnets) == 4
    for name, (parent, bb) in boxes.items():
        if parent != "-":
            assert _inside(bb, boxes[parent][1]), f"{name} outside {parent}"
