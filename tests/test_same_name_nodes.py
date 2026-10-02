"""A container and the node inside it may share a name.

Reported from a gallery diagram: "azurerm_subnet.ingress" holding
"azurerm_application_gateway.ingress" drew the gateway outside the subnet,
and renaming the subnet fixed it. Node identity is the whole address (type
and name), so nodes of different types that share a name must stay distinct
on every provider: renaming the container must not move its child.
"""

import json
import re

import pytest
from test_group_nesting import _draw_dot


def _cluster_depth(dot: str, address: str) -> int:
    """How many clusters enclose the node drawn for ``address``."""
    stack = []
    depth_at_node = None
    for line in dot.splitlines():
        stripped = line.strip()
        if stripped.startswith("subgraph") and stripped.endswith("{"):
            stack.append("cluster" in stripped)
        elif stripped == "}":
            if stack:
                stack.pop()
        elif stripped.startswith(f'tf_resource_name="{address}"'):
            depth_at_node = sum(stack)
    assert depth_at_node is not None, f"{address} was not drawn"
    return depth_at_node


def _renamed(graph, old: str, new: str):
    text = re.sub(rf"\b{re.escape(old)}\b", new, json.dumps(graph))
    return json.loads(text)


CASES = [
    pytest.param(
        {
            "tv_azurerm_users.users": ["azurerm_application_gateway.ingress"],
            "azurerm_resource_group.main": [
                "azurerm_virtual_network.main",
                "azurerm_public_ip.ingress",
            ],
            "azurerm_virtual_network.main": ["azurerm_subnet.ingress"],
            "azurerm_subnet.ingress": ["azurerm_application_gateway.ingress"],
            "azurerm_public_ip.ingress": ["azurerm_application_gateway.ingress"],
        },
        "azurerm_subnet.ingress",
        "azurerm_application_gateway.ingress",
        id="azure",
    ),
    pytest.param(
        {
            "aws_vpc.web": ["aws_subnet.web~1"],
            "aws_subnet.web~1": ["aws_alb.web~1"],
            "aws_alb.web~1": ["aws_s3_bucket.web"],
        },
        "aws_subnet.web",
        "aws_alb.web~1",
        id="aws",
    ),
    pytest.param(
        {
            "google_compute_network.web": ["google_compute_subnetwork.web"],
            "google_compute_subnetwork.web": ["google_compute_instance.web"],
            "google_compute_instance.web": ["google_sql_database_instance.web"],
        },
        "google_compute_subnetwork.web",
        "google_compute_instance.web",
        id="gcp",
    ),
]


@pytest.mark.parametrize("graph, container, child", CASES)
def test_sharing_the_containers_name_does_not_move_the_child(
    graph, container, child, tmp_path, monkeypatch
):
    (tmp_path / "same").mkdir()
    (tmp_path / "other").mkdir()
    same_name = _cluster_depth(_draw_dot(graph, tmp_path / "same", monkeypatch), child)
    other = container.split(".")[0] + ".renamed"
    different_name = _cluster_depth(
        _draw_dot(_renamed(graph, container, other), tmp_path / "other", monkeypatch),
        child,
    )
    assert same_name == different_name
    # cloud box (where drawn), network and subnet at least
    assert same_name >= 2
