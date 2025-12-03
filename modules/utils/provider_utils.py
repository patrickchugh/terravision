"""Provider detection and configuration utilities for TerraVision.

This module provides utilities for detecting cloud providers from resource
types and retrieving provider-specific configuration.
"""

from typing import Dict, List, Optional


def detect_provider(resource_types: List[str]) -> str:
    """Detect cloud provider from resource type prefixes.

    Args:
        resource_types: List of Terraform resource types

    Returns:
        Provider identifier: 'aws', 'azurerm', 'google', or 'unknown'

    Raises:
        ProviderDetectionError: If multiple providers detected or unknown prefix
    """
    providers_found = set()

    for resource_type in resource_types:
        if resource_type.startswith("aws_"):
            providers_found.add("aws")
        elif resource_type.startswith("azurerm_"):
            providers_found.add("azurerm")
        elif resource_type.startswith("google_"):
            providers_found.add("google")
        elif not resource_type.startswith(
            ("data.", "module.", "null_", "random_", "time_")
        ):
            # Unknown provider prefix (not a data source or special resource)
            providers_found.add("unknown")

    if len(providers_found) == 0:
        return "aws"  # Default to AWS if no resources
    elif len(providers_found) > 1:
        from modules.exceptions import ProviderDetectionError

        raise ProviderDetectionError(
            f"Mixed providers detected: {sorted(providers_found)}",
            context={
                "providers": sorted(providers_found),
                "resources": resource_types[:10],
            },
        )
    elif "unknown" in providers_found:
        from modules.exceptions import ProviderDetectionError

        raise ProviderDetectionError(
            "Unknown provider prefix detected",
            context={"resources": resource_types[:10]},
        )

    return providers_found.pop()


def get_provider_config(provider: str) -> Dict[str, any]:
    """Get provider-specific configuration.

    Args:
        provider: Provider identifier ('aws', 'azurerm', 'google')

    Returns:
        dict: Provider configuration dictionary

    Raises:
        ValueError: If provider is not supported
    """
    from modules.cloud_config import ProviderRegistry

    if provider not in ["aws", "azurerm", "google"]:
        raise ValueError(f"Unsupported provider: {provider}")

    ctx = ProviderRegistry.get_context(provider)
    return ctx.get_config(provider)


def detect_provider_for_node(resource_id: str) -> Optional[str]:
    """Detect provider from a single resource identifier.

    Args:
        resource_id: Resource identifier (e.g., 'aws_instance.web')

    Returns:
        Provider identifier or None if cannot detect
    """
    resource_type = resource_id.split(".")[0]

    try:
        return detect_provider([resource_type])
    except Exception:
        return None
