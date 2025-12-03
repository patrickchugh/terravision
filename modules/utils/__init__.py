"""Utility modules for TerraVision.

This package contains utility modules for string manipulation, Terraform
operations, graph processing, and provider detection.
"""

from .string_utils import find_between, find_nth
from .terraform_utils import getvar, tfvar_read
from .graph_utils import (
    list_of_dictkeys_containing,
    find_common_elements,
    ensure_metadata,
    validate_metadata_consistency,
    initialize_metadata,
)
from .provider_utils import (
    detect_provider,
    get_provider_config,
    detect_provider_for_node,
)

__all__ = [
    # String utilities
    "find_between",
    "find_nth",
    # Terraform utilities
    "getvar",
    "tfvar_read",
    # Graph utilities
    "list_of_dictkeys_containing",
    "find_common_elements",
    "ensure_metadata",
    "validate_metadata_consistency",
    "initialize_metadata",
    # Provider utilities
    "detect_provider",
    "get_provider_config",
    "detect_provider_for_node",
]
