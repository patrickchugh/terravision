"""Servers, databases, workstations and devices outside Azure and Google Cloud.

The tv_azurerm_* and tv_gcp_* on-site actors let a hybrid graph show what sits
in a tv_azure_onprem or tv_gcp_onprem data centre, outside the cloud frame.
Neither icon set has a plain server or workstation, so they use the neutral
generic icons.
"""

import pytest

from modules.config import cloud_config_azure, cloud_config_gcp
from resource_classes.azure import icons as azure_icons
from resource_classes.gcp import icons as gcp_icons

ACTORS = [
    (
        azure_icons,
        cloud_config_azure.AZURE_OUTER_NODES,
        "tv_azurerm_server",
        "rack.png",
    ),
    (
        azure_icons,
        cloud_config_azure.AZURE_OUTER_NODES,
        "tv_azurerm_database",
        "sql.png",
    ),
    (
        azure_icons,
        cloud_config_azure.AZURE_OUTER_NODES,
        "tv_azurerm_client",
        "client.png",
    ),
    (
        azure_icons,
        cloud_config_azure.AZURE_OUTER_NODES,
        "tv_azurerm_iot_device",
        "iot-edge.png",
    ),
    (gcp_icons, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_server", "rack.png"),
    (gcp_icons, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_database", "sql.png"),
    (gcp_icons, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_client", "client.png"),
    (
        gcp_icons,
        cloud_config_gcp.GCP_OUTER_NODES,
        "tv_gcp_iot_device",
        "iot-sensor.png",
    ),
]


@pytest.mark.parametrize(
    "module, outer, node_type, icon", ACTORS, ids=[a[2] for a in ACTORS]
)
def test_onprem_actor_icon_exists(module, outer, node_type, icon):
    from pathlib import Path

    cls = getattr(module, node_type)
    assert cls._icon == icon
    root = Path(__file__).resolve().parents[1]
    assert (root / cls._icon_dir / icon).is_file()


@pytest.mark.parametrize(
    "module, outer, node_type, icon", ACTORS, ids=[a[2] for a in ACTORS]
)
def test_onprem_actor_is_drawn_outside_the_cloud(module, outer, node_type, icon):
    assert node_type in outer


@pytest.mark.parametrize(
    "box",
    [
        "tv_gcp_onprem",
        "tv_gcp_external_saas",
        "tv_gcp_external_data",
        "tv_gcp_external_3p",
        "tv_gcp_external_1p",
    ],
)
def test_gcp_outside_box_is_drawn_outside_the_google_cloud_frame(box):
    """They drew inside the blue Google Cloud frame, as if part of it."""
    assert box in cloud_config_gcp.GCP_OUTER_NODES
