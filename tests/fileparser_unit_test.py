import json
import unittest, sys, os
from unittest.mock import patch, MagicMock, mock_open
import tempfile

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.fileparser import (
    handle_module,
    _load_terraform_modules_json,
    _extract_comments_from_tf,
)


class TestExtractCommentsFromTf(unittest.TestCase):
    """Verify the regex-based comment harvester used to feed the LLM
    annotation context block."""

    def test_associates_comments_directly_above_resource(self):
        content = (
            "# Processes incoming order events from SQS\n"
            "# and writes finalized records to DynamoDB\n"
            'resource "aws_lambda_function" "api" {\n'
            '  runtime = "python3.11"\n'
            "}\n"
        )
        per_resource, unattached = _extract_comments_from_tf(content)
        self.assertIn("aws_lambda_function.api", per_resource)
        self.assertIn(
            "Processes incoming order events from SQS",
            per_resource["aws_lambda_function.api"],
        )
        self.assertIn(
            "writes finalized records to DynamoDB",
            per_resource["aws_lambda_function.api"],
        )
        self.assertEqual(unattached, [])

    def test_blank_line_between_comment_and_resource_is_tolerated(self):
        content = (
            "# Stores order records with a 30 day TTL\n"
            "\n"
            'resource "aws_dynamodb_table" "orders" {\n'
            '  hash_key = "id"\n'
            "}\n"
        )
        per_resource, _ = _extract_comments_from_tf(content)
        self.assertIn("aws_dynamodb_table.orders", per_resource)
        self.assertIn("30 day TTL", per_resource["aws_dynamodb_table.orders"])

    def test_supports_double_slash_comments(self):
        content = (
            "// Reads database credentials\n"
            'resource "aws_secretsmanager_secret" "db_creds" {\n'
            '  name = "prod/db"\n'
            "}\n"
        )
        per_resource, _ = _extract_comments_from_tf(content)
        self.assertIn("aws_secretsmanager_secret.db_creds", per_resource)
        self.assertIn(
            "Reads database credentials",
            per_resource["aws_secretsmanager_secret.db_creds"],
        )

    def test_unattached_comments_collected_separately(self):
        content = (
            "# Order processing stack — payments team\n"
            "# Owned by team-payments@example.com\n"
            "\n"
            "locals {\n"
            '  env = "prod"\n'
            "}\n"
        )
        per_resource, unattached = _extract_comments_from_tf(content)
        self.assertEqual(per_resource, {})
        self.assertIn("Order processing stack — payments team", unattached)
        self.assertIn("Owned by team-payments@example.com", unattached)

    def test_first_resource_block_wins_for_duplicate_keys(self):
        """A second declaration of the same logical key (e.g. count
        expansion across files) should not overwrite the first
        documentation block."""
        content = (
            "# Original explanation\n"
            'resource "aws_s3_bucket" "logs" {}\n'
            "# Later, less useful note\n"
            'resource "aws_s3_bucket" "logs" {}\n'
        )
        per_resource, _ = _extract_comments_from_tf(content)
        self.assertEqual(per_resource["aws_s3_bucket.logs"], "Original explanation")

    def test_long_comment_block_is_truncated(self):
        long_text = "x " * 400
        content = f'# {long_text}\nresource "aws_lambda_function" "api" {{}}\n'
        per_resource, _ = _extract_comments_from_tf(content, max_chars_per_resource=200)
        self.assertTrue(per_resource["aws_lambda_function.api"].endswith("..."))
        self.assertLessEqual(len(per_resource["aws_lambda_function.api"]), 203)

    def test_intervening_code_drains_pending_to_unattached(self):
        """If a comment block is followed by a non-resource code line
        (e.g. a variable declaration), the comments should NOT be
        misattributed to the resource that comes after."""
        content = (
            "# Tuning notes for the queue\n"
            'variable "queue_depth" { default = 100 }\n'
            "\n"
            'resource "aws_sqs_queue" "events" {}\n'
        )
        per_resource, unattached = _extract_comments_from_tf(content)
        self.assertNotIn("aws_sqs_queue.events", per_resource)
        self.assertIn("Tuning notes for the queue", unattached)


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

    SAMPLE_MODULES_JSON = json.dumps(
        {
            "Modules": [
                {"Key": "", "Source": "", "Dir": "."},
                {
                    "Key": "registry_vpc",
                    "Source": "registry.terraform.io/terraform-aws-modules/vpc/aws",
                    "Version": "5.1.0",
                    "Dir": ".terraform/modules/registry_vpc",
                },
                {
                    "Key": "git_https_iam_account_ref",
                    "Source": "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-account?ref=v5.30.0",
                    "Dir": ".terraform/modules/git_https_iam_account_ref/modules/iam-account",
                },
                {
                    "Key": "local_vpc",
                    "Source": "./modules/local_vpc",
                    "Dir": "modules/local_vpc",
                },
            ]
        }
    )

    def setUp(self):
        self._orig_tf_data_dir = os.environ.pop("TF_DATA_DIR", None)
        self._tmpdir = tempfile.TemporaryDirectory()
        modules_dir = os.path.join(self._tmpdir.name, ".terraform", "modules")
        os.makedirs(modules_dir)
        with open(os.path.join(modules_dir, "modules.json"), "w") as f:
            f.write(self.SAMPLE_MODULES_JSON)

    def tearDown(self):
        self._tmpdir.cleanup()
        if self._orig_tf_data_dir is not None:
            os.environ["TF_DATA_DIR"] = self._orig_tf_data_dir

    def test_valid_modules_json(self):
        """Test loading modules.json returns expected modules."""
        result = _load_terraform_modules_json(self._tmpdir.name)
        self.assertGreater(len(result), 0)
        self.assertIn("registry_vpc", result)
        self.assertTrue(os.path.isabs(result["registry_vpc"]))
        self.assertTrue(
            result["registry_vpc"].endswith(".terraform/modules/registry_vpc")
        )

    def test_modules_json_resolves_relative_paths(self):
        """Test that relative Dir paths are resolved to absolute paths."""
        result = _load_terraform_modules_json(self._tmpdir.name)
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
        result = _load_terraform_modules_json(self._tmpdir.name)
        self.assertNotIn("", result)

    def test_subfolder_modules_resolved(self):
        """Test modules with subfolder paths (e.g., .terraform/modules/X/modules/Y)."""
        result = _load_terraform_modules_json(self._tmpdir.name)
        self.assertIn("git_https_iam_account_ref", result)
        self.assertTrue(
            result["git_https_iam_account_ref"].endswith("modules/iam-account")
        )


if __name__ == "__main__":
    unittest.main(exit=False)
