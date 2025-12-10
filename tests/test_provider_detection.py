"""
Unit tests for provider_detector module.

Tests the provider detection functionality including:
- Single provider detection (AWS, Azure, GCP)
- Validation of detection results
- Edge cases and error handling
"""

import pytest
from modules.provider_detector import (
    detect_providers,
    get_provider_for_resource,
    validate_provider_detection,
    get_primary_provider_or_default,
    ProviderDetectionError,
    PROVIDER_PREFIXES,
    SUPPORTED_PROVIDERS,
)


class TestGetProviderForResource:
    """Tests for get_provider_for_resource() function."""

    def test_aws_resource(self):
        """Test detection of AWS resources."""
        assert get_provider_for_resource("aws_instance.web") == "aws"
        assert get_provider_for_resource("aws_s3_bucket.data") == "aws"
        assert get_provider_for_resource("aws_vpc.main") == "aws"
        assert get_provider_for_resource("aws_db_instance.postgres") == "aws"

    def test_azure_resource(self):
        """Test detection of Azure resources."""
        assert get_provider_for_resource("azurerm_virtual_machine.app") == "azure"
        assert get_provider_for_resource("azurerm_resource_group.main") == "azure"
        assert get_provider_for_resource("azuread_user.admin") == "azure"
        assert get_provider_for_resource("azurestack_virtual_network.vnet") == "azure"
        assert get_provider_for_resource("azapi_resource.custom") == "azure"

    def test_gcp_resource(self):
        """Test detection of GCP resources."""
        assert get_provider_for_resource("google_compute_instance.vm1") == "gcp"
        assert get_provider_for_resource("google_storage_bucket.data") == "gcp"
        assert get_provider_for_resource("google_sql_database_instance.db") == "gcp"
        assert get_provider_for_resource("google_container_cluster.k8s") == "gcp"

    def test_unknown_resource(self):
        """Test detection of unknown/unsupported resources."""
        assert get_provider_for_resource("random_string.id") == "unknown"
        assert get_provider_for_resource("null_resource.trigger") == "unknown"
        assert get_provider_for_resource("local_file.config") == "unknown"
        assert get_provider_for_resource("data.terraform_remote_state.vpc") == "unknown"

    def test_module_prefixed_aws_resource(self):
        """Test detection from resources with module prefix."""
        assert get_provider_for_resource("module.vpc.aws_subnet.private") == "aws"
        assert get_provider_for_resource("module.networking.aws_vpc.main") == "aws"

    def test_module_prefixed_azure_resource(self):
        """Test detection from Azure resources with module prefix."""
        assert (
            get_provider_for_resource("module.compute.azurerm_virtual_machine.app")
            == "azure"
        )
        assert (
            get_provider_for_resource("module.identity.azuread_user.admin") == "azure"
        )

    def test_module_prefixed_gcp_resource(self):
        """Test detection from GCP resources with module prefix."""
        assert (
            get_provider_for_resource("module.compute.google_compute_instance.vm")
            == "gcp"
        )
        assert (
            get_provider_for_resource("module.storage.google_storage_bucket.data")
            == "gcp"
        )


