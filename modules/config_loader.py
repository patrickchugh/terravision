"""
Configuration Loader Module for TerraVision Multi-Cloud Support

This module provides dynamic loading of provider-specific configuration files.
It replaces direct imports of cloud_config.py with runtime provider detection
and configuration loading.

"""

from typing import Dict, Any, Optional
import importlib
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Module name mapping for each provider
PROVIDER_CONFIG_MODULES = {
    "aws": "modules.config.cloud_config_aws",
    "azure": "modules.config.cloud_config_azure",
    "gcp": "modules.config.cloud_config_gcp",
}

# Supported providers
SUPPORTED_PROVIDERS = ["aws", "azure", "gcp"]


class ConfigurationError(Exception):
    """Raised when configuration loading fails."""

    pass


def load_config(provider: str) -> Any:
    """
    Load provider-specific configuration module dynamically.

    This function dynamically imports the appropriate cloud_config module
    based on the provider name. It replaces static imports like:
        from modules import cloud_config
    with dynamic loading:
        config = config_loader.load_config('aws')

    Args:
        provider: Cloud provider name ('aws' | 'azure' | 'gcp')

    Returns:
        Provider-specific configuration module with constants and mappings

    Raises:
        ValueError: If provider not supported
        ConfigurationError: If configuration module cannot be loaded

    Examples:
        >>> aws_config = load_config('aws')
        >>> aws_config.PROVIDER_NAME
        'AWS'

        >>> azure_config = load_config('azure')
        >>> azure_config.PROVIDER_NAME
        'Azure'

        >>> gcp_config = load_config('gcp')
        >>> gcp_config.PROVIDER_NAME
        'GCP'

    Usage Notes:
        - Configuration modules are cached after first import
        - Module must exist at modules/config/cloud_config_{provider}.py
        - Each config module must define standard constants (see cloud_config_aws.py)
    """
    provider = provider.lower()
    # Validate provider
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' not supported. "
            f"Must be one of: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    # Get module name
    module_name = PROVIDER_CONFIG_MODULES.get(provider)
    if not module_name:
        raise ConfigurationError(
            f"No configuration module mapped for provider '{provider}'"
        )

    try:
        # Dynamically import the configuration module
        config_module = importlib.import_module(module_name)
        logger.info(
            f"Loaded configuration for provider '{provider}' from {module_name}"
        )
        return config_module

    except ImportError as e:
        logger.error(f"Failed to import configuration for provider '{provider}': {e}")
        raise ConfigurationError(
            f"Could not load configuration for provider '{provider}'. "
            f"Module '{module_name}' not found or has import errors. "
            f"Error: {e}"
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error loading configuration for '{provider}': {e}")
        raise ConfigurationError(
            f"Unexpected error loading configuration for provider '{provider}': {e}"
        ) from e


def reload_config(provider: str) -> Any:
    """
    Reload provider configuration module (clears cache).

    Useful for testing or when configuration files are modified at runtime.

    Args:
        provider: Cloud provider name to reload

    Returns:
        Reloaded configuration module

    Raises:
        ValueError: If provider not supported
        ConfigurationError: If configuration cannot be reloaded

    Examples:
        >>> config = reload_config('aws')
        >>> # Config is fresh from disk, not cached
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' not supported. "
            f"Must be one of: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    module_name = PROVIDER_CONFIG_MODULES.get(provider)
    if not module_name:
        raise ConfigurationError(
            f"No configuration module mapped for provider '{provider}'"
        )

    try:
        # Import and reload the module
        config_module = importlib.import_module(module_name)
        config_module = importlib.reload(config_module)
        logger.info(f"Reloaded configuration for provider '{provider}'")
        return config_module

    except ImportError as e:
        logger.error(f"Failed to reload configuration for '{provider}': {e}")
        raise ConfigurationError(
            f"Could not reload configuration for provider '{provider}': {e}"
        ) from e


def validate_config_module(config_module: Any, provider: str) -> bool:
    """
    Validate that a configuration module has required attributes.

    Configuration modules must define certain standard attributes to work
    with TerraVision's diagram generation pipeline.

    Args:
        config_module: Configuration module to validate
        provider: Provider name (for error messages)

    Returns:
        True if validation passes

    Raises:
        ConfigurationError: If validation fails

    Required Attributes:
        - PROVIDER_NAME (str): Human-readable provider name
        - PROVIDER_PREFIX (str or list): Resource name prefix(es)
        - ICON_LIBRARY (str): Path to icon library

    Examples:
        >>> config = load_config('aws')
        >>> validate_config_module(config, 'aws')
        True
    """
    required_attrs = ["PROVIDER_NAME", "PROVIDER_PREFIX", "ICON_LIBRARY"]

    missing_attrs = []
    for attr in required_attrs:
        if not hasattr(config_module, attr):
            missing_attrs.append(attr)

    if missing_attrs:
        raise ConfigurationError(
            f"Configuration module for provider '{provider}' is missing required attributes: "
            f"{', '.join(missing_attrs)}. Please ensure cloud_config_{provider}.py defines all required constants."
        )

    logger.debug(f"Configuration module for '{provider}' passed validation")
    return True


def get_config_with_fallback(provider: str, fallback_provider: str) -> Any:
    """
    Load provider configuration with fallback to another provider.

    Useful for graceful degradation when a provider's configuration is missing.

    Args:
        provider: Primary provider to load
        fallback_provider: Fallback provider if primary fails (MUST be explicitly specified)

    Returns:
        Configuration module (primary or fallback)

    Raises:
        ConfigurationError: If both primary and fallback providers fail to load

    Examples:
        >>> # Try to load Azure, fallback to AWS if missing
        >>> config = get_config_with_fallback('azure', fallback_provider='aws')

    Note:
        No default fallback provider - caller must explicitly specify fallback.
        This prevents hidden AWS assumptions.
    """
    try:
        config = load_config(provider)
        return config
    except (ValueError, ConfigurationError) as e:
        logger.warning(
            f"Could not load config for '{provider}', falling back to '{fallback_provider}': {e}"
        )
        try:
            return load_config(fallback_provider)
        except (ValueError, ConfigurationError) as fallback_error:
            logger.error(
                f"Fallback to '{fallback_provider}' also failed: {fallback_error}"
            )
            raise ConfigurationError(
                f"Could not load config for '{provider}' and fallback to '{fallback_provider}' failed"
            ) from fallback_error


def list_available_providers() -> list:
    """
    List all providers that have configuration modules available.

    Returns:
        List of provider names with available configurations

    Examples:
        >>> list_available_providers()
        ['aws', 'azure', 'gcp']
    """
    available = []

    for provider in SUPPORTED_PROVIDERS:
        try:
            load_config(provider)
            available.append(provider)
        except (ValueError, ConfigurationError):
            # Provider config not available
            pass

    return available


# Backward compatibility helper
def get_aws_config() -> Any:
    """
    Get AWS configuration (backward compatibility helper).

    This function provides backward compatibility for code that previously
    imported cloud_config directly. New code should use load_config('aws').

    Returns:
        AWS configuration module

    Examples:
        >>> config = get_aws_config()
        >>> # Equivalent to: from modules import cloud_config_aws as config
    """
    return load_config("aws")
