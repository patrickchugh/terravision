"""Every handler function a resource handler config names must exist.

graphmaker resolves "additional_handler_function" with getattr at render
time, so a name with no function behind it crashed every plan containing
that resource type. aws_glue_catalog_table named aws_handle_glue_catalog,
which never existed (issue #213).
"""

import importlib

import pytest


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_every_additional_handler_function_exists(provider):
    configs = importlib.import_module(
        f"modules.config.resource_handler_configs_{provider}"
    ).RESOURCE_HANDLER_CONFIGS
    handlers = importlib.import_module(f"modules.resource_handlers_{provider}")
    missing = {
        resource_type: config["additional_handler_function"]
        for resource_type, config in configs.items()
        if config.get("additional_handler_function")
        and not hasattr(handlers, config["additional_handler_function"])
    }
    assert not missing, f"handler functions that do not exist: {missing}"


def test_glue_catalog_table_draws_and_links_its_bucket(tmp_path, monkeypatch):
    """The issue's repro, from a plan file: no crash, table linked to bucket."""
    import shutil
    from pathlib import Path

    from click.testing import CliRunner

    from terravision.terravision import cli

    fixture = (
        Path(__file__).parent / "fixtures" / "aws_terraform" / "glue_catalog_planfile"
    )
    source = tmp_path / "infra"
    shutil.copytree(fixture, source)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli,
        ["graphdata", "--source", str(source), "--planfile", str(source / "plan.json"),
         "--graphfile", str(source / "graph.dot"), "--outfile", "graph.json"],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    import json

    graph = json.loads((tmp_path / "graph.json").read_text())
    assert "aws_s3_bucket.reports" in graph["aws_glue_catalog_table.report"]
