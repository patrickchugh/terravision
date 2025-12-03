"""Graph and metadata manipulation utilities for TerraVision.

This module provides utilities for working with the tfdata graph structure,
metadata validation, and graph operations.
"""

from typing import Any, Dict, List, Tuple


def list_of_dictkeys_containing(
    searchdict: Dict[str, Any], target_keyword: str
) -> List[str]:
    """Find all dictionary keys containing a keyword.

    Args:
        searchdict: Dictionary to search
        target_keyword: Keyword to find in keys

    Returns:
        List of matching keys
    """
    final_list = list()
    for item in searchdict:
        if target_keyword in item:
            final_list.append(item)
    return final_list


def find_common_elements(dict_of_lists: dict, keyword: str) -> list:
    """Find shared elements between dictionary lists where keys contain a keyword.

    Identifies elements that appear in multiple lists, but only when both keys
    contain the specified keyword. Useful for finding duplicate connections
    between similar resources (e.g., security groups).

    This implementation uses set operations for O(n+m) complexity instead of
    nested loops for O(n*m) complexity.

    Args:
        dict_of_lists: Dictionary where values are lists of elements
        keyword: String that must be present in both keys to check for common elements

    Returns:
        list: Sorted list of tuples (key1, key2, common_element) for each shared element
    """
    results = []

    # Get all keys containing the keyword
    matching_keys = [k for k in dict_of_lists.keys() if keyword in k]

    # Compare each pair of matching keys
    for i, key1 in enumerate(matching_keys):
        set1 = set(dict_of_lists[key1])
        for key2 in matching_keys[i + 1 :]:  # Avoid duplicate comparisons
            set2 = set(dict_of_lists[key2])
            # Find common elements using set intersection
            common = set1 & set2
            for element in sorted(common):  # Sort for deterministic output
                results.append((key1, key2, element))
                results.append((key2, key1, element))  # Add reverse for compatibility

    return sorted(results)  # Ensure deterministic ordering


def ensure_metadata(
    resource_id: str, resource_type: str, provider: str = "aws", **additional_attrs: Any
) -> Dict[str, Any]:
    """Create consistent metadata dictionary for graph nodes.

    Args:
        resource_id: Unique resource identifier (e.g., 'aws_vpc.main')
        resource_type: Resource type (e.g., 'aws_vpc')
        provider: Cloud provider ('aws', 'azurerm', 'google')
        **additional_attrs: Additional metadata attributes

    Returns:
        dict: Metadata dictionary with required keys
    """
    metadata = {
        "name": resource_id.split(".")[-1],
        "type": resource_type,
        "provider": provider,
    }
    metadata.update(additional_attrs)
    return metadata


def validate_metadata_consistency(tfdata: Dict[str, Any]) -> List[str]:
    """Validate metadata consistency across graphdict and meta_data.

    Checks for:
    - Resources in graphdict missing from meta_data
    - Required metadata keys (name, type, provider)
    - Orphaned metadata entries

    Args:
        tfdata: Terraform data dictionary with 'graphdict' and 'meta_data'

    Returns:
        list: List of validation error messages (empty if all valid)
    """
    errors = []
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})

    # Check for resources in graph but missing metadata
    for resource_id in graphdict.keys():
        if resource_id not in meta_data:
            errors.append(
                f"Resource {resource_id} in graphdict but missing from meta_data"
            )
        else:
            # Validate required metadata keys
            metadata = meta_data[resource_id]
            required_keys = ["name", "type", "provider"]
            for key in required_keys:
                if key not in metadata:
                    errors.append(
                        f"Resource {resource_id} metadata missing required key: {key}"
                    )

    # Check for orphaned metadata entries (in meta_data but not graphdict)
    for resource_id in meta_data.keys():
        if resource_id not in graphdict:
            errors.append(
                f"Resource {resource_id} in meta_data but missing from graphdict"
            )

    return errors


def initialize_metadata(
    resource_id: str, resource_values: Dict[str, Any], provider: str = "aws"
) -> Dict[str, Any]:
    """Initialize metadata entry from resource values.

    Helper function for consistent metadata entry creation from Terraform
    resource data.

    Args:
        resource_id: Resource identifier (e.g., 'aws_instance.web')
        resource_values: Terraform resource values dictionary
        provider: Cloud provider identifier

    Returns:
        dict: Initialized metadata dictionary
    """
    # Extract resource type and name from resource_id
    parts = resource_id.split(".")
    resource_type = parts[0] if len(parts) > 0 else "unknown"
    resource_name = parts[-1] if len(parts) > 1 else resource_id

    metadata = ensure_metadata(
        resource_id=resource_id,
        resource_type=resource_type,
        provider=provider,
    )

    # Add common attributes from resource values
    common_attrs = [
        "id",
        "name",
        "cidr_block",
        "vpc_id",
        "subnet_id",
        "security_groups",
        "availability_zone",
        "tags",
        "arn",
        "region",
        "location",
        "resource_group_name",
    ]

    for attr in common_attrs:
        if attr in resource_values:
            metadata[attr] = resource_values[attr]

    return metadata
