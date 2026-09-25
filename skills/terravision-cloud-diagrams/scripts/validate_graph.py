#!/usr/bin/env python3
"""Validate a TerraVision graph JSON file against the TVG 1.0 rules.

Usage: python validate_graph.py architecture.tvg.json
Exits 1 with a list of errors when the graph cannot be drawn. Otherwise
exits 0, first printing warnings for things that will draw differently from
what was probably meant. No dependencies.
"""
import json
import re
import sys
from pathlib import Path

# Keep identical to the pattern in references/terravision-graph.schema.json
# and modules/mcp_service.py; a test compares all three.
ADDRESS = re.compile(
    r"^(module\.[A-Za-z0-9_-]+(\[[^\]]+\])?\.)*[a-z][a-z0-9_]*\.[A-Za-z0-9_-]+(\[[^\]]+\])*(~[0-9]+)?$"
)
MODULE_PATH = re.compile(r"^(module\.[A-Za-z0-9_-]+(\[[^\]]+\])?\.)+")

# Resource type prefix -> provider. Keep identical to TV_PROVIDER_PREFIXES and
# PROVIDER_PREFIXES in modules/provider_detector.py; a test compares them.
PROVIDER_PREFIXES = {
    "tv_aws_": "aws",
    "tv_azurerm_": "azure",
    "tv_azure_": "azure",
    "tv_gcp_": "gcp",
    "aws_": "aws",
    "azurerm_": "azure",
    "azuread_": "azure",
    "azurestack_": "azure",
    "azapi_": "azure",
    "google_": "gcp",
}
RESOURCE_PREFIX = {"aws": "aws_", "azure": "azurerm_", "gcp": "google_"}

# Drawing rules, copied from modules/config/cloud_config_<provider>.py so this
# script runs without TerraVision installed; a test keeps them identical.
# Types drawn as boxes around the nodes they list (<PROVIDER>_GROUP_NODES).
CONTAINER_TYPES = {
    "aws_vpc", "aws_az", "aws_group", "aws_account", "aws_appautoscaling_target",
    "aws_autoscaling_group", "aws_subnet", "aws_security_group", "tv_aws_onprem",
    "tv_aws_region",
    "azurerm_resource_group", "azurerm_group", "azurerm_virtual_network",
    "azurerm_subnet", "tv_azurerm_zone", "tv_azure_onprem",
    "tv_gcp_account", "google_project", "tv_gcp_users", "tv_gcp_system",
    "tv_gcp_infra_system2", "tv_gcp_onprem", "tv_gcp_external_saas",
    "tv_gcp_external_data", "tv_gcp_external_3p", "tv_gcp_external_1p",
    "tv_gcp_load_balancer", "google_compute_network", "tv_gcp_logical_group",
    "tv_gcp_region", "google_container_cluster", "google_compute_subnetwork",
    "tv_gcp_zone", "google_compute_firewall", "google_compute_instance_group",
    "tv_gcp_replica_pool", "google_container_node_pool", "tv_gcp_k8s_pod",
    "tv_gcp_optional",
}  # fmt: skip
# Arrows to or from these are not drawn (<PROVIDER>_SHARED_SERVICES) ...
SHARED_SERVICES = {
    "aws_acm_certificate", "aws_cloudwatch_log_group", "aws_ecr_repository",
    "aws_efs_file_system", "aws_ssm_parameter", "aws_kms_key", "aws_eip",
    "aws_secretsmanager",
    "azurerm_key_vault", "azurerm_monitor", "azurerm_log_analytics_workspace",
    "azurerm_container_registry", "azurerm_storage_account",
    "google_kms_key_ring", "google_logging_project_sink",
    "google_monitoring_dashboard", "google_container_registry",
    "google_secret_manager_secret",
}  # fmt: skip
# ... except arrows into them from these (<PROVIDER>_ALWAYS_DRAW_LINE).
ALWAYS_DRAW_LINE = {
    "aws_lb", "aws_iam_role", "aws_volume_attachment", "aws_alb", "aws_nlb",
    "aws_efs_access_point", "aws_efs_mount_target", "aws_ecs_service",
    "aws_rds_aurora", "aws_rds_mysql", "aws_rds_postgres",
    "azurerm_load_balancer", "azurerm_application_gateway",
    "azurerm_network_interface", "azurerm_virtual_machine_scale_set",
    "azurerm_kubernetes_cluster",
    "google_compute_forwarding_rule", "google_compute_backend_service",
    "google_container_node_pool", "google_compute_instance_group",
}  # fmt: skip
SHARED_GROUP = {
    "aws": "aws_group.shared_services",
    "azure": "azurerm_group.shared_services",
}
NODE_TYPES_FILE = (
    Path(__file__).resolve().parent.parent / "references" / "node-types.md"
)


def type_of(node):
    return MODULE_PATH.sub("", node).split(".")[0]


def name_of(node):
    name = MODULE_PATH.sub("", node).split(".", 1)[1]
    return re.sub(r"(\[[^\]]*\])+|~[0-9]+$", "", name)


