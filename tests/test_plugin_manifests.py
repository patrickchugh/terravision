"""The Claude Code and Codex plugins and the Gemini CLI extension run a pinned
TerraVision.

uvx reuses a cached TerraVision when the requirement does not name a
version, so an unpinned plugin kept running the old server after a plugin
update gave users the new skill. Pinned, a plugin update changes the
requirement and uvx installs the matching release. The pin must equal the
version in pyproject.toml, so it is bumped in the same commit as
`poetry version`. scripts/set_versions.py sets all of these versions.
"""

import importlib.util
import json
import re
import shutil
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "set_versions", ROOT / "scripts" / "set_versions.py"
)
set_versions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(set_versions)
MANIFESTS = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    "gemini-extension.json",
]


def _version(root: Path = ROOT) -> str:
    with open(root / "pyproject.toml", "rb") as fh:
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
            f'{path} runs "{requirement}"; after `poetry version`, run '
            "scripts/set_versions.py --pin so plugin updates install the "
            "matching server"
        )


def _plugin_versions(root: Path = ROOT) -> dict:
    plugin = json.loads((root / ".claude-plugin/plugin.json").read_text())["version"]
    market = json.loads((root / ".claude-plugin/marketplace.json").read_text())
    gemini = json.loads((root / "gemini-extension.json").read_text())["version"]
    codex = json.loads((root / ".codex-plugin/plugin.json").read_text())["version"]
    skill = re.search(
        r'^  version: "([^"]+)"',
        (root / "skills/terravision-cloud-diagrams/SKILL.md").read_text(),
        re.M,
    ).group(1)
    return {
        "plugin.json": plugin,
        "marketplace metadata": market["metadata"]["version"],
        "marketplace plugin": market["plugins"][0]["version"],
        "gemini-extension.json": gemini,
        "codex plugin.json": codex,
        "SKILL.md": skill,
    }


def test_plugin_versions_agree():
    """Installed plugins update only when this version rises, so every place
    that states it must move together (bump it whenever the skill changes)."""
    versions = _plugin_versions()
    assert len(set(versions.values())) == 1, versions


@pytest.fixture
def repo(tmp_path):
    """A copy of every file scripts/set_versions.py edits."""
    for name in [*MANIFESTS, set_versions.SKILL, "pyproject.toml"]:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, tmp_path / name)
    return tmp_path


def test_set_plugin_moves_every_place(repo):
    assert set_versions.set_plugin("9.8.7", repo) == "9.8.7"
    assert set(_plugin_versions(repo).values()) == {"9.8.7"}


def test_set_pin_follows_pyproject(repo):
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace(_version(), "9.8.7"))

    assert set_versions.set_pin(repo) == "9.8.7"

    for path in MANIFESTS:
        for server in _servers(json.loads((repo / path).read_text())):
            assert "terravision[mcp]==9.8.7" in server["args"]


@pytest.mark.parametrize(
    "target, expected",
    [
        ("patch", "1.10.1"),
        ("minor", "1.11.0"),
        ("major", "2.0.0"),
        ("3.4.5", "3.4.5"),
    ],
)
def test_next_version(target, expected):
    assert set_versions.next_version("1.10.0", target) == expected


def test_next_version_rejects_anything_else():
    with pytest.raises(ValueError):
        set_versions.next_version("1.10.0", "nonsense")


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
