#!/usr/bin/env python3
"""Regenerate the example list in docs/llms.txt and docs/llms-full.txt.

    poetry run python scripts/update_llms_examples.py

Rewrites the lines between the <!-- examples:start --> and
<!-- examples:end --> markers with one line per row of the table in
examples/graphs/README.md, in its order:

    - [<name>.tvg.json](<raw URL>): <provider>, <what it shows>

scripts/render_examples.py runs this after rendering, so the list cannot
drift from the gallery.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "examples" / "graphs" / "README.md"
TARGETS = [ROOT / "docs" / "llms.txt", ROOT / "docs" / "llms-full.txt"]
RAW = "https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs"
START, END = "<!-- examples:start -->", "<!-- examples:end -->"
ROW = re.compile(
    r"^\|\s*`(?P<file>[a-z0-9-]+\.tvg\.json)`\s*\|\s*(?P<provider>[^|]+?)\s*\|\s*(?P<what>.+?)\s*\|\s*$"
)


def readme_rows():
    """(file, provider, what it shows) for each example row of the README table."""
    return [
        (m["file"], m["provider"], m["what"])
        for m in map(ROW.match, README.read_text().splitlines())
        if m
    ]


def block():
    lines = [
        f"- [{file}]({RAW}/{file}): {provider}, {what}"
        for file, provider, what in readme_rows()
    ]
    return "\n".join([START, *lines, END])


def update(path, text):
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    current = path.read_text()
    if not pattern.search(current):
        raise SystemExit(
            f"{path.relative_to(ROOT)}: {START} ... {END} markers not found"
        )
    updated = pattern.sub(lambda _: text, current, count=1)
    if updated != current:
        path.write_text(updated)
        return True
    return False


def main():
    text = block()
    for path in TARGETS:
        changed = update(path, text)
        print(f"{path.relative_to(ROOT)}: {'updated' if changed else 'up to date'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
