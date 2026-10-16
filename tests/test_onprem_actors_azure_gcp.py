"""Servers, databases, workstations and devices outside Azure and Google Cloud.

The tv_azurerm_* and tv_gcp_* on-site actors let a hybrid graph show what sits
in a tv_azure_onprem or tv_gcp_onprem data centre, outside the cloud frame.
Neither icon set has a plain server or workstation, so they use the neutral
generic icons.
"""

import pytest

from modules.config import cloud_config_azure, cloud_config_gcp
from resource_classes.azure import general
from resource_classes.gcp import generic

ACTORS = [
    (general, cloud_config_azure.AZURE_OUTER_NODES, "tv_azurerm_server", "rack.png"),
    (general, cloud_config_azure.AZURE_OUTER_NODES, "tv_azurerm_database", "sql.png"),
    (general, cloud_config_azure.AZURE_OUTER_NODES, "tv_azurerm_client", "client.png"),
    (
        general,
        cloud_config_azure.AZURE_OUTER_NODES,
        "tv_azurerm_iot_device",
        "iot-edge.png",
    ),
    (generic, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_server", "rack.png"),
    (generic, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_database", "sql.png"),
    (generic, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_client", "client.png"),
    (generic, cloud_config_gcp.GCP_OUTER_NODES, "tv_gcp_iot_device", "iot-sensor.png"),
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


def test_gcp_onprem_box_is_drawn_outside_the_google_cloud_frame():
    """It drew inside the blue Google Cloud frame, as if it were part of it."""
    assert "tv_gcp_onprem" in cloud_config_gcp.GCP_OUTER_NODES
