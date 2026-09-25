#!/usr/bin/env python3
"""Regenerate the published node-type list from resource_classes/.

Every top-level ``<type> = <Class>`` assignment in resource_classes/ whose name
starts with aws_, azurerm_, google_ or tv_ is a node type TerraVision can draw.
Run this after adding resource classes so the published list cannot drift:

    poetry run python scripts/gen_node_types.py

Writes docs/node-types.md, the skill's copy of it, and the node-types section
of docs/llms-full.txt.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = re.compile(r"^([a-z][a-z0-9_]*)\s*=", re.M)
SECTIONS = [
    ("AWS (aws_*)", "aws_"),
    ("Azure (azurerm_*)", "azurerm_"),
    ("GCP (google_*)", "google_"),
    ("Pseudo-nodes (tv_*) for external actors and containers", "tv_"),
]
HEADER = """# TerraVision node types

Every key or value in a TerraVision graph is `<type>.<name>`. The `<type>` selects the icon; anything not listed still renders with a generic icon for its provider. Container types (VPC, subnet, resource group, network, region, zone) draw their connected nodes inside themselves.

Numbered copies: append `~1`, `~2` (for example one node per availability zone). Module grouping: prefix with `module.<name>.`.
"""
TARGETS = [
    ROOT / "docs" / "node-types.md",
    ROOT / "skills" / "terravision-cloud-diagrams" / "references" / "node-types.md",
]
LLMS_FULL = ROOT / "docs" / "llms-full.txt"


def collect() -> set:
    names = set()
    for py in (ROOT / "resource_classes").rglob("*.py"):
        names.update(ASSIGNMENT.findall(py.read_text()))
    return names


def render(names: set) -> str:
    out = [HEADER]
    for title, prefix in SECTIONS:
        types = sorted(n for n in names if n.startswith(prefix))
        out.append(f"\n## {title} ({len(types)})\n\n")
        out.append(", ".join(f"`{t}`" for t in types) + "\n")
    return "".join(out)


def main() -> None:
    doc = render(collect())
    for target in TARGETS:
        target.write_text(doc)
        print(f"wrote {target.relative_to(ROOT)}")
    llms = LLMS_FULL.read_text()
    marker = "# TerraVision node types"
    head, sep, _ = llms.partition(marker)
    if not sep:
        raise SystemExit(f"{LLMS_FULL}: node-types section marker not found")
    LLMS_FULL.write_text(head + doc)
    print(f"wrote {LLMS_FULL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
