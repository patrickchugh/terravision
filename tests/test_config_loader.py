"""
Unit tests for config_loader module.

Tests the dynamic configuration loading functionality including:
- Loading provider-specific configurations
- Validation of configuration modules
- Error handling for missing or invalid providers
- Backward compatibility helpers
"""

import pytest
from modules.config_loader import (
    load_config,
    reload_config,
    validate_config_module,
    get_config_with_fallback,
    list_available_providers,
    get_aws_config,
    ConfigurationError,
    PROVIDER_CONFIG_MODULES,
    SUPPORTED_PROVIDERS,
)


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_load_aws_config(self):
        """Test loading AWS configuration."""
        config = load_config("aws")

        assert hasattr(config, "PROVIDER_NAME")
        assert config.PROVIDER_NAME == "AWS"
        assert hasattr(config, "AWS_GROUP_NODES")
        assert hasattr(config, "AWS_CONSOLIDATED_NODES")
        assert hasattr(config, "AWS_SPECIAL_RESOURCES")

    def test_load_azure_config(self):
        """Test loading Azure configuration."""
        config = load_config("azure")

        assert hasattr(config, "PROVIDER_NAME")
        assert config.PROVIDER_NAME == "Azure"
        assert hasattr(config, "AZURE_GROUP_NODES")
        assert hasattr(config, "AZURE_CONSOLIDATED_NODES")
        assert hasattr(config, "AZURE_SPECIAL_RESOURCES")

    def test_load_gcp_config(self):
        """Test loading GCP configuration."""
        config = load_config("gcp")

        assert hasattr(config, "PROVIDER_NAME")
        assert config.PROVIDER_NAME == "GCP"
        assert hasattr(config, "GCP_GROUP_NODES")
        assert hasattr(config, "GCP_CONSOLIDATED_NODES")
        assert hasattr(config, "GCP_SPECIAL_RESOURCES")

    def test_load_invalid_provider_raises_error(self):
        """Test that loading invalid provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_config("invalid_provider")

        assert "not supported" in str(exc_info.value)

    def test_load_unsupported_provider_raises_error(self):
        """Test that loading unsupported provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_config("alibaba")

        assert "not supported" in str(exc_info.value)

    def test_config_is_cached(self):
        """Test that configuration modules are cached after first import."""
        config1 = load_config("aws")
        config2 = load_config("aws")

        # Same module object (Python's import cache)
        assert config1 is config2


class TestReloadConfig:
    """Tests for reload_config() function."""

    def test_reload_aws_config(self):
        """Test reloading AWS configuration."""
        config1 = load_config("aws")
        config2 = reload_config("aws")

        # Both should have same attributes after reload
        assert config1.PROVIDER_NAME == config2.PROVIDER_NAME
        assert hasattr(config2, "AWS_GROUP_NODES")

    def test_reload_invalid_provider_raises_error(self):
        """Test that reloading invalid provider raises error."""
        with pytest.raises(ValueError):
            reload_config("invalid_provider")


class TestValidateConfigModule:
    """Tests for validate_config_module() function."""

    def test_validate_aws_config(self):
        """Test validation of AWS configuration module."""
        config = load_config("aws")

        # Should pass validation
        assert validate_config_module(config, "aws") is True

    def test_validate_azure_config(self):
        """Test validation of Azure configuration module."""
        config = load_config("azure")

        # Should pass validation
        assert validate_config_module(config, "azure") is True

    def test_validate_gcp_config(self):
        """Test validation of GCP configuration module."""
        config = load_config("gcp")

        # Should pass validation
        assert validate_config_module(config, "gcp") is True

    def test_validate_incomplete_config_raises_error(self):
        """Test that incomplete config module fails validation."""

        # Create a mock config module with missing attributes
        class IncompleteConfig:
            PROVIDER_NAME = "Test"
            # Missing PROVIDER_PREFIX, ICON_LIBRARY

        with pytest.raises(ConfigurationError) as exc_info:
            validate_config_module(IncompleteConfig, "test")

        assert "missing required attributes" in str(exc_info.value)


class TestGetConfigWithFallback:
    """Tests for get_config_with_fallback() function."""

    def test_get_config_primary_exists(self):
        """Test getting primary config when it exists."""
        config = get_config_with_fallback("azure", fallback_provider="aws")

        assert config.PROVIDER_NAME == "Azure"

    def test_get_config_fallback_to_aws(self):
        """Test fallback to AWS when primary doesn't exist."""
        # Try to load non-existent provider, should fallback to AWS
        config = get_config_with_fallback("nonexistent", fallback_provider="aws")

        assert config.PROVIDER_NAME == "AWS"

    def test_get_config_both_fail_raises_error(self):
        """Test that error is raised when both primary and fallback fail."""
        with pytest.raises(ConfigurationError):
            get_config_with_fallback("nonexistent1", fallback_provider="nonexistent2")


class TestListAvailableProviders:
    """Tests for list_available_providers() function."""

    def test_list_available_providers(self):
        """Test listing all available providers."""
        available = list_available_providers()

        # Should have all three providers
        assert set(available) == {"aws", "azure", "gcp"}
        assert len(available) == 3

    def test_available_providers_are_loadable(self):
        """Test that all listed providers can actually be loaded."""
        available = list_available_providers()

        for provider in available:
            config = load_config(provider)
            assert hasattr(config, "PROVIDER_NAME")


