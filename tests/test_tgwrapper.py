"""Tests for Terragrunt wrapper module."""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

import modules.tgwrapper as tgwrapper


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SINGLE_FIXTURE = os.path.join(FIXTURES_DIR, "terragrunt-single")
MULTI_FIXTURE = os.path.join(FIXTURES_DIR, "terragrunt-multi")


@pytest.fixture
def tmpdir():
    """Create a temporary directory and clean it up after the test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestDetectTerragrunt:
    """Tests for detect_terragrunt()."""

    def test_single_module_with_terragrunt_hcl(self, tmpdir):
        """Directory containing terragrunt.hcl is detected as single-module."""
        open(os.path.join(tmpdir, "terragrunt.hcl"), "w").close()
        result = tgwrapper.detect_terragrunt(tmpdir)
        assert result["is_terragrunt"] is True
        assert result["is_multi_module"] is False
        assert result["child_modules"] == []

    def test_multi_module_with_child_terragrunt_hcl(self, tmpdir):
        """Child dirs with terragrunt.hcl detected as multi-module."""
        child_a = os.path.join(tmpdir, "vpc")
        child_b = os.path.join(tmpdir, "eks")
        os.makedirs(child_a)
        os.makedirs(child_b)
        open(os.path.join(child_a, "terragrunt.hcl"), "w").close()
        open(os.path.join(child_b, "terragrunt.hcl"), "w").close()
        result = tgwrapper.detect_terragrunt(tmpdir)
        assert result["is_terragrunt"] is True
        assert result["is_multi_module"] is True
        assert sorted(result["child_modules"]) == sorted(
            [os.path.abspath(child_a), os.path.abspath(child_b)]
        )

    def test_terraform_dir_no_terragrunt(self, tmpdir):
        """Directory without any terragrunt.hcl is not detected."""
        open(os.path.join(tmpdir, "main.tf"), "w").close()
        result = tgwrapper.detect_terragrunt(tmpdir)
        assert result["is_terragrunt"] is False
        assert result["is_multi_module"] is False
        assert result["child_modules"] == []

    def test_empty_directory(self, tmpdir):
        """Empty directory is not detected as terragrunt."""
        result = tgwrapper.detect_terragrunt(tmpdir)
        assert result["is_terragrunt"] is False
        assert result["is_multi_module"] is False
        assert result["child_modules"] == []

    def test_skips_terragrunt_cache_dirs(self, tmpdir):
        """Directories named .terragrunt-cache are skipped."""
        cache_dir = os.path.join(tmpdir, ".terragrunt-cache", "mod")
        os.makedirs(cache_dir)
        open(os.path.join(cache_dir, "terragrunt.hcl"), "w").close()
        result = tgwrapper.detect_terragrunt(tmpdir)
        assert result["is_terragrunt"] is False
        assert result["child_modules"] == []

    def test_nested_child_modules(self, tmpdir):
        """Deeply nested child dirs with terragrunt.hcl are found."""
        nested = os.path.join(tmpdir, "infra", "network", "vpc")
        os.makedirs(nested)
        open(os.path.join(nested, "terragrunt.hcl"), "w").close()
        result = tgwrapper.detect_terragrunt(tmpdir)
        assert result["is_terragrunt"] is True
        assert result["is_multi_module"] is True
        assert result["child_modules"] == [os.path.abspath(nested)]


class TestCheckTerragruntVersion:
    """Tests for check_terragrunt_version()."""

    @patch("modules.tgwrapper.subprocess.run")
    def test_parses_valid_version(self, mock_run):
        """Parses version from 'terragrunt version v0.67.4' output."""
        mock_run.return_value = MagicMock(
            stdout="terragrunt version v0.67.4\n", stderr="", returncode=0
        )
        version = tgwrapper.check_terragrunt_version()
        assert version == "0.67.4"
        mock_run.assert_called_once()

    @patch("modules.tgwrapper.subprocess.run")
    def test_parses_version_without_v_prefix(self, mock_run):
        """Handles version output without 'v' prefix."""
        mock_run.return_value = MagicMock(
            stdout="terragrunt version 0.55.0\n", stderr="", returncode=0
        )
        version = tgwrapper.check_terragrunt_version()
        assert version == "0.55.0"

    @patch("modules.tgwrapper.subprocess.run")
    def test_raises_file_not_found_when_binary_missing(self, mock_run):
        """Raises FileNotFoundError when terragrunt binary is not installed."""
        mock_run.side_effect = FileNotFoundError("No such file")
        with pytest.raises(FileNotFoundError, match="terragrunt.*not found"):
            tgwrapper.check_terragrunt_version()

    @patch("modules.tgwrapper.subprocess.run")
    def test_raises_runtime_error_when_version_too_old(self, mock_run):
        """Raises RuntimeError when version is below minimum."""
        mock_run.return_value = MagicMock(
            stdout="terragrunt version v0.40.0\n", stderr="", returncode=0
        )
        with pytest.raises(RuntimeError, match="not supported"):
            tgwrapper.check_terragrunt_version()

    @patch("modules.tgwrapper.subprocess.run")
    def test_raises_runtime_error_on_unparseable_output(self, mock_run):
        """Raises RuntimeError when version cannot be parsed."""
        mock_run.return_value = MagicMock(
            stdout="something unexpected\n", stderr="", returncode=0
        )
        with pytest.raises(RuntimeError, match="Could not parse"):
            tgwrapper.check_terragrunt_version()

    @patch("modules.tgwrapper.subprocess.run")
    def test_accepts_minimum_version_exactly(self, mock_run):
        """Minimum version (0.50.0) is accepted without error."""
        mock_run.return_value = MagicMock(
            stdout=f"terragrunt version v{tgwrapper.MIN_TERRAGRUNT_VERSION}\n",
            stderr="",
            returncode=0,
        )
        version = tgwrapper.check_terragrunt_version()
        assert version == tgwrapper.MIN_TERRAGRUNT_VERSION


class TestPrepareTgSource:
    """Tests for _prepare_tg_source()."""

    def test_writes_override_and_returns_correct_path(self, tmpdir):
        """_prepare_tg_source writes terravision_override.tf and returns codepath."""
        codepath, override_dest = tgwrapper._prepare_tg_source(tmpdir)
        assert codepath == os.path.abspath(tmpdir)
        assert override_dest == os.path.join(codepath, "terravision_override.tf")
        assert os.path.isfile(override_dest)
        os.remove(override_dest)

    def test_override_contains_local_backend(self, tmpdir):
        """The written override file forces local backend."""
        _, override_dest = tgwrapper._prepare_tg_source(tmpdir)
        with open(override_dest) as f:
            content = f.read()
        assert "local" in content
        assert "backend" in content
        os.remove(override_dest)

    def test_codepath_is_absolute(self, tmpdir):
        """Returned codepath is always absolute."""
        codepath, override_dest = tgwrapper._prepare_tg_source(tmpdir)
        assert os.path.isabs(codepath)
        os.remove(override_dest)


class TestParseTgDependencies:
    """Tests for _parse_tg_dependencies().

    Uses mocked hcl2.load output since python-hcl2 returns custom dict-like
    objects whose indexing differs from standard lists.
    """

    def test_extracts_dependency_and_dep_inputs(self, tmpdir):
        """Parses dependency blocks and input references from mocked HCL data."""
        # Create the file so the os.path.isfile check passes
        with open(os.path.join(tmpdir, "terragrunt.hcl"), "w") as f:
            f.write("placeholder")

        mock_parsed = {
            "dependency": [
                {"vpc": {"config_path": "../vpc"}},
                {"rds": {"config_path": "../rds"}},
            ],
            "inputs": [
                {
                    "vpc_id": "${dependency.vpc.outputs.vpc_id}",
                    "db_host": "${dependency.rds.outputs.endpoint}",
                    "static_val": "hardcoded",
                }
            ],
        }

        with patch("modules.tgwrapper.hcl2.load", return_value=mock_parsed):
            result = tgwrapper._parse_tg_dependencies(tmpdir)

        # Check dependencies
        assert "vpc" in result["dependencies"]
        assert result["dependencies"]["vpc"] == os.path.normpath(
            os.path.join(tmpdir, "../vpc")
        )
        assert "rds" in result["dependencies"]

        # Check dep_inputs
        assert "vpc_id" in result["dep_inputs"]
        assert result["dep_inputs"]["vpc_id"]["dep_name"] == "vpc"
        assert result["dep_inputs"]["vpc_id"]["output_key"] == "vpc_id"
        assert "db_host" in result["dep_inputs"]
        assert result["dep_inputs"]["db_host"]["dep_name"] == "rds"
        assert result["dep_inputs"]["db_host"]["output_key"] == "endpoint"

        # Static values should not appear in dep_inputs
        assert "static_val" not in result["dep_inputs"]

    def test_missing_terragrunt_hcl_returns_empty(self, tmpdir):
        """Returns empty dicts when no terragrunt.hcl exists."""
        result = tgwrapper._parse_tg_dependencies(tmpdir)
        assert result == {"dependencies": {}, "dep_inputs": {}}

    def test_no_dependency_blocks(self, tmpdir):
        """HCL file without dependency blocks returns empty dependencies."""
        with open(os.path.join(tmpdir, "terragrunt.hcl"), "w") as f:
            f.write("placeholder")

        mock_parsed = {
            "inputs": [{"region": "us-east-1"}],
        }

        with patch("modules.tgwrapper.hcl2.load", return_value=mock_parsed):
            result = tgwrapper._parse_tg_dependencies(tmpdir)
        assert result["dependencies"] == {}
        assert result["dep_inputs"] == {}

    def test_malformed_hcl_returns_empty(self, tmpdir):
        """Malformed HCL file returns empty result without raising."""
        with open(os.path.join(tmpdir, "terragrunt.hcl"), "w") as f:
            f.write("this is not { valid hcl {{{{")

        result = tgwrapper._parse_tg_dependencies(tmpdir)
        assert result == {"dependencies": {}, "dep_inputs": {}}

    def test_dependency_without_config_path(self, tmpdir):
        """Dependency block missing config_path still produces an entry."""
        with open(os.path.join(tmpdir, "terragrunt.hcl"), "w") as f:
            f.write("placeholder")

        mock_parsed = {
            "dependency": [
                {"vpc": {"enabled": True}},  # No config_path
            ],
        }

        with patch("modules.tgwrapper.hcl2.load", return_value=mock_parsed):
            result = tgwrapper._parse_tg_dependencies(tmpdir)
        # config_path defaults to "" -> normpath resolves to tmpdir itself
        assert "vpc" in result["dependencies"]

    def test_inputs_without_dependency_refs(self, tmpdir):
        """Inputs that don't reference dependencies produce no dep_inputs."""
        with open(os.path.join(tmpdir, "terragrunt.hcl"), "w") as f:
            f.write("placeholder")

        mock_parsed = {
            "inputs": [
                {
                    "region": "us-east-1",
                    "env": "prod",
                }
            ],
        }

        with patch("modules.tgwrapper.hcl2.load", return_value=mock_parsed):
            result = tgwrapper._parse_tg_dependencies(tmpdir)
        assert result["dep_inputs"] == {}


