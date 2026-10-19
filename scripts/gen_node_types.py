#!/usr/bin/env python3
"""Regenerate the published node-type list, and llms-full.txt from its sources.

Every type in resource_classes/<cloud>/terraform_icons.yml, and every top-level
``<type> = <Class>`` assignment in resource_classes/ (the container types in
groups.py), whose name starts with aws_, azurerm_, azuread_, google_ or tv_ is a node
type TerraVision can draw. Run this after adding types so the published list
cannot drift:

    poetry run python scripts/gen_node_types.py

Writes docs/node-types.md, the skill's copy of it, and docs/llms-full.txt:
its node-types section from the same list, and its Graph Format section copied
from docs/graph-format.md (tests/test_skill.py checks the copies match). Also
updates the per-cloud counts in the Supported Cloud Providers table of the
README, docs/index.md and docs/faq.md (tests/test_type_counts.py checks them).
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = re.compile(r"^([a-z][a-z0-9_]*)\s*=", re.M)
SECTIONS = [
    ("AWS (aws_*)", "aws_"),
    ("Azure (azurerm_*)", "azurerm_"),
    ("Microsoft Entra ID (azuread_*)", "azuread_"),
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
# Pages whose Supported Cloud Providers table quotes how many types each cloud has
COUNT_PAGES = [ROOT / "README.md", ROOT / "docs" / "index.md", ROOT / "docs" / "faq.md"]
# Entra ID (azuread_*) types are drawn in Azure diagrams, so Azure counts them
COUNT_PREFIXES = {
    "AWS": ("aws_",),
    "Google Cloud": ("google_",),
    "Azure": ("azurerm_", "azuread_"),
}
COUNT_ROW = re.compile(
    r"^(\| \*\*(AWS|Google Cloud|Azure)\*\* +\|[^|]+\| )(\d+)( types)", re.M
)
GRAPH_FORMAT = ROOT / "docs" / "graph-format.md"


def collect() -> set:
    names = set()
    for py in (ROOT / "resource_classes").rglob("*.py"):
        names.update(ASSIGNMENT.findall(py.read_text()))
    for mapping in (ROOT / "resource_classes").rglob("terraform_icons.yml"):
        names.update(yaml.safe_load(mapping.read_text()) or {})
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
    counts = type_counts(collect())
    for page in COUNT_PAGES:
        page.write_text(sync_counts(page.read_text(), counts, page))
        print(f"updated type counts in {page.relative_to(ROOT)}")


def type_counts(names: set) -> dict:
    """How many types each cloud row of the Supported Cloud Providers table has."""
    return {
        cloud: sum(1 for n in names if n.startswith(prefixes))
        for cloud, prefixes in COUNT_PREFIXES.items()
    }


def sync_counts(text: str, counts: dict, page: Path) -> str:
    """Put *counts* into the Supported Cloud Providers table rows of *text*."""
    new, found = COUNT_ROW.subn(lambda m: f"{m[1]}{counts[m[2]]}{m[4]}", text)
    if found != len(COUNT_PREFIXES):
        raise SystemExit(
            f"{page}: expected {len(COUNT_PREFIXES)} count rows, found {found}"
        )
    return new


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
