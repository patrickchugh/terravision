"""Resource handlers package with provider-aware dispatch.

This module provides a unified interface for calling provider-specific resource handlers.
Handlers are dynamically dispatched based on the handler function name prefix (aws_, azure_, gcp_).
"""

from typing import Dict, Any
import importlib


def __getattr__(name: str):
    """Dynamically dispatch handler functions to provider-specific modules.

    This allows graphmaker.py to call handlers using:
        getattr(resource_handlers, "aws_handle_sg")(tfdata)
        getattr(resource_handlers, "azure_handle_nsg")(tfdata)
        getattr(resource_handlers, "gcp_handle_firewall")(tfdata)

    Args:
        name: Handler function name (e.g., "aws_handle_sg", "azure_handle_nsg")

    Returns:
        The handler function from the appropriate provider module

    Raises:
        AttributeError: If the handler function is not found
    """
    # Map prefixes to module names
    prefix_to_module = {
        "aws_": "modules.resource_handlers.aws",
        "azure_": "modules.resource_handlers.azure",
        "gcp_": "modules.resource_handlers.gcp",
    }

    # Determine which module to use based on prefix
    for prefix, module_name in prefix_to_module.items():
        if name.startswith(prefix):
            # Import the module and get the handler
            module = importlib.import_module(module_name)
            if hasattr(module, name):
                return getattr(module, name)
            raise AttributeError(
                f"Handler '{name}' not found in module '{module_name}'"
            )

    # Special case: backward compatibility for common AWS handlers
    if name in ("handle_special_cases", "match_resources", "random_string_handler"):
        module = importlib.import_module("modules.resource_handlers.aws")
        return getattr(module, name)

    # Handler not found
    raise AttributeError(
        f"Handler '{name}' not found. "
        f"Ensure it starts with a valid prefix (aws_, azure_, gcp_) "
        f"and exists in the appropriate provider module."
    )


__all__ = [
    "handle_special_cases",
    "match_resources",
    "random_string_handler",
]
