"""GCP resource-specific handlers for Terraform graph processing.

Handles special cases for GCP resources including projects, VPCs, subnets,
firewall rules, load balancers, and other GCP-specific relationships.
"""

from typing import Dict, List, Any
import modules.config.cloud_config_gcp as cloud_config
import modules.helpers as helpers
from ast import literal_eval
import re
import copy

REVERSE_ARROW_LIST = cloud_config.GCP_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.GCP_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.GCP_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.GCP_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.GCP_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.GCP_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.GCP_SHARED_SERVICES
DISCONNECT_SERVICES = cloud_config.GCP_DISCONNECT_LIST


def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle special resource cases and disconnections for GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with special cases handled
    """
    # Remove connections to services specified in disconnect services
    for r in sorted(tfdata["graphdict"].keys()):
        for d in DISCONNECT_SERVICES:
            if d in r:
                tfdata["graphdict"][r] = []
    return tfdata


def gcp_handle_project(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Project relationships.

    Projects are top-level containers in GCP. All GCP resources belong to a Project.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Project relationships configured
    """
    # TODO: Implement Project handling in Phase 4 (US2)
    # - Group all resources by their project attribute
    # - Create hierarchical structure: Project > VPC > Subnet > Resources
    return tfdata


def gcp_handle_vpc(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP VPC (Virtual Private Cloud) relationships.

    VPCs are global network containers in GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VPC relationships configured
    """
    # TODO: Implement VPC handling in Phase 4 (US2)
    # - Link VPCs to their Projects
    # - Group Subnets within VPCs
    # - VPCs are global in GCP (not regional)
    return tfdata


def gcp_handle_subnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Subnet relationships.

    Subnets are regional network segments within VPCs in GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Subnet relationships configured
    """
    # TODO: Implement Subnet handling in Phase 4 (US2)
    # - Link Subnets to their VPCs
    # - Group resources within Subnets
    # - Handle regional placement
    return tfdata


def gcp_handle_firewall(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Firewall Rule relationships.

    Firewall rules are applied at the VPC level in GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Firewall Rule relationships configured
    """
    # TODO: Implement Firewall handling in Phase 4 (US2)
    # - Associate Firewall Rules with VPCs
    # - Handle target tags and service accounts
    return tfdata


def gcp_handle_gke(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP GKE (Google Kubernetes Engine) cluster relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with GKE relationships configured
    """
    # TODO: Implement GKE handling in Phase 4 (US2)
    # - Link GKE clusters to Subnets
    # - Handle node pools
    # - Link to Container Registry (GCR)
    return tfdata


def gcp_handle_instance_group(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Compute Instance Group relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Instance Group relationships configured
    """
    # TODO: Implement Instance Group handling in Phase 4 (US2)
    # - Link instance groups to zones
    # - Handle autoscaling
    return tfdata


def gcp_handle_backend_service(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Backend Service relationships (Load Balancing).

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Backend Service relationships configured
    """
    # TODO: Implement Backend Service handling in Phase 4 (US2)
    # - Link to instance groups
    # - Link to health checks
    # - Link to forwarding rules
    return tfdata


def gcp_handle_sharedgroup(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group shared GCP services into a shared services group.

    Shared services include KMS, Cloud Storage, Logging, Monitoring, GCR, etc.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with shared services grouped
    """
    # Find all shared services and group them
    for node in sorted(tfdata["graphdict"].keys()):
        substring_match = [s for s in SHARED_SERVICES if s in node]
        if substring_match:
            # Create shared services group if needed
            if not tfdata["graphdict"].get("google_group.shared_services"):
                tfdata["graphdict"]["google_group.shared_services"] = []
                tfdata["meta_data"]["google_group.shared_services"] = {}
            # Add node to shared services group
            if node not in tfdata["graphdict"]["google_group.shared_services"]:
                tfdata["graphdict"]["google_group.shared_services"].append(node)

    # Replace consolidated nodes with their consolidated names
    if tfdata["graphdict"].get("google_group.shared_services"):
        for service in sorted(
            list(tfdata["graphdict"]["google_group.shared_services"])
        ):
            if helpers.consolidated_node_check(service, tfdata):
                tfdata["graphdict"]["google_group.shared_services"] = list(
                    map(
                        lambda x: x.replace(
                            service, helpers.consolidated_node_check(service, tfdata)
                        ),
                        tfdata["graphdict"]["google_group.shared_services"],
                    )
                )
    return tfdata


def random_string_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Remove random string resources from graph.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with random strings removed
    """
    randoms = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "random_string.")
    for r in list(randoms):
        del tfdata["graphdict"][r]
    return tfdata


def match_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Match GCP resources based on patterns and dependencies.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with resources matched
    """
    # TODO: Implement GCP-specific resource matching in Phase 4 (US2)
    # - Match firewall rules to VPCs
    # - Match instances to subnets
    # - Match load balancers to backend services
    return tfdata
