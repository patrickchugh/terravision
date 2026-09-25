#!/usr/bin/env python3
"""Validate a TerraVision graph JSON file against the TVG 1.0 rules.

Usage: python validate_graph.py architecture.tvg.json
Exits 0 when valid, 1 with a list of problems otherwise. No dependencies.
"""
import json
import re
import sys

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


def provider_of(node):
    resource_type = MODULE_PATH.sub("", node).split(".")[0]
    for prefix, provider in PROVIDER_PREFIXES.items():
        if resource_type.startswith(prefix):
            return provider
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
    nodes = set(data) | {t for v in data.values() for t in v}
    print(f"OK: {len(nodes)} nodes, {sum(len(v) for v in data.values())} edges")
