"""Generic detection of resources requiring synthetic count for proper numbering.

This module detects resources that should be expanded into multiple numbered instances
but lack explicit Terraform count/for_each attributes. It uses configuration-driven
patterns to identify resources across all cloud providers.

## Problem
Resources deployed across multiple availability zones, subnets, or networks without
explicit Terraform count/for_each create rendering issues:
- Multiple parent groups point to same resource → graphviz shared connection violation
- Resources appear as single node when they should be numbered instances

## Solution
Configuration-driven detection of expansion patterns:
1. Scan Terraform resources for matching resource types
2. Check if trigger attributes (e.g., subnets, zones) contain multiple references
3. Set synthetic count = length of trigger attribute
4. Optionally expand associated resources (e.g., security groups)
5. Let create_multiple_resources() handle numbering naturally

## Examples

**AWS ALB with multiple subnets:**
```
Trigger: subnets = [subnet_a, subnet_b]
Result: count = 2, also expand security_groups
Output: aws_alb.elb~1, aws_alb.elb~2
```

**Azure VM Scale Set with multiple zones:**
```
Trigger: zones = ["1", "2", "3"]
Result: count = 3
Output: azurerm_linux_virtual_machine_scale_set.web~1, ~2, ~3
```

**GCP Instance Group with multiple zones:**
```
Trigger: zones = ["us-central1-a", "us-central1-b"]
Result: count = 2
Output: google_compute_instance_group_manager.web~1, ~2
```
"""

import re
from typing import Dict, Any, List, Set, Optional


# Configuration patterns for multi-instance resource detection
# Each pattern defines:
# - resource_types: List of Terraform resource types to check
# - trigger_attributes: Attributes that trigger expansion (e.g., "subnets", "zones")
# - also_expand_attributes: Attributes containing related resources to also expand
# - resource_pattern: Regex pattern to extract resource references from attribute values
MULTI_INSTANCE_PATTERNS = {
    "aws": [
        {
            "resource_types": ["aws_lb", "aws_alb", "aws_nlb"],
            "trigger_attributes": ["subnets"],
            "also_expand_attributes": ["security_groups"],
            "resource_pattern": r"\$\{(aws_\w+\.\w+)",
            "description": "ALB/NLB spanning multiple subnets",
        },
        {
            "resource_types": ["aws_ecs_service"],
            "trigger_attributes": ["subnets"],
            "also_expand_attributes": ["security_groups"],
            "resource_pattern": r"\$\{(aws_\w+\.\w+)",
            "description": "ECS service spanning multiple subnets",
        },
        # Add more AWS patterns as needed
    ],
    "azure": [
        {
            "resource_types": ["azurerm_lb", "azurerm_public_ip"],
            "trigger_attributes": ["zones"],
            "also_expand_attributes": [],
            "resource_pattern": r'"([^"]+)"',  # Zones are often strings: ["1", "2"]
            "description": "Azure Load Balancer with multiple zones",
        },
        {
            "resource_types": [
                "azurerm_linux_virtual_machine_scale_set",
                "azurerm_windows_virtual_machine_scale_set",
            ],
            "trigger_attributes": ["zones"],
            "also_expand_attributes": [],
            "resource_pattern": r'"([^"]+)"',
            "description": "Azure VM Scale Set with multiple zones",
        },
        # Add more Azure patterns as needed
    ],
    "gcp": [
        {
            "resource_types": [
                "google_compute_instance_group_manager",
                "google_compute_region_instance_group_manager",
            ],
            "trigger_attributes": ["zones", "target_pools"],
            "also_expand_attributes": [],
            "resource_pattern": r'"([^"]+)"',
            "description": "GCP Instance Group Manager with multiple zones",
        },
        {
            "resource_types": ["google_compute_forwarding_rule"],
            "trigger_attributes": ["target"],
            "also_expand_attributes": [],
            "resource_pattern": r"\$\{(google_\w+\.\w+)",
            "description": "GCP Forwarding Rule with target pool",
        },
        # Add more GCP patterns as needed
    ],
}


def extract_resource_references(attribute_value: Any, pattern: str) -> List[str]:
    """Extract resource references from attribute value using regex pattern.

    Args:
        attribute_value: The attribute value (list, string, etc.)
        pattern: Regex pattern to extract references

    Returns:
        List of extracted resource references
    """
    references = []

    if isinstance(attribute_value, list):
        for item in attribute_value:
            if isinstance(item, str):
                matches = re.findall(pattern, item)
                references.extend(matches)
    elif isinstance(attribute_value, str):
        matches = re.findall(pattern, attribute_value)
        references.extend(matches)

    return references