class TestInjectDependencyRefs:
    """Tests for _inject_dependency_refs()."""

    def test_adds_edge_from_consumer_to_producer(self, tmpdir):
        """Consumer resources get a graphdict edge to the matched producer resource."""
        source_root = tmpdir
        vpc_dir = os.path.join(tmpdir, "vpc")
        app_dir = os.path.join(tmpdir, "app")
        os.makedirs(vpc_dir, exist_ok=True)
        os.makedirs(app_dir, exist_ok=True)

        merged_tfdata = {
            "graphdict": {
                "module.app.aws_instance.web": [],
                "module.vpc.aws_vpc.main": [],
            },
        }

        per_module_deps = {
            "app": {
                "dependencies": {"vpc": vpc_dir},
                "dep_inputs": {
                    "vpc_id": {"dep_name": "vpc", "output_key": "vpc_id"},
                },
            },
        }

        per_module_resources = {
            "vpc": [
                {
                    "address": "module.vpc.aws_vpc.main",
                    "type": "aws_vpc",
                    "mode": "managed",
                },
            ],
        }

        result = tgwrapper._inject_dependency_refs(
            merged_tfdata, per_module_deps, per_module_resources, source_root
        )

        assert (
            "module.vpc.aws_vpc.main"
            in result["graphdict"]["module.app.aws_instance.web"]
        )

    def test_no_matching_producer_leaves_graphdict_unchanged(self, tmpdir):
        """When producer has no matching resource, no edges are added."""
        source_root = tmpdir
        vpc_dir = os.path.join(tmpdir, "vpc")
        os.makedirs(vpc_dir, exist_ok=True)

        merged_tfdata = {
            "graphdict": {
                "module.app.aws_instance.web": [],
            },
        }

        per_module_deps = {
            "app": {
                "dependencies": {"vpc": vpc_dir},
                "dep_inputs": {
                    "vpc_id": {"dep_name": "vpc", "output_key": "vpc_id"},
                },
            },
        }

        per_module_resources = {"vpc": [], "app": []}

        result = tgwrapper._inject_dependency_refs(
            merged_tfdata, per_module_deps, per_module_resources, source_root
        )
        assert result["graphdict"]["module.app.aws_instance.web"] == []

    def test_missing_dependency_name_skipped(self, tmpdir):
        """When dep_name references a dependency not in the dependencies dict, skip."""
        source_root = tmpdir

        merged_tfdata = {
            "graphdict": {
                "module.app.aws_instance.web": [],
            },
        }

        per_module_deps = {
            "app": {
                "dependencies": {},
                "dep_inputs": {
                    "db_host": {"dep_name": "rds", "output_key": "endpoint"},
                },
            },
        }

        per_module_resources = {}

        result = tgwrapper._inject_dependency_refs(
            merged_tfdata, per_module_deps, per_module_resources, source_root
        )
        assert result["graphdict"]["module.app.aws_instance.web"] == []

    def test_multiple_consumers_get_edges(self, tmpdir):
        """Multiple consumer modules each get edges to the producer."""
        source_root = tmpdir
        vpc_dir = os.path.join(tmpdir, "vpc")
        app_dir = os.path.join(tmpdir, "app")
        api_dir = os.path.join(tmpdir, "api")
        os.makedirs(vpc_dir, exist_ok=True)
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(api_dir, exist_ok=True)

        merged_tfdata = {
            "graphdict": {
                "module.app.aws_instance.web": [],
                "module.api.aws_lambda_function.handler": [],
                "module.vpc.aws_vpc.main": [],
            },
        }

        per_module_deps = {
            "app": {
                "dependencies": {"vpc": vpc_dir},
                "dep_inputs": {
                    "vpc_id": {"dep_name": "vpc", "output_key": "vpc_id"},
                },
            },
            "api": {
                "dependencies": {"vpc": vpc_dir},
                "dep_inputs": {
                    "vpc_id": {"dep_name": "vpc", "output_key": "vpc_id"},
                },
            },
        }

        per_module_resources = {
            "vpc": [
                {
                    "address": "module.vpc.aws_vpc.main",
                    "type": "aws_vpc",
                    "mode": "managed",
                },
            ],
        }

        result = tgwrapper._inject_dependency_refs(
            merged_tfdata, per_module_deps, per_module_resources, source_root
        )

        assert (
            "module.vpc.aws_vpc.main"
            in result["graphdict"]["module.app.aws_instance.web"]
        )
        assert (
            "module.vpc.aws_vpc.main"
            in result["graphdict"]["module.api.aws_lambda_function.handler"]
        )


