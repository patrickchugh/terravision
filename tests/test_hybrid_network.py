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


def test_export_has_no_redundant_outer_container_listings(graph):
    from tests.test_skill import _validator

    warnings = _validator().warnings(graph)
    assert not [w for w in warnings if "which already contains" in w]
    for node, box in (
        (
            "aws_ec2_transit_gateway_vpc_attachment.production",
            "aws_subnet.production_tgw",
        ),
        ("aws_networkfirewall_firewall.inspection~1", "aws_subnet.firewall[0]~1"),
        (
            "aws_directory_service_directory.corporate_ad~1",
            "aws_subnet.shared_endpoints[0]~1",
        ),
    ):
        assert node in graph[box]


def test_export_matches_mcp_graph_and_companion_file(graph, tmp_path):
    from modules.mcp_service import _write_graph, run_architecture_graph

    result = run_architecture_graph(
        source=str(FIXTURE),
        planfile=str(FIXTURE / "plan.json"),
        graphfile=str(FIXTURE / "graph.dot"),
    )
    assert result["graphdict"] == graph
    assert result["node_count"] == len(graph)
    assert result["edge_count"] == sum(map(len, graph.values()))

    from terravision.terravision import compile_tfdata

    data = compile_tfdata(
        source=str(FIXTURE),
        varfile=[],
        workspace="default",
        debug=False,
        planfile=str(FIXTURE / "plan.json"),
        graphfile=str(FIXTURE / "graph.dot"),
    )
    path = _write_graph(data, tmp_path, "companion", str(FIXTURE))
    assert json.loads(path.read_text()) == graph


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


# ---- VPC endpoints ----


def test_interface_endpoint_is_in_each_of_its_subnets(graph):
    """It was moved to the first VPC in the graph (here the development VPC)."""
    for copy in ("aws_vpc_endpoint.ssm~1", "aws_vpc_endpoint.ssm~2"):
        assert len(boxes_holding(graph, copy)) == 1
    assert all("aws_vpc_endpoint" not in c for c in graph["aws_vpc.development"])


def test_gateway_endpoint_is_in_its_vpc_not_a_subnet():
    """A gateway endpoint (S3, DynamoDB) has no subnet; with resolved ids it
    was given an interface endpoint's subnets."""
    from modules.resource_handlers_aws import place_gateway_endpoints

    gw, vpc = "aws_vpc_endpoint.s3", "aws_vpc.main"
    tfdata = {
        "graphdict": {vpc: ["aws_subnet.a"], "aws_subnet.a": [gw], gw: []},
        "meta_data": {
            gw: {"vpc_endpoint_type": "Gateway", "vpc_id": "vpc-1"},
            vpc: {"id": "vpc-1"},
        },
    }
    place_gateway_endpoints(tfdata)
    assert gw not in tfdata["graphdict"]["aws_subnet.a"]
    assert gw in tfdata["graphdict"][vpc]


# ---- Databases ----


def _db_tfdata(multi_az):
    subnets = ["aws_subnet.data[0]~1", "aws_subnet.data[1]~2"]
    return {
        "graphdict": {
            "aws_vpc.main": ["aws_az.a", "aws_az.b"],
            "aws_az.a": [subnets[0]],
            "aws_az.b": [subnets[1]],
            subnets[0]: [],
            subnets[1]: [],
            "aws_db_subnet_group.db": ["aws_rds_postgres.db"],
            "aws_ecs_fargate.app": ["aws_rds_postgres.db"],
            "aws_rds_postgres.db": [],
        },
        "meta_data": {
            "aws_db_subnet_group.db": {"subnet_ids": "${aws_subnet.data[*].id}"},
            "aws_rds_postgres.db": {
                "db_subnet_group_name": "${aws_db_subnet_group.db.name}",
                "multi_az": multi_az,
            },
        },
        "original_metadata": {"aws_db_subnet_group.db": {"subnet_ids": True}},
    }


def test_single_az_database_is_in_its_vpc(graph):
    """It was drawn outside every VPC; which subnet it runs in is not known."""
    assert "aws_rds_postgres.orders" in graph["aws_vpc.production"]


def test_multi_az_database_has_a_copy_in_each_subnet_of_its_group():
    from modules.resource_handlers_aws import place_databases

    tfdata = place_databases(_db_tfdata(multi_az=True))
    g = tfdata["graphdict"]
    assert g["aws_subnet.data[0]~1"] == ["aws_rds_postgres.db~1"]
    assert g["aws_subnet.data[1]~2"] == ["aws_rds_postgres.db~2"]
    assert "aws_rds_postgres.db" not in g
    # arrows to the database now point at both copies
    assert g["aws_ecs_fargate.app"] == [
        "aws_rds_postgres.db~1",
        "aws_rds_postgres.db~2",
    ]


def test_single_az_database_from_references_is_in_the_vpc():
    from modules.resource_handlers_aws import place_databases

    tfdata = place_databases(_db_tfdata(multi_az=False))
    assert "aws_rds_postgres.db" in tfdata["graphdict"]["aws_vpc.main"]
