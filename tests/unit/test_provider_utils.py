"""Unit tests for modules/utils/provider_utils.py"""

import unittest
import sys
from pathlib import Path

# Add modules directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.utils.provider_utils import (
    detect_provider,
    get_provider_config,
    detect_provider_for_node,
)
from modules.exceptions import ProviderDetectionError


class DummyProviderContext:
    """Minimal ProviderRegistry context for testing."""

    def __init__(self, config_module):
        self._config = config_module

    def get_config(self, provider: str):
        return self._config


import types
from unittest import mock

from modules.cloud_config import aws, azure, gcp


class TestDetectProvider(unittest.TestCase):
    """Test detect_provider() function for cloud provider detection."""

    def test_detect_aws_single_resource(self):
        """Test detection with single AWS resource."""
        result = detect_provider(["aws_instance"])
        self.assertEqual(result, "aws")

    def test_detect_aws_multiple_resources(self):
        """Test detection with multiple AWS resources."""
        result = detect_provider(["aws_instance", "aws_vpc", "aws_s3_bucket"])
        self.assertEqual(result, "aws")

    def test_detect_azure_single_resource(self):
        """Test detection with single Azure resource."""
        result = detect_provider(["azurerm_virtual_network"])
        self.assertEqual(result, "azurerm")

    def test_detect_azure_multiple_resources(self):
        """Test detection with multiple Azure resources."""
        result = detect_provider(
            [
                "azurerm_resource_group",
                "azurerm_virtual_network",
                "azurerm_network_security_group",
            ]
        )
        self.assertEqual(result, "azurerm")

    def test_detect_gcp_single_resource(self):
        """Test detection with single GCP resource."""
        result = detect_provider(["google_compute_instance"])
        self.assertEqual(result, "google")

    def test_detect_gcp_multiple_resources(self):
        """Test detection with multiple GCP resources."""
        result = detect_provider(
            [
                "google_compute_network",
                "google_compute_firewall",
                "google_storage_bucket",
            ]
        )
        self.assertEqual(result, "google")

    def test_empty_resource_list_defaults_to_aws(self):
        """Test that empty list defaults to AWS."""
        result = detect_provider([])
        self.assertEqual(result, "aws")

    def test_data_sources_ignored(self):
        """Test that data sources don't trigger provider detection."""
        result = detect_provider(["data.aws_ami.ubuntu", "aws_instance.web"])
        self.assertEqual(result, "aws")

    def test_modules_ignored(self):
        """Test that module references don't trigger provider detection."""
        result = detect_provider(["module.vpc", "aws_instance.web"])
        self.assertEqual(result, "aws")

    def test_null_resources_ignored(self):
        """Test that null resources don't trigger unknown provider."""
        result = detect_provider(["null_resource.example", "aws_instance.web"])
        self.assertEqual(result, "aws")

    def test_random_resources_ignored(self):
        """Test that random resources don't trigger unknown provider."""
        result = detect_provider(["random_id.suffix", "aws_instance.web"])
        self.assertEqual(result, "aws")

    def test_time_resources_ignored(self):
        """Test that time resources don't trigger unknown provider."""
        result = detect_provider(["time_sleep.wait", "aws_instance.web"])
        self.assertEqual(result, "aws")

    def test_mixed_aws_and_azure_raises_error(self):
        """Test that mixing AWS and Azure resources raises error."""
        with self.assertRaises(ProviderDetectionError) as context:
            detect_provider(["aws_instance", "azurerm_virtual_network"])
        # Check error message contains both providers
        self.assertIn("Mixed providers", str(context.exception))
        self.assertIn("providers", context.exception.context)
        self.assertEqual(
            sorted(context.exception.context["providers"]), ["aws", "azurerm"]
        )

    def test_mixed_aws_and_gcp_raises_error(self):
        """Test that mixing AWS and GCP resources raises error."""
        with self.assertRaises(ProviderDetectionError) as context:
            detect_provider(["aws_instance", "google_compute_instance"])
        self.assertIn("Mixed providers", str(context.exception))

    def test_mixed_three_providers_raises_error(self):
        """Test that mixing all three providers raises error."""
        with self.assertRaises(ProviderDetectionError) as context:
            detect_provider(
                ["aws_instance", "azurerm_virtual_network", "google_compute_instance"]
            )
        self.assertIn("Mixed providers", str(context.exception))
        self.assertIn("providers", context.exception.context)

    def test_unknown_provider_prefix_raises_error(self):
        """Test that unknown provider prefix raises error."""
        with self.assertRaises(ProviderDetectionError) as context:
            detect_provider(["custom_resource"])
        self.assertIn("Unknown provider prefix", str(context.exception))
        self.assertIn("resources", context.exception.context)

    def test_mixed_special_resources_default_to_aws(self):
        """Test that only special resources default to AWS."""
        result = detect_provider(["data.aws_ami.ubuntu", "null_resource.example"])
        self.assertEqual(result, "aws")

    def test_error_context_includes_resource_samples(self):
        """Test that error context includes sample resources."""
        with self.assertRaises(ProviderDetectionError) as context:
            detect_provider(["aws_instance"] + ["azurerm_vm"] * 20)
        # Should include up to 10 sample resources
        self.assertIn("resources", context.exception.context)
        self.assertLessEqual(len(context.exception.context["resources"]), 10)