class TestTgRunAllPlan:
    """Integration tests for tg_run_all_plan() — requires Terragrunt installed."""

    @pytest.mark.slow
    def test_multi_module_produces_merged_tfdata(self):
        """tg_run_all_plan on multi-module fixture returns merged tfdata with cross-module edges."""
        tfdata = tgwrapper.tg_run_all_plan(
            MULTI_FIXTURE, varfile=[], workspace="default", debug=False, upgrade=False
        )
        assert tfdata["is_terragrunt"] is True
        # Should have resources from both vpc and app modules
        addresses = [rc["address"] for rc in tfdata["tf_resources_created"]]
        has_vpc = any("aws_vpc" in a for a in addresses)
        has_instance = any("aws_instance" in a for a in addresses)
        assert has_vpc, f"Expected aws_vpc in {addresses}"
        assert has_instance, f"Expected aws_instance in {addresses}"
        # All addresses should be prefixed with module.<name>.
        for addr in addresses:
            assert addr.startswith("module."), f"Expected module prefix on {addr}"
        # Verify override files were cleaned up
        for subdir in ["vpc", "app"]:
            override = os.path.join(MULTI_FIXTURE, subdir, "terravision_override.tf")
            assert not os.path.exists(override), f"Override not cleaned up in {subdir}"
