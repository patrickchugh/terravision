"""Servers, databases and workstations outside AWS draw with the AWS General icons.

tv_aws_server, tv_aws_database and tv_aws_client let a graph show an
on-premises system or workstation inside a tv_aws_onprem data centre,
outside the AWS Cloud frame.
"""

import pytest

from modules.config import cloud_config_aws
from resource_classes.aws import icons


@pytest.mark.parametrize(
    "node_type, icon",
    [
        ("tv_aws_server", "traditional-server.png"),
        ("tv_aws_database", "generic-database.png"),
        ("tv_aws_client", "client.png"),
        ("tv_aws_iot_sensor", "iot-sensor.png"),
    ],
)
def test_onprem_actor_uses_the_aws_general_icon(node_type, icon):
    assert getattr(icons, node_type)._icon == icon


@pytest.mark.parametrize(
    "node_type",
    ["tv_aws_server", "tv_aws_database", "tv_aws_client", "tv_aws_iot_sensor"],
)
def test_onprem_actor_is_drawn_outside_the_cloud(node_type):
    assert node_type in cloud_config_aws.AWS_OUTER_NODES
