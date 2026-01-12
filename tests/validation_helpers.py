"""
TerraVision validation functions for graph integrity checks.

This module contains validation functions for checking diagram correctness,
hierarchy integrity, and rendering compatibility across cloud providers.
"""

from typing import Dict, List, Any


def validate_gcp_hierarchy_integrity(tfdata: Dict[str, Any]) -> List[str]:
    """
    Validate GCP hierarchy integrity (FR-008a, FR-008b).

    Ensures complete hierarchy chain is respected:
    Project → VPC → Region → Subnet → Zone → Resources

    Args:
        tfdata: Terraform data dictionary containing graphdict

    Returns:
        List of error messages (empty if valid)

    Requirements:
        - FR-008a/FR-008b: No hierarchy gaps - each level must have appropriate parent
    """
    errors = []
    graphdict = tfdata.get("graphdict", {})

    # Define GCP hierarchy rules: child_type → list of valid parent types
    hierarchy_rules = {
        "tv_gcp_zone.": {
            "valid_parents": ["google_compute_subnetwork."],
            "error_template": "Zone {node} has no subnet parent (FR-008a violation: "
            "zones MUST have subnet parent in GCP hierarchy)",
        },
        "google_compute_subnetwork.": {
            "valid_parents": ["google_compute_network.", "tv_gcp_region."],
            "error_template": "Subnet {node} has no region/VPC parent (FR-008b violation: "
            "subnets MUST have region or VPC parent in GCP hierarchy)",
        },
        "tv_gcp_region.": {
            "valid_parents": ["google_compute_network.", "google_project."],
            "error_template": "Region {node} has no VPC/Project parent (FR-008b violation: "
            "regions MUST have VPC or Project parent in GCP hierarchy)",
        },
        "google_compute_network.": {
            "valid_parents": ["google_project.", "tv_gcp_account."],
            "error_template": "VPC {node} has no Project/Account parent (FR-008b violation: "
            "VPCs MUST have Project or Account parent in GCP hierarchy)",
        },
    }

    # Check each node type for proper parent
    for node in graphdict:
        for node_prefix, rule in hierarchy_rules.items():
            if node.startswith(node_prefix):
                has_valid_parent = False
                for parent, children in graphdict.items():
                    if node in children:
                        # Check if parent matches any valid parent type
                        for valid_prefix in rule["valid_parents"]:
                            if parent.startswith(valid_prefix):
                                has_valid_parent = True
                                break
                    if has_valid_parent:
                        break

                if not has_valid_parent:
                    errors.append(rule["error_template"].format(node=node))
                break  # Only check once per node

    return errors


def validate_no_shared_gcp_connections(tfdata: Dict[str, Any]) -> List[str]:
    """
    Validate no shared connections between GCP group nodes.

    When multiple zones/subnets point to the same resource, graphviz
    cannot render correctly. Resources must be expanded with numbering.

    Args:
        tfdata: Terraform data dictionary containing graphdict

    Returns:
        List of error messages (empty if valid)

    Example violation:
        {
            "tv_gcp_zone.us-central1-a": ["google_compute_instance.web"],
            "tv_gcp_zone.us-central1-b": ["google_compute_instance.web"]
        }

    Solution: Expand to numbered instances:
        {
            "tv_gcp_zone.us-central1-a": ["google_compute_instance.web~1"],
            "tv_gcp_zone.us-central1-b": ["google_compute_instance.web~2"]
        }
    """
    errors = []
    graphdict = tfdata.get("graphdict", {})

    # Track which resources have multiple zone/subnet parents
    resource_parents = {}

    # GCP group nodes that should not share connections
    gcp_group_prefixes = ["tv_gcp_zone.", "google_compute_subnetwork."]

    for parent, children in graphdict.items():
        # Only check GCP group nodes
        if not any(parent.startswith(prefix) for prefix in gcp_group_prefixes):
            continue

        for child in children:
            # Skip already numbered resources (instance~1, instance~2)
            if "~" in child:
                continue

            if child not in resource_parents:
                resource_parents[child] = []
            resource_parents[child].append(parent)

    # Report resources with multiple group parents
    for resource, parents in resource_parents.items():
        if len(parents) > 1:
            errors.append(
                f"Resource {resource} has multiple zone/subnet parents: {parents}. "
                f"Resource must be expanded with numbered instances "
                f"(e.g., {resource}~1, {resource}~2)"
            )

    return errors
