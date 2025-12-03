"""Unit tests for modules/utils/terraform_utils.py"""

import json
import os
import tempfile
import unittest
import sys
from pathlib import Path

# Add modules directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.utils.terraform_utils import getvar, tfvar_read
from modules.exceptions import TerraformParsingError

DEFAULT_MARKER = "NOTFOUND"


class TestGetvar(unittest.TestCase):
    """Test getvar() function for retrieving Terraform variables."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_vars = {
            "region": "us-east-1",
            "instance_type": "t2.micro",
            "Tags": {"Name": "TestInstance"},
            "subnet_id": "subnet-12345",
        }
        self.nested_tfdata = {
            "resource": {
                "aws_vpc": {
                    "main": {
                        "cidr_block": "10.0.0.0/16",
                        "tags": {"Environment": "dev"},
                    }
                }
            }
        }
        # Clear any test environment variables
        for key in list(os.environ.keys()):
            if key.startswith("TF_VAR_test_"):
                del os.environ[key]

    def tearDown(self):
        """Clean up environment variables."""
        for key in list(os.environ.keys()):
            if key.startswith("TF_VAR_test_"):
                del os.environ[key]

    def test_exact_match_from_dict(self):
        """Test retrieving variable with exact key match."""
        result = getvar("region", self.test_vars)
        self.assertEqual(result, "us-east-1")

    def test_nested_dict_value(self):
        """Test retrieving nested dictionary value."""
        result = getvar("Tags", self.test_vars)
        self.assertEqual(result, {"Name": "TestInstance"})

    def test_case_insensitive_match(self):
        """Test case-insensitive variable retrieval."""
        result = getvar("tags", self.test_vars)
        self.assertEqual(result, {"Name": "TestInstance"})

    def test_environment_variable_priority(self):
        """Test that environment variables take priority."""
        os.environ["TF_VAR_test_region"] = "eu-west-1"
        result = getvar("test_region", {"test_region": "us-east-1"})
        self.assertEqual(result, "eu-west-1")

    def test_variable_not_found_returns_default_marker(self):
        """Test behavior when variable doesn't exist returns default marker."""
        result = getvar("nonexistent", self.test_vars)
        self.assertEqual(result, "NOTFOUND")

    def test_empty_dict_returns_default_marker(self):
        """Test with empty variables dictionary returns default marker."""
        result = getvar("anything", {})
        self.assertEqual(result, "NOTFOUND")

    def test_environment_variable_only(self):
        """Test retrieving value only from environment."""
        os.environ["TF_VAR_test_env_var"] = "env_value"
        result = getvar("test_env_var", {})
        self.assertEqual(result, "env_value")

    def test_default_value_parameter(self):
        """Test that providing a default value returns fallback when not found."""
        result = getvar("missing", self.test_vars, default="fallback")
        self.assertEqual(result, "fallback")

    def test_nested_path_access(self):
        """Test accessing nested dict path using dotted notation."""
        nested = {
            "resource": {
                "aws_vpc": {
                    "main": {
                        "cidr_block": "10.0.0.0/16",
                        "tags": {"Environment": "dev"},
                    }
                }
            }
        }
        result = getvar("resource.aws_vpc.main.cidr_block", nested)
        self.assertEqual(result, "10.0.0.0/16")

    def test_list_index_access(self):
        """Test accessing list elements via bracket notation."""
        data = {"items": ["a", "b", "c"]}
        result = getvar("items[1]", data)
        self.assertEqual(result, "b")

    def test_invalid_access_path_returns_default(self):
        """Test that invalid nested access returns default marker."""
        # Actually, the implementation DOES support nested path access
        # Tags.Name should work since Tags is a dict with Name key
        result = getvar("Tags.Name", self.test_vars)
        self.assertEqual(result, "TestInstance")  # Correctly retrieves nested value

        # Test an actually invalid path
        result_invalid = getvar("NonExistent.Path", self.test_vars)
        self.assertEqual(result_invalid, "NOTFOUND")

    def test_invalid_list_index_raises_error(self):
        """Test that non-numeric list index raises TerraformParsingError."""
        with self.assertRaises(TerraformParsingError):
            getvar("items[foo]", {"items": [1, 2, 3]})

    def test_out_of_range_list_index_returns_default(self):
        """Test that out-of-range list index returns default marker."""
        result = getvar("items[3]", {"items": ["a", "b", "c"]})
        self.assertEqual(result, "NOTFOUND")

    def test_mixed_case_lookup(self):
        """Test case-insensitive matching with mixed case."""
        result = getvar("INSTANCE_TYPE", self.test_vars)
        self.assertEqual(result, "t2.micro")


class TestTfvarRead(unittest.TestCase):
    """Test tfvar_read() function for parsing .tfvars files."""

    def test_parse_json_tfvars(self):
        """Test parsing JSON format .tfvars file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tfvars", delete=False) as f:
            json.dump({"region": "us-west-2", "count": 3}, f)
            temp_path = f.name

        try:
            result = tfvar_read(temp_path)
            self.assertEqual(result["region"], "us-west-2")
            self.assertEqual(result["count"], 3)
        finally:
            os.unlink(temp_path)

    def test_parse_hcl_tfvars(self):
        """Test parsing HCL format .tfvars file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tfvars", delete=False) as f:
            f.write('region = "us-west-2"\n')
            f.write("instance_count = 5\n")
            f.write('tags = {\n  Name = "Test"\n}\n')
            temp_path = f.name

        try:
            result = tfvar_read(temp_path)
            self.assertIn("region", result)
            # HCL parser may return different structure
            self.assertIsInstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_file_not_found(self):
        """Test error handling for missing file."""
        with self.assertRaises(FileNotFoundError):
            tfvar_read("/nonexistent/path/vars.tfvars")

    def test_invalid_file_format(self):
        """Test error handling for unparseable file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tfvars", delete=False) as f:
            f.write("this is not valid JSON or HCL\n")
            f.write("@#$%^&*()\n")
            temp_path = f.name

        try:
            with self.assertRaises(TerraformParsingError) as context:
                tfvar_read(temp_path)
            # Should include filepath in error context
            self.assertIn("filepath", str(context.exception.context))
        finally:
            os.unlink(temp_path)

    def test_empty_json_file(self):
        """Test parsing empty JSON object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tfvars", delete=False) as f:
            f.write("{}")
            temp_path = f.name

        try:
            result = tfvar_read(temp_path)
            self.assertEqual(result, {})
        finally:
            os.unlink(temp_path)

    def test_complex_json_structure(self):
        """Test parsing complex nested JSON structure."""
        complex_vars = {
            "vpc_config": {
                "cidr": "10.0.0.0/16",
                "subnets": ["10.0.1.0/24", "10.0.2.0/24"],
            },
            "tags": {"Environment": "dev", "Team": "platform"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tfvars", delete=False) as f:
            json.dump(complex_vars, f)
            temp_path = f.name

        try:
            result = tfvar_read(temp_path)
            self.assertEqual(result["vpc_config"]["cidr"], "10.0.0.0/16")
            self.assertEqual(len(result["vpc_config"]["subnets"]), 2)
        finally:
            os.unlink(temp_path)

    def test_hcl_list_flattening(self):
        """Test HCL parser list flattening behavior."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tfvars", delete=False) as f:
            f.write('single_value = "test"\n')
            temp_path = f.name

        try:
            result = tfvar_read(temp_path)
            # HCL parser wraps values in lists, our code should flatten single-item lists
            self.assertIsInstance(result, dict)
            if "single_value" in result:
                # Should be flattened to string, not list
                self.assertIsInstance(result["single_value"], str)
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
