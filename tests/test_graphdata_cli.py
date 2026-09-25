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