class TestBackwardCompatibility:
    """Tests for backward compatibility helpers."""

    def test_get_aws_config(self):
        """Test backward compatibility helper for AWS config."""
        config = get_aws_config()

        assert config.PROVIDER_NAME == "AWS"
        assert hasattr(config, "AWS_GROUP_NODES")

    def test_get_aws_config_equivalent_to_load_config(self):
        """Test that get_aws_config is equivalent to load_config('aws')."""
        config1 = get_aws_config()
        config2 = load_config("aws")

        # Should be the same module
        assert config1 is config2


class TestProviderConstants:
    """Tests for module constants."""

    def test_provider_config_modules_complete(self):
        """Test that PROVIDER_CONFIG_MODULES has entries for all providers."""
        assert PROVIDER_CONFIG_MODULES["aws"] == "modules.config.cloud_config_aws"
        assert PROVIDER_CONFIG_MODULES["azure"] == "modules.config.cloud_config_azure"
        assert PROVIDER_CONFIG_MODULES["gcp"] == "modules.config.cloud_config_gcp"

    def test_supported_providers_complete(self):
        """Test that SUPPORTED_PROVIDERS contains expected providers."""
        assert set(SUPPORTED_PROVIDERS) == {"aws", "azure", "gcp"}
        assert len(SUPPORTED_PROVIDERS) == 3


class TestConfigModuleAttributes:
    """Tests for configuration module attributes and structure."""

    def test_aws_config_has_required_lists(self):
        """Test that AWS config has all required list constants."""
        config = load_config("aws")

        assert hasattr(config, "AWS_CONSOLIDATED_NODES")
        assert hasattr(config, "AWS_GROUP_NODES")
        assert hasattr(config, "AWS_EDGE_NODES")
        assert hasattr(config, "AWS_OUTER_NODES")
        assert hasattr(config, "AWS_DRAW_ORDER")
        assert hasattr(config, "AWS_AUTO_ANNOTATIONS")
        assert hasattr(config, "AWS_SPECIAL_RESOURCES")
        assert hasattr(config, "AWS_SHARED_SERVICES")

    def test_azure_config_has_required_lists(self):
        """Test that Azure config has all required list constants."""
        config = load_config("azure")

        assert hasattr(config, "AZURE_CONSOLIDATED_NODES")
        assert hasattr(config, "AZURE_GROUP_NODES")
        assert hasattr(config, "AZURE_EDGE_NODES")
        assert hasattr(config, "AZURE_OUTER_NODES")
        assert hasattr(config, "AZURE_DRAW_ORDER")
        assert hasattr(config, "AZURE_AUTO_ANNOTATIONS")
        assert hasattr(config, "AZURE_SPECIAL_RESOURCES")
        assert hasattr(config, "AZURE_SHARED_SERVICES")

    def test_gcp_config_has_required_lists(self):
        """Test that GCP config has all required list constants."""
        config = load_config("gcp")

        assert hasattr(config, "GCP_CONSOLIDATED_NODES")
        assert hasattr(config, "GCP_GROUP_NODES")
        assert hasattr(config, "GCP_EDGE_NODES")
        assert hasattr(config, "GCP_OUTER_NODES")
        assert hasattr(config, "GCP_DRAW_ORDER")
        assert hasattr(config, "GCP_AUTO_ANNOTATIONS")
        assert hasattr(config, "GCP_SPECIAL_RESOURCES")
        assert hasattr(config, "GCP_SHARED_SERVICES")

    def test_all_configs_have_ai_prompts(self):
        """Test that all configs have AI prompt constants."""
        for provider in ["aws", "azure", "gcp"]:
            config = load_config(provider)
            provider_upper = provider.upper()

            assert hasattr(config, f"{provider_upper}_REFINEMENT_PROMPT")
            assert hasattr(config, f"{provider_upper}_DOCUMENTATION_PROMPT")

    def test_all_configs_have_name_replacements(self):
        """Test that all configs have name replacement mappings."""
        aws_config = load_config("aws")
        azure_config = load_config("azure")
        gcp_config = load_config("gcp")

        assert hasattr(aws_config, "AWS_NAME_REPLACEMENTS")
        assert hasattr(azure_config, "AZURE_NAME_REPLACEMENTS")
        assert hasattr(gcp_config, "GCP_NAME_REPLACEMENTS")

        # Should be dictionaries
        assert isinstance(aws_config.AWS_NAME_REPLACEMENTS, dict)
        assert isinstance(azure_config.AZURE_NAME_REPLACEMENTS, dict)
        assert isinstance(gcp_config.GCP_NAME_REPLACEMENTS, dict)

    def test_all_configs_have_provider_prefix(self):
        """Test that all configs have PROVIDER_PREFIX."""
        aws_config = load_config("aws")
        azure_config = load_config("azure")
        gcp_config = load_config("gcp")

        assert aws_config.PROVIDER_PREFIX == ["aws_"]
        assert set(azure_config.PROVIDER_PREFIX) == {
            "azurerm_",
            "azuread_",
            "azurestack_",
            "azapi_",
        }
        assert gcp_config.PROVIDER_PREFIX == ["google_"]


class TestIntegrationWithProviderDetector:
    """Tests for integration with provider_detector module."""

    def test_load_config_for_detected_provider(self):
        """Test loading config based on provider detection result."""
        from modules.provider_detector import detect_providers

        # Simulate detection result
        tfdata = {
            "all_resource": [
                "azurerm_virtual_machine.app",
                "azurerm_storage_account.storage",
            ]
        }

        detection_result = detect_providers(tfdata)
        primary_provider = detection_result["primary_provider"]

        # Load config for detected provider
        config = load_config(primary_provider)

        assert config.PROVIDER_NAME == "Azure"
