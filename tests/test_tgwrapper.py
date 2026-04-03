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
INCLUDES_FIXTURE = os.path.join(FIXTURES_DIR, "terragrunt-includes")
REMOTE_STATE_FIXTURE = os.path.join(FIXTURES_DIR, "terragrunt-remote-state")


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
        codepath, override_files = tgwrapper._prepare_tg_source(tmpdir)
        assert codepath == os.path.abspath(tmpdir)
        assert len(override_files) >= 1
        assert override_files[0] == os.path.join(codepath, "terravision_override.tf")
        assert os.path.isfile(override_files[0])
        for f in override_files:
            os.remove(f)

    def test_override_contains_local_backend(self, tmpdir):
        """The written override file forces local backend."""
        _, override_files = tgwrapper._prepare_tg_source(tmpdir)
        with open(override_files[0]) as f:
            content = f.read()
        assert "local" in content
        assert "backend" in content
        for f in override_files:
            os.remove(f)

    def test_codepath_is_absolute(self, tmpdir):
        """Returned codepath is always absolute."""
        codepath, override_files = tgwrapper._prepare_tg_source(tmpdir)
        assert os.path.isabs(codepath)
        for f in override_files:
            os.remove(f)

    def test_writes_override_to_dependency_dirs(self, tmpdir):
        """_prepare_tg_source writes overrides to dependency module dirs too."""
        # Create dependency directory
        dep_dir = os.path.join(str(tmpdir), "dep_vpc")
        os.makedirs(dep_dir)
        # Create terragrunt.hcl with a dependency block
        tg_content = (
            'dependency "vpc" {\n'
            '  config_path = "./dep_vpc"\n'
            "  mock_outputs = {\n"
            '    vpc_id = "vpc-mock"\n'
            "  }\n"
            "}\n"
        )
        with open(os.path.join(str(tmpdir), "terragrunt.hcl"), "w") as f:
            f.write(tg_content)
        codepath, override_files = tgwrapper._prepare_tg_source(str(tmpdir))
        # Should have overrides in both main dir and dependency dir
        assert len(override_files) == 2
        assert os.path.isfile(os.path.join(dep_dir, "terravision_override.tf"))
        for f in override_files:
            os.remove(f)


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


class TestTgIntegration:
    """Single comprehensive integration test for Terragrunt.

    Tests real-world patterns from issue #114 in one test to minimize CI time.
    Covers: includes, find_in_parent_folders, remote git sources, local sources,
    cross-module dependencies, mock_outputs, single-module and multi-module modes,
    backend override, codepath resolution, and override cleanup.
    """

    @pytest.mark.slow
    def test_terragrunt_full_pipeline(self):
        """Comprehensive test of all Terragrunt scenarios."""
        # Clean all caches
        for fixture_dir in [INCLUDES_FIXTURE, REMOTE_STATE_FIXTURE]:
            for root, dirs, _ in os.walk(fixture_dir):
                dirs[:] = [d for d in dirs if d != ".git"]
                for d in list(dirs):
                    if d == ".terragrunt-cache":
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                        dirs.remove(d)

        # --- Test 1: Single module with remote source and includes ---
        vpc_path = os.path.join(
            INCLUDES_FIXTURE, "staging", "us-east-1", "networking", "vpc"
        )
        tfdata = tgwrapper.tg_initplan(
            vpc_path, varfile=[], workspace="default", debug=False, upgrade=False
        )
        assert tfdata["is_terragrunt"] is True
        types = {rc.get("type", "") for rc in tfdata["tf_resources_created"]}
        assert "aws_vpc" in types, f"Expected aws_vpc in {types}"
        # codepath should point to cache dir with .tf files
        assert ".terragrunt-cache" in tfdata["codepath"]
        tf_files = [f for f in os.listdir(tfdata["codepath"]) if f.endswith(".tf")]
        assert len(tf_files) > 0, f"No .tf files in codepath: {tfdata['codepath']}"
        # No override leak
        assert not os.path.exists(os.path.join(vpc_path, "terravision_override.tf"))

        # --- Test 2: Single module with dependency (remote source) ---
        rds_path = os.path.join(
            INCLUDES_FIXTURE, "staging", "us-east-1", "data-stores", "rds"
        )
        tfdata = tgwrapper.tg_initplan(
            rds_path, varfile=[], workspace="default", debug=False, upgrade=False
        )
        types = {rc.get("type", "") for rc in tfdata["tf_resources_created"]}
        assert (
            "aws_db_subnet_group" in types
        ), f"Expected aws_db_subnet_group in {types}"
        assert ".terragrunt-cache" in tfdata["codepath"]
        # No override leak on either module or dependency
        assert not os.path.exists(os.path.join(rds_path, "terravision_override.tf"))
        assert not os.path.exists(os.path.join(vpc_path, "terravision_override.tf"))

        # --- Test 3: Multi-module with remote sources ---
        staging_path = os.path.join(INCLUDES_FIXTURE, "staging")
        tfdata = tgwrapper.tg_run_all_plan(
            staging_path, varfile=[], workspace="default", debug=False, upgrade=False
        )
        addresses = [rc["address"] for rc in tfdata["tf_resources_created"]]
        assert any("aws_vpc" in a for a in addresses), f"No vpc in {addresses}"
        assert any("aws_db" in a for a in addresses), f"No rds in {addresses}"
        for addr in addresses:
            assert addr.startswith("module."), f"Missing module prefix: {addr}"
        # codepath should be a list of cache directories
        assert isinstance(tfdata["codepath"], list)
        for cp in tfdata["codepath"]:
            assert ".terragrunt-cache" in cp
            assert any(f.endswith(".tf") for f in os.listdir(cp))
        # Override cleanup
        for dirpath, dirs, _ in os.walk(staging_path):
            dirs[:] = [d for d in dirs if d != ".terragrunt-cache"]
            assert not os.path.exists(
                os.path.join(dirpath, "terravision_override.tf")
            ), f"Override leak in {dirpath}"
