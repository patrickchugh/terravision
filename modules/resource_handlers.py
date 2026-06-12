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