class TestDetectProviders:
    """Tests for detect_providers() function."""

    def test_detect_aws_only(self):
        """Test detection of AWS-only project."""
        tfdata = {
            "all_resource": ["aws_instance.web", "aws_s3_bucket.data", "aws_vpc.main"],
            "graphdict": {},
            "meta_data": {},
        }

        result = detect_providers(tfdata)

        assert result["providers"] == ["aws"]
        assert result["primary_provider"] == "aws"
        assert result["resource_counts"]["aws"] == 3
        assert result["detection_method"] == "resource_prefix"
        assert result["confidence"] == 1.0

    def test_detect_azure_only(self):
        """Test detection of Azure-only project."""
        tfdata = {
            "all_resource": [
                "azurerm_resource_group.main",
                "azurerm_virtual_machine.app",
                "azurerm_storage_account.logs",
                "azuread_user.admin",
            ]
        }

        result = detect_providers(tfdata)

        assert result["providers"] == ["azure"]
        assert result["primary_provider"] == "azure"
        assert result["resource_counts"]["azure"] == 4
        assert result["confidence"] == 1.0

    def test_detect_gcp_only(self):
        """Test detection of GCP-only project."""
        tfdata = {
            "all_resource": [
                "google_compute_instance.vm1",
                "google_storage_bucket.data",
                "google_sql_database_instance.db",
            ]
        }

        result = detect_providers(tfdata)

        assert result["providers"] == ["gcp"]
        assert result["primary_provider"] == "gcp"
        assert result["resource_counts"]["gcp"] == 3
        assert result["confidence"] == 1.0

    def test_detect_with_unknown_resources_high_confidence(self):
        """Test detection with some unknown resources (>80% known)."""
        tfdata = {
            "all_resource": [
                "aws_instance.web",
                "aws_s3_bucket.data",
                "aws_vpc.main",
                "aws_subnet.private",
                "random_string.id",  # 1 unknown out of 5 = 80% known
            ]
        }

        result = detect_providers(tfdata)

        assert result["providers"] == ["aws"]
        assert result["primary_provider"] == "aws"
        assert result["resource_counts"]["aws"] == 4
        assert 0.8 <= result["confidence"] < 0.9

    def test_detect_with_many_unknown_resources_low_confidence(self):
        """Test detection with many unknown resources (<50% known)."""
        tfdata = {
            "all_resource": [
                "aws_instance.web",
                "random_string.id1",
                "random_string.id2",
                "null_resource.trigger1",
                "null_resource.trigger2",
            ]
        }

        result = detect_providers(tfdata)

        assert result["providers"] == ["aws"]
        assert result["primary_provider"] == "aws"
        assert result["resource_counts"]["aws"] == 1
        assert result["confidence"] < 0.5

    def test_detect_empty_resources_defaults_to_aws(self):
        """Test that empty resource list defaults to AWS with low confidence."""
        tfdata = {"all_resource": []}

        result = detect_providers(tfdata)

        assert result["providers"] == ["aws"]
        assert result["primary_provider"] == "aws"
        assert result["confidence"] < 0.5
        assert result["detection_method"] == "default"

    def test_detect_only_unknown_resources_raises_error(self):
        """Test that project with only unknown resources raises error."""
        tfdata = {
            "all_resource": [
                "random_string.id",
                "null_resource.trigger",
                "local_file.config",
            ]
        }

        with pytest.raises(ProviderDetectionError) as exc_info:
            detect_providers(tfdata)

        assert "Could not detect any supported cloud providers" in str(exc_info.value)

    def test_detect_invalid_tfdata_raises_error(self):
        """Test that invalid tfdata raises ValueError."""
        with pytest.raises(ValueError):
            detect_providers(None)

        with pytest.raises(ValueError):
            detect_providers("not a dict")

        with pytest.raises(ValueError):
            detect_providers({"no_all_resource_key": []})

    def test_primary_provider_is_most_common(self):
        """Test that primary provider is the one with most resources."""
        tfdata = {
            "all_resource": [
                "aws_instance.web1",
                "aws_instance.web2",
                "aws_s3_bucket.data",
                "azurerm_virtual_machine.app",
                "google_compute_instance.vm",
            ]
        }

        result = detect_providers(tfdata)

        assert result["primary_provider"] == "aws"  # 3 AWS vs 1 Azure vs 1 GCP
        assert result["resource_counts"]["aws"] == 3
        assert result["resource_counts"]["azure"] == 1
        assert result["resource_counts"]["gcp"] == 1


