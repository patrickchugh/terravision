"""Azure resource-specific handlers for Terraform graph processing.

Handles special cases for Azure resources including resource groups, virtual networks,
network security groups, load balancers, and other Azure-specific relationships.
"""

from typing import Dict, List, Any
import modules.cloud_config_azure as cloud_config
import modules.helpers as helpers
from ast import literal_eval
import re
import copy

REVERSE_ARROW_LIST = cloud_config.AZURE_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AZURE_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.AZURE_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AZURE_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AZURE_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.AZURE_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.AZURE_SHARED_SERVICES
DISCONNECT_SERVICES = cloud_config.AZURE_DISCONNECT_LIST


def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle special resource cases and disconnections for Azure.

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


def azure_handle_resource_group(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Resource Group relationships.

    Resource Groups are top-level containers in Azure. All Azure resources
    belong to a Resource Group.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Resource Group relationships configured
    """
    # TODO: Implement Resource Group handling in Phase 3 (US1)
    # - Group all resources by their resource_group_name attribute
    # - Create hierarchical structure: RG > VNet > Subnet > Resources
    return tfdata


def azure_handle_vnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Virtual Network relationships.

    VNets are network boundary containers within Resource Groups.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VNet relationships configured
    """
    # TODO: Implement VNet handling in Phase 3 (US1)
    # - Link VNets to their Resource Groups
    # - Group Subnets within VNets
    return tfdata


def azure_handle_subnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Subnet relationships.

    Subnets are network segments within VNets.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Subnet relationships configured
    """
    # TODO: Implement Subnet handling in Phase 3 (US1)
    # - Link Subnets to their VNets
    # - Group resources within Subnets
    return tfdata


def azure_handle_nsg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Network Security Group relationships.

    NSGs can be associated with Subnets or Network Interfaces.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with NSG relationships configured
    """
    # TODO: Implement NSG handling in Phase 3 (US1)
    # - Associate NSGs with Subnets or NICs
    # - Handle azurerm_subnet_network_security_group_association
    # - Handle azurerm_network_interface_security_group_association
    return tfdata


def azure_handle_vmss(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure VM Scale Set relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VMSS relationships configured
    """
    # TODO: Implement VMSS handling in Phase 3 (US1)
    # - Link VMSS to Subnets
    # - Handle load balancer associations
    return tfdata


def azure_handle_appgw(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Application Gateway relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Application Gateway relationships configured
    """
    # TODO: Implement Application Gateway handling in Phase 3 (US1)
    # - Link to backend pools
    # - Link to Subnets
    return tfdata


def azure_handle_sharedgroup(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group shared Azure services into a shared services group.

    Shared services include Key Vault, Monitor, Log Analytics, ACR, etc.

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
            if not tfdata["graphdict"].get("azurerm_group.shared_services"):
                tfdata["graphdict"]["azurerm_group.shared_services"] = []
                tfdata["meta_data"]["azurerm_group.shared_services"] = {}
            # Add node to shared services group
            if node not in tfdata["graphdict"]["azurerm_group.shared_services"]:
                tfdata["graphdict"]["azurerm_group.shared_services"].append(node)

    # Replace consolidated nodes with their consolidated names
    if tfdata["graphdict"].get("azurerm_group.shared_services"):
        for service in sorted(list(tfdata["graphdict"]["azurerm_group.shared_services"])):
            if helpers.consolidated_node_check(service):
                tfdata["graphdict"]["azurerm_group.shared_services"] = list(
                    map(
                        lambda x: x.replace(
                            service, helpers.consolidated_node_check(service)
                        ),
                        tfdata["graphdict"]["azurerm_group.shared_services"],
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
    """Match Azure resources based on patterns and dependencies.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with resources matched
    """
    # TODO: Implement Azure-specific resource matching in Phase 3 (US1)
    # - Match NSGs to Subnets
    # - Match NICs to Subnets
    # - Match VMs to NICs
    return tfdata
