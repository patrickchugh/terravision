"""
Cloud provider configuration package.

This package contains provider-specific configurations for AWS, Azure, and GCP.
It provides backward compatibility with the old cloud_config.py monolithic file.
"""

# Import provider runtime for registration
from modules.provider_runtime import ProviderRegistry, ProviderDescriptor

# Register built-in providers
ProviderRegistry.register(
    ProviderDescriptor(
        id="aws",
        resource_prefixes=("aws_",),
        cloud_config_module="modules.cloud_config.aws",
        handler_module="resource_handlers.aws",
    ),
    default=True,  # AWS is the default provider for backwards compatibility
)

ProviderRegistry.register(
    ProviderDescriptor(
        id="azurerm",
        resource_prefixes=("azurerm_", "azuread_"),
        cloud_config_module="modules.cloud_config.azure",
        handler_module="resource_handlers.azure",
    )
)

ProviderRegistry.register(
    ProviderDescriptor(
        id="google",
        resource_prefixes=("google_",),
        cloud_config_module="modules.cloud_config.gcp",
        handler_module="resource_handlers.gcp",
    )
)

# Import AWS config for backward compatibility
from .aws import (
    AWS_ACRONYMS_LIST,
    AWS_ALWAYS_DRAW_LINE,
    AWS_AUTO_ANNOTATIONS,
    AWS_CONSOLIDATED_NODES,
    AWS_DISCONNECT_LIST,
    AWS_DRAW_ORDER,
    AWS_EDGE_NODES,
    AWS_FORCED_DEST,
    AWS_FORCED_ORIGIN,
    AWS_GROUP_NODES,
    AWS_IMPLIED_CONNECTIONS,
    AWS_NAME_REPLACEMENTS,
    AWS_NEVER_DRAW_LINE,
    AWS_NODE_VARIANTS,
    AWS_OUTER_NODES,
    AWS_REVERSE_ARROW_LIST,
    AWS_SHARED_SERVICES,
    AWS_SPECIAL_RESOURCES,
)

__all__ = [
    # Registry exports
    "ProviderRegistry",
    "ProviderDescriptor",
    # AWS constants (for backward compatibility)
    "AWS_ACRONYMS_LIST",
    "AWS_ALWAYS_DRAW_LINE",
    "AWS_AUTO_ANNOTATIONS",
    "AWS_CONSOLIDATED_NODES",
    "AWS_DISCONNECT_LIST",
    "AWS_DRAW_ORDER",
    "AWS_EDGE_NODES",
    "AWS_FORCED_DEST",
    "AWS_FORCED_ORIGIN",
    "AWS_GROUP_NODES",
    "AWS_IMPLIED_CONNECTIONS",
    "AWS_NAME_REPLACEMENTS",
    "AWS_NEVER_DRAW_LINE",
    "AWS_NODE_VARIANTS",
    "AWS_OUTER_NODES",
    "AWS_REVERSE_ARROW_LIST",
    "AWS_SHARED_SERVICES",
    "AWS_SPECIAL_RESOURCES",
]
