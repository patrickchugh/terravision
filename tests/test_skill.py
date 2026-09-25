"""Tests for the agent skill in skills/terravision-cloud-diagrams."""

import re
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / "skills" / "terravision-cloud-diagrams"


def _frontmatter():
    text = (SKILL / "SKILL.md").read_text()
    return yaml.safe_load(re.match(r"---\n(.*?)\n---\n", text, re.S).group(1))


def test_frontmatter_is_valid_yaml():
    """A strict YAML parser must accept it; an unquoted ': ' in the
    description once made the whole skill unloadable for strict agents."""
    meta = _frontmatter()
    assert meta["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9-]+", meta["name"])
    assert 0 < len(meta["description"]) <= 1024
