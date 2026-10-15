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


# ---- Resources with a network interface in each subnet ----


def boxes_holding(graph, node):
    return [
        box
        for box, children in graph.items()
        if node in children and box.startswith("aws_subnet.")
    ]


@pytest.mark.parametrize(
    "resource",
    [
        "aws_networkfirewall_firewall.inspection",
        "aws_ec2_transit_gateway_vpc_attachment.inspection",
        "aws_ec2_transit_gateway_vpc_attachment.egress",
        "aws_directory_service_directory.corporate_ad",
    ],
)
def test_resource_spanning_subnets_has_a_copy_in_each(graph, resource):
    """subnet_ids = aws_subnet.x[*].id names two subnets, not one."""
    copies = [f"{resource}~1", f"{resource}~2"]
    for copy in copies:
        assert len(boxes_holding(graph, copy)) == 1, copy
    assert boxes_holding(graph, copies[0]) != boxes_holding(graph, copies[1])
    assert resource not in graph


@pytest.mark.parametrize(
    "resource",
    [
        "aws_ec2_transit_gateway_vpc_attachment.production",
        "aws_ec2_transit_gateway_vpc_attachment.development",
        "aws_ec2_transit_gateway_vpc_attachment.shared_services",
    ],
)
def test_resource_in_one_subnet_stays_one_node(graph, resource):
    """Numbering one attachment must not number every attachment."""
    assert resource in graph
    assert f"{resource}~1" not in graph


def test_splat_counts_the_instances_it_refers_to():
    from modules.graphmaker import _count_references

    graph = {"aws_subnet.a[0]~1": [], "aws_subnet.a[1]~2": [], "aws_subnet.b": []}
    pattern = r"\$\{(aws_subnet\.\w+)"
    assert _count_references("${aws_subnet.a[*].id}", pattern, graph) == 2
    assert _count_references(["${aws_subnet.b.id}"], pattern, graph) == 1
    assert (
        _count_references(
            {"subnet_ids": "${aws_subnet.a[*].id}", "vpc_id": "${aws_vpc.v.id}"},
            pattern,
            graph,
        )
        == 2
    )


# ---- Plumbing with no icon is not drawn ----


def test_routing_and_firewall_rules_are_not_drawn(tmp_path):
    """Transit Gateway route tables and routes, and Network Firewall's policy
    and rule groups, drew as blank boxes; like aws_route_table they are
    hidden."""
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", str(FIXTURE),
         "--planfile", str(FIXTURE / "plan.json"),
         "--graphfile", str(FIXTURE / "graph.dot"),
         "--format", "dot", "--outfile", str(tmp_path / "out")],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "no icon for" not in result.output
    [dot] = list(tmp_path.glob("out*.dot"))
    text = dot.read_text()
    for hidden in (
        "aws_ec2_transit_gateway_route",
        "aws_networkfirewall_firewall_policy",
        "aws_networkfirewall_rule_group",
    ):
        assert f'tf_resource_name="{hidden}.' not in text
    assert 'tf_resource_name="aws_networkfirewall_firewall.inspection~1"' in text
