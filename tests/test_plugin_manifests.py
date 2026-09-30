"""The Claude Code and Codex plugins and the Gemini CLI extension run a pinned
TerraVision.

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
    ".codex-plugin/plugin.json",
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


def test_plugin_versions_agree():
    """Installed plugins update only when this version rises, so every place
    that states it must move together (bump it whenever the skill changes)."""
    import re

    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    gemini = json.loads((ROOT / "gemini-extension.json").read_text())["version"]
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())["version"]
    skill = re.search(
        r'^  version: "([^"]+)"',
        (ROOT / "skills/terravision-cloud-diagrams/SKILL.md").read_text(),
        re.M,
    ).group(1)
    versions = {
        "plugin.json": plugin,
        "marketplace metadata": market["metadata"]["version"],
        "marketplace plugin": market["plugins"][0]["version"],
        "gemini-extension.json": gemini,
        "codex plugin.json": codex,
        "SKILL.md": skill,
    }
    assert len(set(versions.values())) == 1, versions


def test_codex_manifest_is_the_claude_one_plus_its_own_fields():
    """Codex reads .codex-plugin/plugin.json in preference to the Claude
    manifest, and shows interface.websiteURL as the plugin's website. Claude
    Code rejects that key, so Codex gets its own copy; everything else in it
    must stay the same as the Claude manifest."""
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    interface = codex.pop("interface")
    assert codex == claude
    assert interface["websiteURL"] == claude["homepage"]
