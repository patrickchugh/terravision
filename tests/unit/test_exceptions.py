"""Unit tests for custom exception types."""

import unittest
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.exceptions import (
    TerraVisionError,
    MissingResourceError,
    ProviderDetectionError,
    MetadataInconsistencyError,
    TerraformParsingError,
)


class TestTerraVisionError(unittest.TestCase):
    """Test base TerraVisionError exception class."""

    def test_basic_error_message(self):
        """Test error with message only."""
        error = TerraVisionError("Test error message")
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.context, {})
        self.assertEqual(str(error), "Test error message")

    def test_error_with_context(self):
        """Test error with contextual information."""
        context = {"resource_id": "aws_vpc.main", "line_number": 42}
        error = TerraVisionError("Configuration error", context=context)

        self.assertEqual(error.message, "Configuration error")
        self.assertEqual(error.context, context)
        self.assertIn("resource_id=aws_vpc.main", str(error))
        self.assertIn("line_number=42", str(error))

    def test_error_inheritance(self):
        """Test that TerraVisionError inherits from Exception."""
        error = TerraVisionError("Test")
        self.assertIsInstance(error, Exception)


class TestMissingResourceError(unittest.TestCase):
    """Test MissingResourceError exception class."""

    def test_missing_resource_basic(self):
        """Test basic missing resource error."""
        error = MissingResourceError("VPC not found")
        self.assertEqual(error.message, "VPC not found")
        self.assertIsInstance(error, TerraVisionError)

    def test_missing_resource_with_context(self):
        """Test missing resource with context."""
        context = {
            "required_type": "aws_vpc",
            "dependent_resource": "aws_vpc_endpoint.s3",
        }
        error = MissingResourceError("No VPCs found for endpoints", context=context)

        self.assertEqual(error.context["required_type"], "aws_vpc")
        self.assertIn("aws_vpc_endpoint.s3", str(error))


class TestProviderDetectionError(unittest.TestCase):
    """Test ProviderDetectionError exception class."""

    def test_provider_detection_basic(self):
        """Test basic provider detection error."""
        error = ProviderDetectionError("Cannot detect provider")
        self.assertIsInstance(error, TerraVisionError)

    def test_mixed_providers(self):
        """Test error for mixed provider configurations."""
        context = {
            "providers": ["aws", "azurerm", "google"],
            "resources": ["aws_instance.web", "azurerm_virtual_machine.app"],
        }
        error = ProviderDetectionError("Mixed providers detected", context=context)

        self.assertIn("aws", str(error))
        self.assertIn("azurerm", str(error))


class TestMetadataInconsistencyError(unittest.TestCase):
    """Test MetadataInconsistencyError exception class."""

    def test_metadata_inconsistency_basic(self):
        """Test basic metadata inconsistency error."""
        error = MetadataInconsistencyError("Missing metadata key")
        self.assertIsInstance(error, TerraVisionError)

    def test_metadata_validation_failure(self):
        """Test metadata validation failure with details."""
        context = {
            "resource_id": "aws_instance.web",
            "missing_keys": ["name", "type"],
        }
        error = MetadataInconsistencyError(
            "Required metadata keys missing", context=context
        )

        self.assertEqual(error.context["resource_id"], "aws_instance.web")
        self.assertIn("name", str(error))


class TestTerraformParsingError(unittest.TestCase):
    """Test TerraformParsingError exception class."""

    def test_parsing_error_basic(self):
        """Test basic parsing error."""
        error = TerraformParsingError("Failed to parse HCL")
        self.assertIsInstance(error, TerraVisionError)

    def test_parsing_error_with_file_context(self):
        """Test parsing error with file and line information."""
        context = {
            "filepath": "/path/to/main.tf",
            "line": 15,
            "error": "Unexpected token",
        }
        error = TerraformParsingError("Syntax error in Terraform file", context=context)

        self.assertIn("main.tf", str(error))
        self.assertIn("15", str(error))


if __name__ == "__main__":
    unittest.main()
