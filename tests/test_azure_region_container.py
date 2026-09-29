"""tv_azurerm_region: the Azure counterpart of tv_aws_region and tv_gcp_region.

Multi-region Azure designs (hubs in several regions, ExpressRoute or VPN into
more than one of them) had no way to draw a region boundary: a resource group
is not regional, and a VNet with nothing declared inside it is not drawn.
"""

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config import cloud_config_azure  # noqa: E402

GRAPH = {
    "tv_azurerm_region.belgium_central": [
        "azurerm_virtual_hub.hub_bec",
        "azurerm_subscription.landing_zones_bec",
    ],
    "tv_azurerm_region.france_central": ["azurerm_subscription.landing_zones_frc"],
    "azurerm_virtual_hub.hub_bec": [
        "azurerm_subscription.landing_zones_bec",
        "azurerm_subscription.landing_zones_frc",
    ],
}


def test_region_maps_to_region_group():
    from resource_classes.azure.groups import RegionGroup, tv_azurerm_region

    assert tv_azurerm_region is RegionGroup


def test_region_label_icon_exists_and_matches_the_other_group_icons(tmp_path):
    from resource_classes import Canvas, setdiagram
    from resource_classes.azure.groups import RegionGroup

    diagram = Canvas("test", str(tmp_path / "out"), outformat="png", show=False)
    setdiagram(diagram)
    try:
        region = RegionGroup(label="West Europe")
    finally:
        setdiagram(None)
    assert region.dot.graph_attr["style"] == "solid"
    assert Path(region.label_icon).is_file()
    # Drawn at the size of the resource group and VNet label icons (120x120),
    # not at the source's 256x256, which overflowed the box border.
    assert (region.label_icon_width, region.label_icon_height) == (120, 120)
    assert region.label_text == "West Europe"


def test_region_is_a_group_node_and_the_outermost_one():
    assert "tv_azurerm_region" in cloud_config_azure.AZURE_GROUP_NODES
    assert cloud_config_azure.AZURE_GROUP_NODES[0] == "tv_azurerm_region"


def test_simplified_mode_removes_region_boxes_like_other_containers():
    assert "tv_azurerm_region" in cloud_config_azure.AZURE_SIMPLIFIED_REMOVE_NODES


def test_skill_validator_treats_region_as_a_container():
    skill_scripts = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "terravision-cloud-diagrams"
        / "scripts"
    )
    sys.path.insert(0, str(skill_scripts))
    import validate_graph

    assert "tv_azurerm_region" in validate_graph.CONTAINER_TYPES


@pytest.mark.slow
def test_regions_render_as_labelled_boxes(tmp_path):
    from modules import mcp_service

    saved_dir, saved_rendered = mcp_service._OUTPUT_DIR, set(mcp_service._RENDERED)
    mcp_service._RENDERED.clear()
    mcp_service.set_output_dir(str(tmp_path))
    try:
        result = mcp_service.run_render_graph(
            GRAPH, outfile="regions", title="Regions", preview=False
        )
    finally:
        mcp_service._OUTPUT_DIR = saved_dir
        mcp_service._RENDERED.clear()
        mcp_service._RENDERED.update(saved_rendered)
    svg = Path(result["files"]["svg"]).read_text(encoding="utf-8")
    # Each region is drawn as a box (a Graphviz cluster), not as a node. An
    # unknown type would still draw its label as a generic node, so counting
    # labels proves nothing; the cluster is what only a container produces.
    regions = re.findall(r"<title>cluster_RegionGroup\.\d+</title>", svg)
    assert len(regions) == 2
    assert svg.count(">Belgium Central<") == 1
    assert svg.count(">France Central<") == 1
