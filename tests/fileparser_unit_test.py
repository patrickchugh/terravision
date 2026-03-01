import unittest, sys, os
from unittest.mock import patch, MagicMock, mock_open
import tempfile

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.fileparser import (
    handle_module,
    _load_terraform_modules_json,
)


class TestHandleModule(unittest.TestCase):
    def test_handle_module_local_source(self):
        modules_list = [{"test_module": {"source": "./local/path"}}]
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertIn("tf_file_paths", result)
        self.assertIn("module_source_dict", result)
        self.assertIn("test_module", result["module_source_dict"])

    def test_handle_module_remote_source(self):
        modules_list = [{"test_module": {"source": "terraform-aws-modules/vpc/aws"}}]
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertIn("test_module", result["module_source_dict"])
        self.assertIn("cache_path", result["module_source_dict"]["test_module"])

    def test_handle_module_empty_list(self):
        modules_list = []
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertEqual(len(result["module_source_dict"]), 0)

    def test_handle_module_multiple_modules(self):
        modules_list = [
            {"module1": {"source": "./path1"}},
            {"module2": {"source": "./path2"}},
        ]
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertEqual(len(result["module_source_dict"]), 2)


class TestLoadTerraformModulesJson(unittest.TestCase):
    """Tests for _load_terraform_modules_json()."""

    def test_valid_modules_json(self):
        """Test loading the real modules.json fixture."""
        fixtures_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "aws_terraform", "module_sources"
        )
        result = _load_terraform_modules_json(fixtures_dir)
        # Should have entries (root module with empty key is excluded)
        self.assertGreater(len(result), 0)
        # Check a known module
        self.assertIn("registry_vpc", result)
        self.assertTrue(os.path.isabs(result["registry_vpc"]))
        self.assertTrue(
            result["registry_vpc"].endswith(".terraform/modules/registry_vpc")
        )

    def test_modules_json_resolves_relative_paths(self):
        """Test that relative Dir paths are resolved to absolute paths."""
        fixtures_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "aws_terraform", "module_sources"
        )
        result = _load_terraform_modules_json(fixtures_dir)
        for key, path in result.items():
            self.assertTrue(
                os.path.isabs(path), f"Module '{key}' path is not absolute: {path}"
            )

    def test_missing_modules_json(self):
        """Test with a directory that has no .terraform/modules/modules.json."""
        result = _load_terraform_modules_json("/tmp/nonexistent_dir_12345")
        self.assertEqual(result, {})

    def test_malformed_json(self):
        """Test with malformed JSON content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modules_dir = os.path.join(tmpdir, ".terraform", "modules")
            os.makedirs(modules_dir)
            with open(os.path.join(modules_dir, "modules.json"), "w") as f:
                f.write("not valid json{{{")
            result = _load_terraform_modules_json(tmpdir)
            self.assertEqual(result, {})

    def test_empty_key_excluded(self):
        """Test that the root module (empty Key) is excluded."""
        fixtures_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "aws_terraform", "module_sources"
        )
        result = _load_terraform_modules_json(fixtures_dir)
        self.assertNotIn("", result)

    def test_subfolder_modules_resolved(self):
        """Test modules with subfolder paths (e.g., .terraform/modules/X/modules/Y)."""
        fixtures_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "aws_terraform", "module_sources"
        )
        result = _load_terraform_modules_json(fixtures_dir)
        # git_https_iam_account_ref has Dir: .terraform/modules/git_https_iam_account_ref/modules/iam-account
        self.assertIn("git_https_iam_account_ref", result)
        self.assertTrue(
            result["git_https_iam_account_ref"].endswith("modules/iam-account")
        )


if __name__ == "__main__":
    unittest.main(exit=False)
