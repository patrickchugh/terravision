"""The type counts the README and docs quote match what TerraVision can draw.

The Supported Cloud Providers table on README.md, docs/index.md and
docs/faq.md says how many types each cloud has. scripts/gen_node_types.py
writes those counts; this fails when types were added without rerunning it.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "gen_node_types", ROOT / "scripts" / "gen_node_types.py"
)
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
COUNTS = _gen.type_counts(_gen.collect())


@pytest.mark.parametrize("page", _gen.COUNT_PAGES, ids=lambda p: p.name)
def test_published_type_counts_are_current(page):
    quoted = {m[2]: int(m[3]) for m in _gen.COUNT_ROW.finditer(page.read_text())}
    assert quoted == COUNTS, (
        f"{page.relative_to(ROOT)} quotes {quoted}, but TerraVision draws "
        f"{COUNTS}: run poetry run python scripts/gen_node_types.py"
    )
