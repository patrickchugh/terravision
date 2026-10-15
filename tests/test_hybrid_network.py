"""A hybrid network drawn from Terraform keeps its on-premises side.

The fixture connects a corporate data centre to a Transit Gateway over Direct
Connect (connection, transit VIF, Direct Connect gateway and its association)
and a site-to-site VPN. Every aws_dx* resource used to merge into one node
pointing at the Transit Gateway, with an empty data centre box and a
customer gateway placeholder that had no icon, while the real customer
gateway was drawn inside the AWS Cloud.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from modules import resource_transformers
from terravision.terravision import cli

FIXTURE = Path(__file__).parent / "fixtures" / "aws_terraform" / "hybrid_network"
ONPREM = "tv_aws_onprem.corporate_datacenter"
ROUTER = "aws_customer_gateway.datacentre_router"
DX = "aws_dx_connection.directconnect"
DXGW = "aws_dx_gateway.directconnect"
TGW = "aws_ec2_transit_gateway.hub"


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    out = tmp_path_factory.mktemp("hybrid") / "graph.tvg.json"
    result = CliRunner().invoke(
        cli,
        ["graphdata", "--source", str(FIXTURE),
         "--planfile", str(FIXTURE / "plan.json"),
         "--graphfile", str(FIXTURE / "graph.dot"),
         "--outfile", str(out)],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return json.loads(out.read_text())


def linked(graph, a, b):
    return b in graph.get(a, []) or a in graph.get(b, [])


def test_customer_gateway_is_in_the_data_centre(graph):
    assert graph[ONPREM] == [ROUTER]


def test_direct_connect_runs_from_the_router_to_the_transit_gateway(graph):
    assert linked(graph, ROUTER, DX)
    assert linked(graph, DX, DXGW)
    assert linked(graph, DXGW, TGW)
    # the association is the gateway's arrow, not a route from the connection
    assert not linked(graph, DX, TGW)


def test_vpn_stays_the_backup_path(graph):
    assert linked(graph, ROUTER, "aws_vpn_connection.ipsec_vpn")
    assert linked(graph, "aws_vpn_connection.ipsec_vpn", TGW)


def test_no_placeholder_nodes(graph):
    nodes = set(graph) | {t for targets in graph.values() for t in targets}
    assert not [n for n in nodes if n.startswith("tv_aws_cgw")]


def test_direct_connect_without_a_customer_gateway_gets_one():
    """Direct Connect needs no aws_customer_gateway in Terraform; the router
    it starts from is still drawn, in the data centre."""
    from modules import annotations

    tfdata = {
        "graphdict": {DX: [DXGW], DXGW: [TGW], TGW: []},
        "meta_data": {DX: {}, DXGW: {}, TGW: {}},
        "provider_detection": {"primary_provider": "aws", "providers": ["aws"]},
    }
    tfdata = annotations.add_annotations(tfdata)
    assert DX in tfdata["graphdict"]["aws_customer_gateway.this"]
    tfdata = resource_transformers.move_into_group(
        tfdata, "aws_customer_gateway", ONPREM
    )
    assert tfdata["graphdict"][ONPREM] == ["aws_customer_gateway.this"]


def test_move_into_group_takes_the_node_out_of_other_boxes():
    tfdata = {
        "graphdict": {
            "aws_vpc.main": [ROUTER, "aws_subnet.a"],
            "aws_subnet.a": [],
            ROUTER: [DX],
            DX: [],
        },
        "meta_data": {},
        "provider_detection": {"primary_provider": "aws", "providers": ["aws"]},
    }
    tfdata = resource_transformers.move_into_group(
        tfdata, "aws_customer_gateway", ONPREM
    )
    assert tfdata["graphdict"][ONPREM] == [ROUTER]
    assert ROUTER not in tfdata["graphdict"]["aws_vpc.main"]
    # connections are not containers and keep their arrows
    assert tfdata["graphdict"][ROUTER] == [DX]
