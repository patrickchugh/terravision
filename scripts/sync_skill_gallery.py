#!/usr/bin/env python3
"""Copy the gallery examples into the agent skill, for diagram_guide.

    poetry run python scripts/sync_skill_gallery.py

Writes skills/terravision-cloud-diagrams/examples/gallery/: each example's
<name>.tvg.json and <name>.annotations.yml from examples/graphs, and
index.json, one entry per row of the table in examples/graphs/README.md, in
its order:

    {"name": ..., "provider": "aws" | "azure" | "gcp", "title": ...,
     "description": <what it shows>}

diagram_guide lists these and returns one by name, so an assistant can start
from the closest gallery design. Files for examples no longer in the README
are removed. scripts/render_examples.py runs this after rendering, so the
skill's copies cannot drift from the gallery.
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from update_llms_examples import readme_rows  # noqa: E402

EXAMPLES = ROOT / "examples" / "graphs"
GALLERY = ROOT / "skills" / "terravision-cloud-diagrams" / "examples" / "gallery"
PROVIDERS = {"AWS": "aws", "Azure": "azure", "GCP": "gcp"}


def index():
    entries = []
    for file, provider, what in readme_rows():
        name = file[: -len(".tvg.json")]
        annotations = yaml.safe_load((EXAMPLES / f"{name}.annotations.yml").read_text())
        entries.append(
            {
                "name": name,
                "provider": PROVIDERS[provider],
                "title": annotations["title"],
                "description": what,
            }
        )
    return entries


def _write(path, text):
    if path.exists() and path.read_text() == text:
        return False
    path.write_text(text)
    return True


def sync():
    """Bring the skill's gallery folder up to date; return the files changed."""
    GALLERY.mkdir(parents=True, exist_ok=True)
    entries = index()
    wanted = {"index.json"}
    changed = []
    for entry in entries:
        for suffix in (".tvg.json", ".annotations.yml"):
            name = entry["name"] + suffix
            wanted.add(name)
            if _write(GALLERY / name, (EXAMPLES / name).read_text()):
                changed.append(name)
    if _write(GALLERY / "index.json", json.dumps(entries, indent=2) + "\n"):
        changed.append("index.json")
    for stale in sorted(p for p in GALLERY.iterdir() if p.name not in wanted):
        stale.unlink()
        changed.append(f"removed {stale.name}")
    return entries, changed


def main():
    entries, changed = sync()
    where = GALLERY.relative_to(ROOT)
    if changed:
        print(f"{where}: {len(entries)} examples, updated {len(changed)} files")
    else:
        print(f"{where}: {len(entries)} examples, up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
