"""Tests for graph file handling on the CLI: graphdata output naming and
loading a graph file as a draw source."""

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


def test_graph_file_leaf_targets_become_nodes(tmp_path):
    """A leaf that only appears as a target must still be drawn."""
    import json

    from modules.tfwrapper import load_json_source

    graph = tmp_path / "leaf.tvg.json"
    graph.write_text(
        json.dumps({"aws_lambda_function.api": ["aws_dynamodb_table.orders"]})
    )
    graphdict = load_json_source(str(graph))["graphdict"]
    assert graphdict == {
        "aws_lambda_function.api": ["aws_dynamodb_table.orders"],
        "aws_dynamodb_table.orders": [],
    }


def test_exported_terraform_dangling_targets_stay_undrawn():
    """Terraform exports reference stale names that must not become nodes:
    an unnumbered copy of numbered nodes, and a hidden type's children."""
    from modules.tfwrapper import _add_leaf_targets

    graph = {
        "aws_eks_cluster.main": ["aws_eks_node_group.main"],
        "aws_eks_node_group.main~1": [],
        "aws_fargate.ecs~1": ["aws_efs_mount_target.this"],
        "aws_efs_mount_target.this[0]~1": [],
        "aws_route_table.private": ["aws_route_table_association.private"],
    }
    before = dict(graph)
    _add_leaf_targets(graph)
    assert graph == before


class TestSingleProviderGraph:
    """A graph file is drawn with one provider's conventions, so mixing
    providers is refused instead of silently dropping the minority."""

    @staticmethod
    def _load(tmp_path, graph):
        import json

        from modules.tfwrapper import load_json_source

        path = tmp_path / "g.tvg.json"
        path.write_text(json.dumps(graph))
        return load_json_source(str(path))

    @pytest.mark.parametrize(
        "graph",
        [
            {"aws_lambda_function.fn": ["azurerm_storage_account.sa"]},
            {"tv_aws_users.u": ["azurerm_linux_web_app.web"]},
            {"module.app.google_cloud_run_v2_service.api": ["aws_s3_bucket.b"]},
        ],
    )
    def test_mixed_providers_refused(self, tmp_path, graph):
        from modules.helpers import TerravisionError

        with pytest.raises(TerravisionError, match="Graph mixes"):
            self._load(tmp_path, graph)

    @pytest.mark.parametrize(
        "graph",
        [
            {"aws_lambda_function.fn": ["random_string.suffix"]},
            {"tv_gcp_users_icon.aws_team": ["google_cloud_run_v2_service.api"]},
            {"tv_azure_onprem.dc": ["azurerm_virtual_network_gateway.gw"]},
        ],
    )
    def test_single_provider_accepted(self, tmp_path, graph):
        assert self._load(tmp_path, graph)["graphdict"]

    def test_draw_reports_mixed_providers(self, tmp_path, monkeypatch):
        import json

        from click.testing import CliRunner

        from terravision.terravision import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / "g.tvg.json").write_text(
            json.dumps({"aws_lambda_function.fn": ["google_storage_bucket.b"]})
        )
        result = CliRunner().invoke(cli, ["draw", "--source", "g.tvg.json"])
        assert result.exit_code != 0
        assert "Graph mixes aws_* and google_* resources" in result.output
        assert not list(tmp_path.glob("architecture*.png"))