def find_matching_node_in_graphdict(
    original_resource: str,
    graphdict: Dict[str, List[str]],
    provider_config: Dict[str, Any],
) -> List[str]:
    """Find matching nodes in graphdict after consolidation.

    Handles resource renaming during consolidation (e.g., aws_lb.main -> aws_alb.elb).

    Args:
        original_resource: Original resource name from all_resource
        graphdict: Current graphdict (post-consolidation)
        provider_config: Provider-specific configuration

    Returns:
        List of matching node names in graphdict
    """
    matching_nodes = []
    resource_type = original_resource.split(".")[0]

    # Get list of resource types that might be consolidated together
    # For AWS: aws_lb, aws_alb, aws_nlb are often consolidated
    consolidated_types = provider_config.get("resource_types", [resource_type])

    for node in graphdict.keys():
        if "~" in node:  # Skip already-numbered nodes
            continue

        node_type = node.split(".")[0]

        # Check if node type matches or is a consolidated variant
        if node_type == resource_type or node_type in consolidated_types:
            matching_nodes.append(node)

    return matching_nodes


def detect_and_set_counts(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect multi-instance resources and set synthetic count attributes.

    Uses configuration-driven patterns to detect resources across all cloud providers
    that should be expanded into numbered instances.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with count attributes set for detected resources
    """
    all_resource = tfdata.get("all_resource", {})
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})

    # Determine cloud provider from tfdata
    provider_detection = tfdata.get("provider_detection", {})
    primary_provider = provider_detection.get("primary_provider", "aws")

    # Get patterns for this provider
    patterns = MULTI_INSTANCE_PATTERNS.get(primary_provider, [])

    if not patterns:
        # No patterns defined for this provider, return unchanged
        return tfdata

    # Track resources to expand: {resource_key: (count, [associated_resources])}
    resources_to_expand: Dict[str, tuple[int, Set[str]]] = {}

    # Scan all_resource for matching patterns
    for tf_file, resources in all_resource.items():
        if not isinstance(resources, list):
            continue

        for resource_block in resources:
            for resource_type, instances in resource_block.items():
                if not isinstance(instances, dict):
                    continue

                # Check if this resource type matches any pattern
                for pattern in patterns:
                    if resource_type not in pattern["resource_types"]:
                        continue

                    # Found matching resource type, check trigger attributes
                    for instance_name, instance_data in instances.items():
                        resource_key = f"{resource_type}.{instance_name}"

                        # Check trigger attributes
                        for trigger_attr in pattern["trigger_attributes"]:
                            attr_value = instance_data.get(trigger_attr)
                            if not attr_value:
                                continue

                            # Extract references from attribute
                            references = extract_resource_references(
                                attr_value, pattern["resource_pattern"]
                            )

                            if len(references) > 1:
                                # Found multi-instance resource!
                                if resource_key not in resources_to_expand:
                                    resources_to_expand[resource_key] = (
                                        len(references),
                                        set(),
                                    )

                                # Extract associated resources to also expand
                                for assoc_attr in pattern["also_expand_attributes"]:
                                    assoc_value = instance_data.get(assoc_attr)
                                    if assoc_value:
                                        assoc_refs = extract_resource_references(
                                            assoc_value, pattern["resource_pattern"]
                                        )
                                        resources_to_expand[resource_key][1].update(
                                            assoc_refs
                                        )

    # Set count for detected resources
    for resource_key, (count, associated_resources) in resources_to_expand.items():
        resource_type = resource_key.split(".")[0]

        # Find matching pattern for type matching logic
        matching_pattern = None
        for pattern in patterns:
            if resource_type in pattern["resource_types"]:
                matching_pattern = pattern
                break

        # Find corresponding nodes in graphdict (handles consolidation)
        matching_nodes = find_matching_node_in_graphdict(
            resource_key, graphdict, matching_pattern or {}
        )

        # Set count for main resource
        for node in matching_nodes:
            if node not in meta_data:
                meta_data[node] = {}
            if not meta_data[node].get("count"):
                meta_data[node]["count"] = count

        # Set count for associated resources
        for assoc_resource in associated_resources:
            # Find matching nodes in graphdict for associated resource
            for node in graphdict.keys():
                if "~" in node:  # Skip already-numbered
                    continue

                # Match by checking if original resource name is related to node
                assoc_base = (
                    assoc_resource.split(".")[1] if "." in assoc_resource else ""
                )
                node_base = node.split(".")[1] if "." in node else ""

                # Check if this is the associated resource
                if assoc_base and (assoc_base in node_base or node_base in assoc_base):
                    node_type = node.split(".")[0]
                    assoc_type = assoc_resource.split(".")[0]

                    # Verify type matches
                    if (
                        node_type == assoc_type
                        or node_type in assoc_type
                        or assoc_type in node_type
                    ):
                        if node not in meta_data:
                            meta_data[node] = {}
                        if not meta_data[node].get("count"):
                            meta_data[node]["count"] = count

    tfdata["meta_data"] = meta_data
    return tfdata
