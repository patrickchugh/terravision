"""Render smoke tests: every provider's replay fixture must survive Graphviz.

The rest of the suite validates the *graph* (graphdict comparisons) but almost
nothing validates that the graph can be *drawn*: ``render_diagram`` writes a
``.gv`` file whose parsing happens inside the external ``dot`` binary, so a
malformed label or an invalid rankset is invisible to any Python-level
assertion. Two real regressions motivated these tests, both introduced while
the graphdict suite stayed green:

- an availability-zone caption emitted as a bare ``<FONT>`` HTML string,
  which ``dot`` rejects as a syntax error (angle brackets must balance);
- nodes that live inside a nested cluster additionally placed in a
  ``rank=same`` subgraph by the grid-wrapper, which trips an assertion
  inside ``dot``'s mincross pass (SIGABRT).

Rendering to ``png`` runs the full pipeline - .gv generation, ``dot``
parsing, layout, and image emission - so a failure anywhere in it fails the
test. No pixel comparison: the assertion is only that the render completes
and produces a non-empty file, which is exactly the property the graphdict
tests cannot see.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from terravision.terravision import cli

JSON_DIR = Path(__file__).parent / "json"

# One replay fixture per provider, chosen to exercise provider-specific
# drawing paths: Azure zone clusters (bare-FONT captions, nested ranksets),
# GCP HTML-table nodes plus the generic-node fallback (outer_node kwarg),
# and the AWS AZ/subnet nesting.
RENDER_FIXTURES = [
    pytest.param("bastion-tfdata.json", id="aws"),
    pytest.param("azure-vm-vmss-tfdata.json", id="azure"),
    pytest.param("gcp-three-tier-webapp-tfdata.json", id="gcp"),
]


@pytest.mark.parametrize("fixture", RENDER_FIXTURES)
def test_draw_renders_png_from_replay(fixture, tmp_path, monkeypatch):
    """`terravision draw` must produce a PNG for each provider's fixture."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", str(JSON_DIR / fixture), "--outfile", "smoke"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    produced = list(tmp_path.glob("smoke*.png"))
    assert produced, f"no PNG produced; files: {[p.name for p in tmp_path.iterdir()]}"
    assert produced[0].stat().st_size > 0
