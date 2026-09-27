"""The Claude Code plugin and Gemini CLI extension run a pinned TerraVision.

uvx reuses a cached TerraVision when the requirement does not name a
version, so an unpinned plugin kept running the old server after a plugin
update gave users the new skill. Pinned, a plugin update changes the
requirement and uvx installs the matching release. The pin must equal the
version in pyproject.toml, so it is bumped in the same commit as
`poetry version`.
"""

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "gemini-extension.json",
]


def _version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _servers(manifest: dict):
    yield from (manifest.get("mcpServers") or {}).values()
    for plugin in manifest.get("plugins") or []:
        yield from (plugin.get("mcpServers") or {}).values()


@pytest.mark.parametrize("path", MANIFESTS)
def test_mcp_server_is_pinned_to_this_release(path):
    manifest = json.loads((ROOT / path).read_text())
    servers = list(_servers(manifest))
    assert servers, f"{path} defines no MCP server"
    for server in servers:
        args = server["args"]
        requirement = args[args.index("--from") + 1]
        assert requirement == f"terravision[mcp]=={_version()}", (
            f'{path} runs "{requirement}"; after `poetry version`, set it to '
            f'"terravision[mcp]=={_version()}" so plugin updates install the '
            "matching server"
        )
