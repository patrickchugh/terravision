#!/usr/bin/env python3
"""Set the versions that have to agree across the plugin manifests.

    poetry run python scripts/set_versions.py --pin            # step 1 of a release
    poetry run python scripts/set_versions.py --plugin patch   # or minor, major, 1.11.0

--pin sets the terravision[mcp] pin in every manifest to the version in
pyproject.toml. Run it after `poetry version` and commit it with the release.

--plugin sets the plugin's own version in every manifest and in SKILL.md.
Installed plugins update only when this rises, so run it for any skill change
and for every release, but for a release only once pip can install the new
version: until then an updated plugin pins a server that cannot start.

Claude Code, Codex and Gemini each read their manifest from the repository as
it stands, so the files have to hold the numbers themselves.
tests/test_plugin_manifests.py fails if they disagree.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    "gemini-extension.json",
]
SKILL = "skills/terravision-cloud-diagrams/SKILL.md"
PIN = re.compile(r"terravision\[mcp\]==[^\"]+")
MANIFEST_VERSION = re.compile(r'"version": "([^"]+)"')
SKILL_VERSION = re.compile(r'^  version: "[^"]+"', re.M)
PLAIN_VERSION = re.compile(r"\d+\.\d+\.\d+")


def next_version(current: str, target: str) -> str:
    """Return the version a bump gives: target is patch, minor, major or x.y.z."""
    if PLAIN_VERSION.fullmatch(target):
        return target
    major, minor, patch = (int(part) for part in current.split("."))
    if target == "major":
        return f"{major + 1}.0.0"
    if target == "minor":
        return f"{major}.{minor + 1}.0"
    if target == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"'{target}' is not patch, minor, major or a version like 1.11.0")


def _substitute(path: Path, pattern: re.Pattern, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = pattern.subn(replacement, text)
    if not count:
        raise ValueError(f"{path} has nothing to update")
    path.write_text(new_text, encoding="utf-8")


def set_pin(root: Path = ROOT) -> str:
    """Pin every manifest's MCP server to the version in pyproject.toml."""
    with open(root / "pyproject.toml", "rb") as fh:
        version = tomllib.load(fh)["project"]["version"]
    for manifest in MANIFESTS:
        _substitute(root / manifest, PIN, f"terravision[mcp]=={version}")
    return version


def set_plugin(target: str, root: Path = ROOT) -> str:
    """Set the plugin version everywhere it is stated and return it."""
    manifest_text = (root / MANIFESTS[0]).read_text(encoding="utf-8")
    version = next_version(MANIFEST_VERSION.search(manifest_text).group(1), target)
    for manifest in MANIFESTS:
        _substitute(root / manifest, MANIFEST_VERSION, f'"version": "{version}"')
    _substitute(root / SKILL, SKILL_VERSION, f'  version: "{version}"')
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--pin", action="store_true", help="pin the MCP server to pyproject.toml"
    )
    action.add_argument(
        "--plugin",
        metavar="VERSION",
        help="plugin version: patch, minor, major or x.y.z",
    )
    args = parser.parse_args()
    try:
        if args.pin:
            print(f"MCP server pinned to terravision[mcp]=={set_pin()}")
        else:
            print(f"Plugin version set to {set_plugin(args.plugin)}")
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