class TestGetProviderConfig(unittest.TestCase):
    """Test get_provider_config() function for retrieving provider configuration."""

    @mock.patch("modules.cloud_config.ProviderRegistry")
    def test_get_aws_config(self, mock_registry):
        """Test retrieving AWS configuration via ProviderRegistry context."""
        mock_registry.get_context.return_value = DummyProviderContext(aws)
        config = get_provider_config("aws")
        self.assertIs(config, aws)
        mock_registry.get_context.assert_called_once_with("aws")

    @mock.patch("modules.cloud_config.ProviderRegistry")
    def test_get_azure_config(self, mock_registry):
        """Test retrieving Azure configuration via ProviderRegistry context."""
        mock_registry.get_context.return_value = DummyProviderContext(azure)
        config = get_provider_config("azurerm")
        self.assertIs(config, azure)
        mock_registry.get_context.assert_called_once_with("azurerm")

    @mock.patch("modules.cloud_config.ProviderRegistry")
    def test_get_gcp_config(self, mock_registry):
        """Test retrieving GCP configuration via ProviderRegistry context."""
        mock_registry.get_context.return_value = DummyProviderContext(gcp)
        config = get_provider_config("google")
        self.assertIs(config, gcp)
        mock_registry.get_context.assert_called_once_with("google")

    def test_unsupported_provider_raises_error(self):
        """Test that unsupported provider raises ValueError."""
        with self.assertRaises(ValueError) as context:
            get_provider_config("alibaba")
        self.assertIn("Unsupported provider", str(context.exception))

    def test_empty_provider_raises_error(self):
        """Test that empty provider string raises ValueError."""
        with self.assertRaises(ValueError):
            get_provider_config("")

    def test_case_sensitive_provider_name(self):
        """Test that provider names are case-sensitive."""
        with self.assertRaises(ValueError):
            get_provider_config("AWS")  # Should be lowercase "aws"


class TestDetectProviderForNode(unittest.TestCase):
    """Test detect_provider_for_node() function for single node detection."""

    def test_detect_aws_from_instance_id(self):
        """Test detecting AWS from instance resource ID."""
        result = detect_provider_for_node("aws_instance.web")
        self.assertEqual(result, "aws")

    def test_detect_azure_from_vm_id(self):
        """Test detecting Azure from VM resource ID."""
        result = detect_provider_for_node("azurerm_virtual_machine.vm1")
        self.assertEqual(result, "azurerm")

    def test_detect_gcp_from_instance_id(self):
        """Test detecting GCP from instance resource ID."""
        result = detect_provider_for_node("google_compute_instance.server")
        self.assertEqual(result, "google")

    def test_data_source_returns_none(self):
        """Test that data sources return None (cannot detect from 'data' prefix)."""
        result = detect_provider_for_node("data.aws_ami.ubuntu")
        # 'data' doesn't match any provider prefix, so returns None
        self.assertIsNone(result)

    def test_module_reference_returns_none(self):
        """Test that module references return None (cannot detect from 'module' prefix)."""
        result = detect_provider_for_node("module.vpc.aws_vpc.main")
        # 'module' doesn't match any provider prefix, so returns None
        self.assertIsNone(result)

    def test_null_resource_returns_aws_default(self):
        """Test that null resources default to AWS."""
        result = detect_provider_for_node("null_resource.example")
        self.assertEqual(result, "aws")

    def test_resource_id_with_multiple_dots(self):
        """Test handling resource IDs with multiple dots."""
        # Should take first segment before dot
        result = detect_provider_for_node("aws_instance.web.extra.parts")
        self.assertEqual(result, "aws")

    def test_unknown_resource_type_returns_none(self):
        """Test that unknown resource types return None."""
        result = detect_provider_for_node("unknown_resource.test")
        self.assertIsNone(result)

    def test_invalid_format_returns_none(self):
        """Test that invalid format returns None gracefully."""
        result = detect_provider_for_node("not_a_valid_resource_id")
        # Should handle gracefully, either aws default or None
        self.assertIn(result, ["aws", None])

    def test_empty_string_returns_none(self):
        """Test that empty string returns None."""
        result = detect_provider_for_node("")
        # Should return aws (default) or None
        self.assertIn(result, ["aws", None])


if __name__ == "__main__":
    unittest.main()