class TestValidateProviderDetection:
    """Tests for validate_provider_detection() function."""

    def test_validate_success(self):
        """Test validation of valid detection result."""
        result = {
            "providers": ["aws"],
            "primary_provider": "aws",
            "resource_counts": {"aws": 3},
            "detection_method": "resource_prefix",
            "confidence": 1.0,
        }
        tfdata = {
            "all_resource": ["aws_instance.web", "aws_s3_bucket.data", "aws_vpc.main"]
        }

        assert validate_provider_detection(result, tfdata) is True

    def test_validate_with_unknown_resources_success(self):
        """Test validation allows for unknown resources."""
        result = {
            "providers": ["aws"],
            "primary_provider": "aws",
            "resource_counts": {"aws": 2},
            "detection_method": "resource_prefix",
            "confidence": 0.7,
        }
        tfdata = {
            "all_resource": [
                "aws_instance.web",
                "aws_s3_bucket.data",
                "random_string.id",  # Unknown resource
            ]
        }

        assert validate_provider_detection(result, tfdata) is True

    def test_validate_fails_invalid_provider(self):
        """Test validation fails for invalid provider."""
        result = {
            "providers": ["invalid_cloud"],
            "primary_provider": "invalid_cloud",
            "resource_counts": {"invalid_cloud": 2},
            "detection_method": "resource_prefix",
            "confidence": 1.0,
        }
        tfdata = {"all_resource": ["resource1", "resource2"]}

        assert validate_provider_detection(result, tfdata) is False

    def test_validate_fails_primary_not_in_providers(self):
        """Test validation fails when primary not in providers list."""
        result = {
            "providers": ["aws"],
            "primary_provider": "azure",  # Not in providers list!
            "resource_counts": {"aws": 2},
            "detection_method": "resource_prefix",
            "confidence": 1.0,
        }
        tfdata = {"all_resource": ["aws_instance.web", "aws_s3_bucket.data"]}

        assert validate_provider_detection(result, tfdata) is False

    def test_validate_fails_no_providers(self):
        """Test validation fails when no providers detected."""
        result = {
            "providers": [],
            "primary_provider": None,
            "resource_counts": {},
            "detection_method": "resource_prefix",
            "confidence": 0.0,
        }
        tfdata = {"all_resource": []}

        assert validate_provider_detection(result, tfdata) is False

    def test_validate_fails_resource_count_mismatch(self):
        """Test validation fails when resource counts don't match."""
        result = {
            "providers": ["aws"],
            "primary_provider": "aws",
            "resource_counts": {"aws": 5},  # Claims 5 but only 3 exist
            "detection_method": "resource_prefix",
            "confidence": 1.0,
        }
        tfdata = {
            "all_resource": ["aws_instance.web", "aws_s3_bucket.data", "aws_vpc.main"]
        }

        assert validate_provider_detection(result, tfdata) is False

    def test_validate_fails_invalid_confidence(self):
        """Test validation fails for invalid confidence values."""
        result = {
            "providers": ["aws"],
            "primary_provider": "aws",
            "resource_counts": {"aws": 2},
            "detection_method": "resource_prefix",
            "confidence": 1.5,  # Invalid: > 1.0
        }
        tfdata = {"all_resource": ["aws_instance.web", "aws_s3_bucket.data"]}

        assert validate_provider_detection(result, tfdata) is False

        # Test negative confidence
        result["confidence"] = -0.1
        assert validate_provider_detection(result, tfdata) is False


class TestHelperFunctions:
    """Tests for helper utility functions."""

    def test_get_primary_provider_or_default_with_detection(self):
        """Test getting primary provider from existing detection result."""
        tfdata = {
            "provider_detection": {"providers": ["azure"], "primary_provider": "azure"}
        }

        assert get_primary_provider_or_default(tfdata) == "azure"

    def test_get_primary_provider_or_default_without_detection(self):
        """Test getting primary provider with auto-detection."""
        tfdata = {"all_resource": ["azurerm_virtual_machine.app"]}

        assert get_primary_provider_or_default(tfdata) == "azure"

    def test_get_primary_provider_or_default_fallback(self):
        """Test fallback to AWS when detection fails."""
        tfdata = {"all_resource": []}

        assert get_primary_provider_or_default(tfdata) == "aws"


class TestConstants:
    """Tests for module constants."""

    def test_provider_prefixes_complete(self):
        """Test that PROVIDER_PREFIXES contains expected entries."""
        assert PROVIDER_PREFIXES["aws_"] == "aws"
        assert PROVIDER_PREFIXES["azurerm_"] == "azure"
        assert PROVIDER_PREFIXES["azuread_"] == "azure"
        assert PROVIDER_PREFIXES["azurestack_"] == "azure"
        assert PROVIDER_PREFIXES["azapi_"] == "azure"
        assert PROVIDER_PREFIXES["google_"] == "gcp"

    def test_supported_providers_complete(self):
        """Test that SUPPORTED_PROVIDERS contains expected entries."""
        assert set(SUPPORTED_PROVIDERS) == {"aws", "azure", "gcp"}
        assert len(SUPPORTED_PROVIDERS) == 3
