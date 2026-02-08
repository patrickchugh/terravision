"""Tests for pre-generated plan file input mode (--planfile / --graphfile)."""

import json
import os
import tempfile

import pytest
from click.testing import CliRunner

# Import the functions under test
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from terravision.terravision import (
    _validate_planfile,
    _validate_pregenerated_inputs,
    _validate_consistency,
    cli,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "json")
PLAN_FILE = os.path.join(FIXTURES_DIR, "bastion-plan.json")
GRAPH_FILE = os.path.join(FIXTURES_DIR, "bastion-graph.dot")


# ── _validate_planfile tests ──


class TestValidatePlanfile:
    def test_valid_plan_json(self):
        """Valid plan JSON should return parsed dict with resource_changes."""
        result = _validate_planfile(PLAN_FILE)
        assert isinstance(result, dict)
        assert "resource_changes" in result
        assert len(result["resource_changes"]) > 0

    def test_invalid_json_file(self, tmp_path):
        """Non-JSON file should cause SystemExit."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("this is not json {{{")
        with pytest.raises(SystemExit):
            _validate_planfile(str(bad_file))

    def test_binary_file_detected(self, tmp_path):
        """Binary .tfplan file should be detected and produce helpful error."""
        binary_file = tmp_path / "tfplan.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03binary data")
        with pytest.raises(SystemExit):
            _validate_planfile(str(binary_file))

    def test_missing_resource_changes(self, tmp_path):
        """JSON without resource_changes key should cause SystemExit."""
        bad_plan = tmp_path / "no-resources.json"
        bad_plan.write_text(json.dumps({"format_version": "1.0"}))
        with pytest.raises(SystemExit):
            _validate_planfile(str(bad_plan))

    def test_empty_resource_changes(self, tmp_path):
        """JSON with empty resource_changes should cause SystemExit."""
        empty_plan = tmp_path / "empty.json"
        empty_plan.write_text(
            json.dumps({"format_version": "1.0", "resource_changes": []})
        )
        with pytest.raises(SystemExit):
            _validate_planfile(str(empty_plan))

    def test_unrecognized_format_version_warns(self, tmp_path, capsys):
        """Unrecognized format version should warn but not fail."""
        plan = tmp_path / "v2.json"
        plan.write_text(
            json.dumps(
                {
                    "format_version": "2.0",
                    "resource_changes": [
                        {
                            "address": "aws_vpc.main",
                            "mode": "managed",
                            "type": "aws_vpc",
                            "change": {
                                "actions": ["create"],
                                "after": {},
                                "after_unknown": {},
                                "after_sensitive": {},
                            },
                        }
                    ],
                }
            )
        )
        result = _validate_planfile(str(plan))
        assert result is not None
        captured = capsys.readouterr()
        assert "WARNING" in captured.out or "Unrecognized" in captured.out


# ── _validate_pregenerated_inputs tests ──


class TestValidatePreGeneratedInputs:
    def test_planfile_without_graphfile(self):
        """--planfile without --graphfile should cause SystemExit."""
        with pytest.raises(SystemExit):
            _validate_pregenerated_inputs(PLAN_FILE, "", ["."])

    def test_graphfile_without_planfile(self):
        """--graphfile without --planfile should cause SystemExit."""
        with pytest.raises(SystemExit):
            _validate_pregenerated_inputs("", GRAPH_FILE, ["."])

    def test_planfile_without_source(self):
        """--planfile without --source should cause SystemExit."""
        with pytest.raises(SystemExit):
            _validate_pregenerated_inputs(PLAN_FILE, GRAPH_FILE, ["."])

    def test_planfile_with_json_source(self):
        """--planfile with .json source should cause SystemExit."""
        with pytest.raises(SystemExit):
            _validate_pregenerated_inputs(PLAN_FILE, GRAPH_FILE, ["tfdata.json"])

    def test_valid_inputs_pass(self, tmp_path):
        """Valid planfile + graphfile + source directory should not raise."""
        source_dir = str(tmp_path)
        _validate_pregenerated_inputs(PLAN_FILE, GRAPH_FILE, [source_dir])

    def test_valid_inputs_git_url_pass(self):
        """Valid planfile + graphfile + git URL source should not raise."""
        _validate_pregenerated_inputs(
            PLAN_FILE, GRAPH_FILE, ["https://github.com/user/repo.git"]
        )

    def test_nonexistent_planfile(self, tmp_path):
        """Non-existent planfile should cause SystemExit."""
        with pytest.raises(SystemExit):
            _validate_pregenerated_inputs(
                "/nonexistent/plan.json", GRAPH_FILE, [str(tmp_path)]
            )

    def test_nonexistent_graphfile(self, tmp_path):
        """Non-existent graphfile should cause SystemExit."""
        with pytest.raises(SystemExit):
            _validate_pregenerated_inputs(
                PLAN_FILE, "/nonexistent/graph.dot", [str(tmp_path)]
            )


# ── _validate_consistency tests ──


class TestValidateConsistency:
    def test_matching_provider_prefix_passes(self):
        """Consistency check should pass when provider prefixes match."""
        tfdata = {
            "tf_resources_created": [
                {"address": "aws_vpc.main", "mode": "managed", "type": "aws_vpc"}
            ],
            "all_resource": {"vpc.tf": [{"aws_vpc": {"main": {}}}]},
            "graphdict": {"aws_vpc.main": []},
        }
        # Should not raise
        _validate_consistency(tfdata)

    def test_mismatched_provider_prefix_fails(self):
        """Consistency check should fail when provider prefixes don't match."""
        tfdata = {
            "tf_resources_created": [
                {"address": "aws_vpc.main", "mode": "managed", "type": "aws_vpc"}
            ],
            "all_resource": {"network.tf": [{"azurerm_virtual_network": {"main": {}}}]},
            "graphdict": {"aws_vpc.main": []},
        }
        with pytest.raises(SystemExit):
            _validate_consistency(tfdata)

    def test_resource_not_in_graph_fails(self):
        """Consistency check should fail when plan resource missing from graph."""
        tfdata = {
            "tf_resources_created": [
                {"address": "aws_vpc.main", "mode": "managed", "type": "aws_vpc"}
            ],
            "all_resource": {"vpc.tf": [{"aws_vpc": {"main": {}}}]},
            "graphdict": {"aws_subnet.public": []},
        }
        with pytest.raises(SystemExit):
            _validate_consistency(tfdata)

    def test_empty_plan_resources_passes(self):
        """No managed resources should pass (nothing to check)."""
        tfdata = {
            "tf_resources_created": [
                {"address": "data.aws_ami.latest", "mode": "data", "type": "aws_ami"}
            ],
            "all_resource": {},
            "graphdict": {},
        }
        # Should not raise
        _validate_consistency(tfdata)


# ── CLI option tests ──


class TestCliOptions:
    def test_draw_accepts_planfile_option(self):
        """draw command should accept --planfile and --graphfile options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["draw", "--help"])
        assert "--planfile" in result.output
        assert "--graphfile" in result.output

    def test_graphdata_accepts_planfile_option(self):
        """graphdata command should accept --planfile and --graphfile options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["graphdata", "--help"])
        assert "--planfile" in result.output
        assert "--graphfile" in result.output