def base_of(node):
    return re.sub(r"(\[[^\]]*\])*(~[0-9]+)?$", "", node)


def provider_of(node):
    resource_type = type_of(node)
    for prefix, provider in PROVIDER_PREFIXES.items():
        if resource_type.startswith(prefix):
            return provider
    return None


def known_types():
    try:
        return set(re.findall(r"`([a-z][a-z0-9_]*)`", NODE_TYPES_FILE.read_text()))
    except OSError:
        return None


def validate(graph):
    problems = []
    if not isinstance(graph, dict) or not graph:
        return ["Top level must be a non-empty JSON object."]
    for node, targets in graph.items():
        if not ADDRESS.match(node):
            problems.append(f"Bad node address: {node!r} (expected '<type>.<name>')")
        if not isinstance(targets, list):
            problems.append(f"{node!r}: value must be a list of node addresses")
            continue
        for t in targets:
            if not isinstance(t, str) or not ADDRESS.match(t):
                problems.append(f"{node!r}: bad target address {t!r}")
        if len(set(targets)) != len(targets):
            problems.append(f"{node!r}: duplicate targets")
    providers = {
        provider_of(node)
        for node in set(graph)
        | {t for v in graph.values() if isinstance(v, list) for t in v}
        if isinstance(node, str) and provider_of(node)
    }
    if len(providers) > 1:
        prefixes = [f"{RESOURCE_PREFIX[p]}*" for p in sorted(providers)]
        problems.append(
            f"Graph mixes {', '.join(prefixes[:-1])} and {prefixes[-1]} "
            "resources; use one cloud provider per graph."
        )
    return problems


def warnings(graph):
    """Things that draw, but not the way the author probably meant.

    Call only on a graph that validate() accepts.
    """
    found = []
    nodes = set(graph) | {t for v in graph.values() for t in v}
    edges = [
        (src, dst)
        for src, targets in graph.items()
        if type_of(src) not in CONTAINER_TYPES
        for dst in targets
    ]

    known = known_types()
    if known is not None:
        for resource_type in sorted({type_of(n) for n in nodes} - known):
            if provider_of(resource_type + ".x"):
                found.append(
                    f"Unknown type {resource_type!r} draws a blank icon; check "
                    "the spelling against references/node-types.md."
                )

    for src, dst in edges:
        if type_of(dst) in CONTAINER_TYPES:
            found.append(
                f"Arrow {src} -> {dst} is not drawn: {type_of(dst)} is a "
                "container. Point at a node inside it."
            )

    hidden = {}
    for src, dst in edges:
        if type_of(src) in SHARED_SERVICES:
            hidden.setdefault(src, []).append(dst)
        elif (
            type_of(dst) in SHARED_SERVICES
            and type_of(src) not in ALWAYS_DRAW_LINE
            and type_of(dst) not in CONTAINER_TYPES
        ):
            hidden.setdefault(dst, []).append(src)
    for shared, others in sorted(hidden.items()):
        group = SHARED_GROUP.get(provider_of(shared))
        if group and shared in graph.get(group, []):
            continue  # grouped on purpose, so hidden arrows are expected
        hint = (
            f" List it in {group} to draw it in the Shared Services box."
            if group
            else ""
        )
        found.append(
            f"Arrows between {shared} and {', '.join(sorted(others))} are not "
            f"drawn: {type_of(shared)} is a shared service.{hint}"
        )

    parents = {}
    for src, targets in graph.items():
        if type_of(src) in CONTAINER_TYPES:
            for t in targets:
                parents.setdefault(t, []).append(src)
    for node, boxes in sorted(parents.items()):
        if len(boxes) > 1:
            found.append(
                f"{node} is listed in {', '.join(boxes)} but is drawn in only "
                "one of them; use numbered copies (~1, ~2) for one per container."
            )

    numbered = {base_of(n) for n in nodes if re.search(r"~[0-9]+$", n)}
    for src, dst in edges:
        if dst in numbered:
            found.append(
                f"{src} points at {dst}, which has numbered copies; point at "
                f"{dst}~1, {dst}~2 ... or an extra node can appear."
            )

    pairs = {frozenset(e) for e in edges if (e[1], e[0]) in edges and e[0] != e[1]}
    for pair in sorted(sorted(p) for p in pairs):
        found.append(
            f"{pair[0]} and {pair[1]} point at each other; only one arrow is "
            "drawn. Keep the main direction of flow."
        )

    for node in sorted(nodes):
        if re.search(r"[A-Z-]", name_of(node)):
            found.append(
                f"{node}: use a lowercase snake_case name; hyphens and capitals "
                "are mangled in the label."
            )
    return found


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
    issues = validate(data)
    if issues:
        print("\n".join(issues))
        sys.exit(1)
    for warning in warnings(data):
        print(f"WARNING: {warning}")
    nodes = set(data) | {t for v in data.values() for t in v}
    print(f"OK: {len(nodes)} nodes, {sum(len(v) for v in data.values())} edges")
