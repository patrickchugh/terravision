#!/usr/bin/env python3
"""Regenerate the published node-type list, and llms-full.txt from its sources.

Every top-level ``<type> = <Class>`` assignment in resource_classes/ whose name
starts with aws_, azurerm_, google_ or tv_ is a node type TerraVision can draw.
Run this after adding resource classes so the published list cannot drift:

    poetry run python scripts/gen_node_types.py

Writes docs/node-types.md, the skill's copy of it, and docs/llms-full.txt:
its node-types section from the same list, and its Graph Format section copied
from docs/graph-format.md (tests/test_skill.py checks the copies match).
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

Every key or value in a TerraVision graph is `<type>.<name>`. The `<type>` selects the icon; anything not listed still renders with a generic icon for its provider. Container types draw their connected nodes inside themselves; the Graph Format rules list them all, including less obvious ones such as `aws_autoscaling_group` and `google_container_cluster`.

Numbered copies: append `~1`, `~2` (for example one node per availability zone). Module grouping: prefix with `module.<name>.`.
"""
TARGETS = [
    ROOT / "docs" / "node-types.md",
    ROOT / "skills" / "terravision-cloud-diagrams" / "references" / "node-types.md",
]
LLMS_FULL = ROOT / "docs" / "llms-full.txt"
GRAPH_FORMAT = ROOT / "docs" / "graph-format.md"


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
    head = sync_graph_format(head)
    LLMS_FULL.write_text(head + doc)
    print(f"wrote {LLMS_FULL.relative_to(ROOT)}")


def sync_graph_format(text: str) -> str:
    """Replace the Graph Format section of *text* with docs/graph-format.md.

    The section runs from its heading to the next ``---`` separator.
    """
    heading = "# TerraVision Graph Format (TVG)"
    start = text.find(heading)
    end = text.find("\n---\n", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{LLMS_FULL}: Graph Format section not found")
    source = (GRAPH_FORMAT.read_text()).strip()
    return text[:start] + source + "\n" + text[end:]


if __name__ == "__main__":
    main()
