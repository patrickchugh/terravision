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
