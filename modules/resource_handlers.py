"""Resource handler dispatcher for multi-cloud Terraform graph processing.

This module acts as a dispatcher/facade that routes resource handling operations
to provider-specific handler modules (AWS, Azure, GCP) based on the detected
cloud provider.

Architecture:
- resource_handlers.py (this file) - Dispatcher
- resource_handlers_aws.py - AWS-specific handlers
- resource_handlers_azure.py - Azure-specific handlers
- resource_handlers_gcp.py - GCP-specific handlers
"""

from typing import Dict, Any, Callable
import modules.resource_handlers_aws as aws_handlers
import modules.resource_handlers_azure as azure_handlers
import modules.resource_handlers_gcp as gcp_handlers
from modules.provider_detector import get_primary_provider_or_default
import logging

logger = logging.getLogger(__name__)

# Provider-specific handler module registry
HANDLER_MODULES = {"aws": aws_handlers, "azure": azure_handlers, "gcp": gcp_handlers}


def get_handler_module(tfdata: Dict[str, Any]):
    """Get the appropriate handler module based on provider detection.

    Args:
        tfdata: Terraform data dictionary (must contain provider_detection)

    Returns:
        Provider-specific handler module (aws_handlers, azure_handlers, or gcp_handlers)

    Raises:
        ValueError: If provider detection not found or provider not supported

    Note:
        This function NO LONGER defaults to AWS. Provider detection must be run
        before calling this function.
    """
    # Detect primary provider from tfdata (will raise error if not detected)
    provider = get_primary_provider_or_default(tfdata)

    # Get handler module for provider
    handler_module = HANDLER_MODULES.get(provider)

    if not handler_module:
        logger.error(
            f"No handler module found for provider '{provider}'. "
            f"Supported providers: {list(HANDLER_MODULES.keys())}"
        )
        raise ValueError(
            f"No handler module available for provider '{provider}'. "
            f"Please ensure a handler module exists for this provider."
        )

    logger.info(f"Using {provider.upper()} resource handlers")
    return handler_module


def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch special resource case handling to provider-specific implementation.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with special cases handled
    """
    handler_module = get_handler_module(tfdata)
    return handler_module.handle_special_cases(tfdata)


def match_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch resource matching to provider-specific implementation.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with resources matched
    """
    handler_module = get_handler_module(tfdata)
    return handler_module.match_resources(tfdata)


def random_string_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Remove random string resources from graph (provider-agnostic).

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with random strings removed
    """
    # This is common across all providers, but dispatch for consistency
    handler_module = get_handler_module(tfdata)
    return handler_module.random_string_handler(tfdata)


def get_special_resource_handler(resource_type: str, provider: str) -> Callable:
    """Get handler function for a specific resource type and provider.

    Args:
        resource_type: Terraform resource type (e.g., 'aws_security_group')
        provider: Cloud provider ('aws', 'azure', 'gcp')

    Returns:
        Handler function for the resource type, or None if not found

    Examples:
        >>> handler = get_special_resource_handler('aws_security_group', 'aws')
        >>> handler  # Returns aws_handlers.aws_handle_sg

        >>> handler = get_special_resource_handler('azurerm_virtual_network', 'azure')
        >>> handler  # Returns azure_handlers.azure_handle_vnet
    """
    handler_module = HANDLER_MODULES.get(provider)
    if not handler_module:
        logger.warning(f"No handler module for provider '{provider}'")
        return None

    # Get SPECIAL_RESOURCES dict from provider module
    special_resources = getattr(handler_module, "SPECIAL_RESOURCES", {})

    # Find handler for this resource type (prefix match)
    for prefix, handler_name in special_resources.items():
        if resource_type.startswith(prefix):
            # Get handler function from module
            handler_func = getattr(handler_module, handler_name, None)
            if handler_func:
                return handler_func
            else:
                logger.warning(
                    f"Handler '{handler_name}' not found in {provider} module for '{resource_type}'"
                )
                return None

    return None


def apply_special_resource_handlers(
    tfdata: Dict[str, Any], provider: str
) -> Dict[str, Any]:
    """Apply all special resource handlers for a provider.

    This processes SPECIAL_RESOURCES config in order, applying each handler function.

    Args:
        tfdata: Terraform data dictionary
        provider: Cloud provider ('aws', 'azure', 'gcp')

    Returns:
        Updated tfdata with all special handlers applied
    """
    handler_module = HANDLER_MODULES.get(provider)
    if not handler_module:
        logger.warning(f"No handler module for provider '{provider}'")
        return tfdata

    special_resources = getattr(handler_module, "SPECIAL_RESOURCES", {})

    # Apply handlers in order defined in config
    for prefix, handler_name in special_resources.items():
        # Check if any resources match this prefix
        matching_resources = [
            r for r in tfdata.get("all_resource", []) if r.startswith(prefix)
        ]

        if matching_resources:
            # Get and apply handler function
            handler_func = getattr(handler_module, handler_name, None)
            if handler_func:
                logger.debug(
                    f"Applying {handler_name} for {len(matching_resources)} resources"
                )
                tfdata = handler_func(tfdata)
            else:
                logger.warning(
                    f"Handler '{handler_name}' not found in {provider} module"
                )

    return tfdata
