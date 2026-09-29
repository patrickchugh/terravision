"""The diagram footer: a reproducible timestamp, and the source path as given.

Issue #216: the footer's timestamp made every render differ, so a CI job that
commits the diagram only when it changed committed on every run. It honours
SOURCE_DATE_EPOCH now.

Issue #219: Graphviz expands \\G, \\N and the like even in HTML labels, so a
Windows path such as C:\\dev\\GitLab printed as C:\\dev%1itLab.
"""

import json

import pytest
from click.testing import CliRunner

from modules import drawing
from modules.helpers import TerravisionError
from terravision.terravision import cli

GRAPH = {
    "aws_vpc.main": ["aws_subnet.app"],
    "aws_subnet.app": ["aws_instance.web"],
}


def _draw_svg(source_dir, outdir):
    source = source_dir / "architecture.tvg.json"
    source.write_text(json.dumps(GRAPH))
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(source),
            "--format",
            "svg",
            "--outfile",
            str(outdir / "diagram"),
        ],
    )
    assert result.exit_code == 0, result.output
    [svg] = outdir.glob("diagram*.svg")
    return svg.read_text(encoding="utf-8")


def test_source_date_epoch_sets_the_timestamp(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    assert drawing._footer_timestamp() == "2023-11-14 22:13:20 UTC"


def test_timestamp_is_now_without_source_date_epoch(monkeypatch):
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert drawing._footer_timestamp().startswith(
        __import__("datetime").date.today().isoformat()
    )


@pytest.mark.parametrize("value", ["yesterday", "1.5", "99999999999999999999"])
def test_a_malformed_source_date_epoch_is_an_error(monkeypatch, value):
    """The specification asks for an error rather than a guess."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", value)
    with pytest.raises(TerravisionError, match="SOURCE_DATE_EPOCH"):
        drawing._footer_timestamp()


def test_same_source_draws_identical_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    first = _draw_svg(tmp_path, tmp_path)
    second = _draw_svg(tmp_path, tmp_path)
    assert "2023&#45;11&#45;14 22:13:20 UTC" in first  # SVG escapes hyphens
    assert first == second


def test_backslashes_in_the_source_path_survive(tmp_path, monkeypatch):
    """A folder named like a Windows path segment starting with G: Graphviz
    turned \\G into the graph's name."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    source_dir = tmp_path / "dev\\GitLab"
    source_dir.mkdir()
    outdir = tmp_path / "out"
    outdir.mkdir()
    svg = _draw_svg(source_dir, outdir)
    assert "dev/GitLab/architecture.tvg.json" in svg
    assert "itLab" not in svg.replace("GitLab", "")
