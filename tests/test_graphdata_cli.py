"""Tests for the graphdata command's output file naming."""

from pathlib import Path

import pytest


class TestGraphdataOutfileExtension:
    """graphdata names a full graph .tvg.json, a service list plain .json."""

    REPLAY = str(Path(__file__).parent / "json" / "bastion-tfdata.json")

    @pytest.mark.parametrize(
        "args, expected",
        [
            (["--outfile", "arch"], "arch.tvg.json"),
            (["--outfile", "arch.json"], "arch.json"),
            (["--outfile", "svc", "--show_services"], "svc.json"),
        ],
    )
    def test_outfile_name(self, tmp_path, monkeypatch, args, expected):
        from click.testing import CliRunner

        from terravision.terravision import cli

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            cli, ["graphdata", "--source", self.REPLAY, *args], catch_exceptions=False
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / expected).exists()
