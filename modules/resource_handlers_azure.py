"""Azure resource-specific handlers for Terraform graph processing.

Handles special cases for Azure resources including resource groups, virtual networks,
network security groups, load balancers, and other Azure-specific relationships.
"""

from typing import Dict, List, Any
import modules.config.cloud_config_azure as cloud_config
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
    # Find all resource groups
    resource_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_resource_group"
    )

    if not resource_groups:
        return tfdata

    # For each resource, check if it has a resource_group_name attribute
    # and link it to the appropriate resource group
    for rg in resource_groups:
        rg_name = helpers.get_no_module_name(rg).split(".")[-1]

        # Find resources that reference this resource group
        for resource in sorted(tfdata["graphdict"].keys()):
            if resource == rg:
                continue

            resource_type = helpers.get_no_module_name(resource).split(".")[0]

            # Skip if already a child of this RG
            if resource in tfdata["graphdict"].get(rg, []):
                continue

            # Skip group nodes that are not VNets (VNets go directly under RG)
            if (
                resource_type in GROUP_NODES
                and resource_type != "azurerm_virtual_network"
            ):
                continue

            # Check metadata for resource_group_name reference
            if tfdata["meta_data"].get(resource):
                rg_ref = tfdata["meta_data"][resource].get("resource_group_name", "")
                # Check if this resource references our RG
                if rg in str(rg_ref) or rg_name in str(rg_ref):
                    # Add VNets directly under RG
                    if resource_type == "azurerm_virtual_network":
                        if resource not in tfdata["graphdict"][rg]:
                            tfdata["graphdict"][rg].append(resource)
                    # For non-VNet, non-group resources that aren't in a subnet yet
                    elif resource_type not in GROUP_NODES:
                        # Check if resource is already placed in a subnet or VNet
                        parent_list = helpers.list_of_parents(
                            tfdata["graphdict"], resource
                        )
                        in_hierarchy = any(
                            helpers.get_no_module_name(p).split(".")[0] in GROUP_NODES
                            for p in parent_list
                        )
                        if not in_hierarchy:
                            if resource not in tfdata["graphdict"][rg]:
                                tfdata["graphdict"][rg].append(resource)

    return tfdata


def azure_handle_vnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Virtual Network relationships.

    VNets are network boundary containers within Resource Groups.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VNet relationships configured
    """
    # Find all VNets
    vnets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_virtual_network"
    )

    if not vnets:
        return tfdata

    # Find all subnets and link them to their VNets
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_subnet")

    for vnet in vnets:
        vnet_name = helpers.get_no_module_name(vnet).split(".")[-1]

        for subnet in subnets:
            # Skip subnet associations
            if "association" in subnet:
                continue

            # Check if subnet references this VNet
            if tfdata["meta_data"].get(subnet):
                vnet_ref = tfdata["meta_data"][subnet].get("virtual_network_name", "")
                if vnet in str(vnet_ref) or vnet_name in str(vnet_ref):
                    if subnet not in tfdata["graphdict"].get(vnet, []):
                        tfdata["graphdict"][vnet].append(subnet)
                    # Remove subnet from other parents that aren't VNets
                    parent_list = helpers.list_of_parents(tfdata["graphdict"], subnet)
                    for parent in parent_list:
                        parent_type = helpers.get_no_module_name(parent).split(".")[0]
                        if parent != vnet and parent_type != "azurerm_virtual_network":
                            if subnet in tfdata["graphdict"].get(parent, []):
                                tfdata["graphdict"][parent].remove(subnet)

    return tfdata


def azure_handle_subnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Subnet relationships.

    Subnets are network segments within VNets.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Subnet relationships configured
    """
    # Find all subnets (excluding association resources)
    subnets = [
        s
        for s in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        )
        if "association" not in s
    ]

    if not subnets:
        return tfdata

    # Find network interfaces and their subnet associations
    nics = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_interface"
    )

    for subnet in subnets:
        subnet_name = helpers.get_no_module_name(subnet).split(".")[-1]

        # Link NICs to subnets based on ip_configuration.subnet_id
        for nic in nics:
            if tfdata["meta_data"].get(nic):
                ip_config = tfdata["meta_data"][nic].get("ip_configuration", "")
                if subnet in str(ip_config) or subnet_name in str(ip_config):
                    if nic not in tfdata["graphdict"].get(subnet, []):
                        tfdata["graphdict"][subnet].append(nic)

        # Find VMs and link them to subnets through their NICs
        vms = helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_virtual_machine"
        )
        vms.extend(
            helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "azurerm_linux_virtual_machine"
            )
        )
        vms.extend(
            helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "azurerm_windows_virtual_machine"
            )
        )

        for vm in vms:
            # Check if VM is connected to a NIC that's in this subnet
            vm_nic_refs = (
                tfdata["meta_data"].get(vm, {}).get("network_interface_ids", "")
            )
            for nic in nics:
                if nic in str(vm_nic_refs) or nic.split(".")[-1] in str(vm_nic_refs):
                    # If this NIC is in our subnet, put VM under the subnet
                    if nic in tfdata["graphdict"].get(subnet, []):
                        if vm not in tfdata["graphdict"].get(subnet, []):
                            tfdata["graphdict"][subnet].append(vm)
                        # Remove VM from NIC's children (VM is now direct child of subnet)
                        if vm in tfdata["graphdict"].get(nic, []):
                            tfdata["graphdict"][nic].remove(vm)

    return tfdata


def azure_handle_nsg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Network Security Group relationships.

    NSGs can be associated with Subnets or Network Interfaces.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with NSG relationships configured
    """
    # Find all NSGs
    nsgs = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_security_group"
    )

    # Filter out association resources from the NSG list
    nsgs = [n for n in nsgs if "association" not in n]

    if not nsgs:
        return tfdata

    # Find subnet-NSG associations
    subnet_nsg_associations = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_subnet_network_security_group_association"
    )

    # Find NIC-NSG associations
    nic_nsg_associations = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_interface_security_group_association"
    )

    # Process subnet-NSG associations
    for assoc in subnet_nsg_associations:
        if not tfdata["meta_data"].get(assoc):
            continue

        subnet_id = tfdata["meta_data"][assoc].get("subnet_id", "")
        nsg_id = tfdata["meta_data"][assoc].get("network_security_group_id", "")

        # Find the subnet and NSG
        target_subnet = None
        target_nsg = None

        for subnet in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        ):
            if "association" in subnet:
                continue
            if subnet in str(subnet_id) or subnet.split(".")[-1] in str(subnet_id):
                target_subnet = subnet
                break

        for nsg in nsgs:
            if nsg in str(nsg_id) or nsg.split(".")[-1] in str(nsg_id):
                target_nsg = nsg
                break

        # Link NSG to subnet - NSG becomes a container for subnet's resources
        if target_subnet and target_nsg:
            # Get resources currently in the subnet
            subnet_resources = list(tfdata["graphdict"].get(target_subnet, []))

            # Add NSG to subnet
            if target_nsg not in tfdata["graphdict"].get(target_subnet, []):
                tfdata["graphdict"][target_subnet].append(target_nsg)

            # Move non-group resources from subnet to NSG
            for resource in subnet_resources:
                resource_type = helpers.get_no_module_name(resource).split(".")[0]
                if resource_type not in GROUP_NODES and resource != target_nsg:
                    # Add resource to NSG
                    if resource not in tfdata["graphdict"].get(target_nsg, []):
                        tfdata["graphdict"][target_nsg].append(resource)
                    # Remove from direct subnet connection
                    if resource in tfdata["graphdict"].get(target_subnet, []):
                        tfdata["graphdict"][target_subnet].remove(resource)

        # Remove the association resource from graph (it's a linking resource)
        if assoc in tfdata["graphdict"]:
            del tfdata["graphdict"][assoc]

    # Process NIC-NSG associations
    for assoc in nic_nsg_associations:
        if not tfdata["meta_data"].get(assoc):
            continue

        nic_id = tfdata["meta_data"][assoc].get("network_interface_id", "")
        nsg_id = tfdata["meta_data"][assoc].get("network_security_group_id", "")

        # Find the NIC and NSG
        target_nic = None
        target_nsg = None

        for nic in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_network_interface"
        ):
            if nic in str(nic_id) or nic.split(".")[-1] in str(nic_id):
                target_nic = nic
                break

        for nsg in nsgs:
            if nsg in str(nsg_id) or nsg.split(".")[-1] in str(nsg_id):
                target_nsg = nsg
                break

        # Link NIC to NSG
        if target_nic and target_nsg:
            if target_nic not in tfdata["graphdict"].get(target_nsg, []):
                tfdata["graphdict"][target_nsg].append(target_nic)

        # Remove the association resource from graph
        if assoc in tfdata["graphdict"]:
            del tfdata["graphdict"][assoc]

    return tfdata


def azure_handle_vmss(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure VM Scale Set relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VMSS relationships configured
    """
    # Find all VMSS resources
    vmss_list = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_virtual_machine_scale_set"
    )

    if not vmss_list:
        return tfdata

    # Find subnets and load balancers
    subnets = [
        s
        for s in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        )
        if "association" not in s
    ]
    load_balancers = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_lb"
    )

    for vmss in vmss_list:
        if not tfdata["meta_data"].get(vmss):
            continue

        # Check network_profile for subnet references
        network_profile = tfdata["meta_data"][vmss].get("network_profile", "")

        # Link VMSS to subnet
        for subnet in subnets:
            subnet_name = subnet.split(".")[-1]
            if subnet in str(network_profile) or subnet_name in str(network_profile):
                if vmss not in tfdata["graphdict"].get(subnet, []):
                    tfdata["graphdict"][subnet].append(vmss)
                break

        # Check for load balancer backend pool associations
        lb_backend = tfdata["meta_data"][vmss].get(
            "load_balancer_backend_address_pool_ids", ""
        )
        for lb in load_balancers:
            lb_name = lb.split(".")[-1]
            if lb in str(lb_backend) or lb_name in str(lb_backend):
                # Link LB to VMSS
                if vmss not in tfdata["graphdict"].get(lb, []):
                    tfdata["graphdict"][lb].append(vmss)

    return tfdata


def azure_handle_appgw(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Application Gateway relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Application Gateway relationships configured
    """
    # Find all Application Gateways
    appgws = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_application_gateway"
    )

    if not appgws:
        return tfdata

    # Find subnets
    subnets = [
        s
        for s in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        )
        if "association" not in s
    ]

    for appgw in appgws:
        if not tfdata["meta_data"].get(appgw):
            continue

        # Check gateway_ip_configuration for subnet references
        gateway_ip_config = tfdata["meta_data"][appgw].get(
            "gateway_ip_configuration", ""
        )

        # Link App Gateway to subnet
        for subnet in subnets:
            subnet_name = subnet.split(".")[-1]
            if subnet in str(gateway_ip_config) or subnet_name in str(
                gateway_ip_config
            ):
                # App Gateway typically goes in its own subnet, add it under subnet
                if appgw not in tfdata["graphdict"].get(subnet, []):
                    tfdata["graphdict"][subnet].append(appgw)
                break

        # Check backend_address_pool for backend references
        backend_pools = tfdata["meta_data"][appgw].get("backend_address_pool", "")

        # Find VMs, NICs, or IP addresses referenced in backend pools
        if backend_pools:
            # Look for FQDN or IP references to link to backend resources
            vms = helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "azurerm_virtual_machine"
            )
            for vm in vms:
                vm_name = vm.split(".")[-1]
                if vm in str(backend_pools) or vm_name in str(backend_pools):
                    if vm not in tfdata["graphdict"].get(appgw, []):
                        tfdata["graphdict"][appgw].append(vm)

            # Link to VMSS if referenced
            vmss_list = helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "azurerm_virtual_machine_scale_set"
            )
            for vmss in vmss_list:
                vmss_name = vmss.split(".")[-1]
                if vmss in str(backend_pools) or vmss_name in str(backend_pools):
                    if vmss not in tfdata["graphdict"].get(appgw, []):
                        tfdata["graphdict"][appgw].append(vmss)

    return tfdata


# azure_handle_sharedgroup REMOVED - Decision 9: Shared services grouping
# is now core functionality in graphmaker.py (group_shared_services_core)
# instead of a handler. This eliminates per-provider duplication.


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
    # Match NSGs to Subnets by suffix pattern
    tfdata["graphdict"] = match_nsg_to_subnets(tfdata["graphdict"])

    # Match NICs to VMs
    tfdata["graphdict"] = match_nic_to_vm(
        tfdata["graphdict"], tfdata.get("meta_data", {})
    )

    # Clean up orphaned resources
    tfdata["graphdict"] = remove_empty_groups(tfdata["graphdict"])

    return tfdata


def match_nsg_to_subnets(graphdict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Match NSGs to subnets by suffix pattern.

    Args:
        graphdict: Resource graph dictionary

    Returns:
        Updated graphdict with NSG-subnet matches
    """
    result = dict(graphdict)
    suffix_pattern = r"~(\d+)$"

    # Find NSGs and subnets with numbered suffixes
    nsgs = [
        k
        for k in graphdict.keys()
        if "azurerm_network_security_group" in k and "association" not in k
    ]
    subnets = [
        k for k in graphdict.keys() if "azurerm_subnet" in k and "association" not in k
    ]

    for subnet in subnets:
        subnet_match = re.search(suffix_pattern, subnet)
        if subnet_match:
            subnet_suffix = subnet_match.group(1)

            # Find NSGs with matching suffix
            for nsg in nsgs:
                nsg_match = re.search(suffix_pattern, nsg)
                if nsg_match and nsg_match.group(1) == subnet_suffix:
                    if nsg not in result.get(subnet, []):
                        result[subnet].append(nsg)

    return result


def match_nic_to_vm(
    graphdict: Dict[str, List[str]], meta_data: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Match NICs to VMs based on network_interface_ids reference.

    Args:
        graphdict: Resource graph dictionary
        meta_data: Resource metadata

    Returns:
        Updated graphdict with NIC-VM matches
    """
    result = dict(graphdict)

    nics = [
        k
        for k in graphdict.keys()
        if "azurerm_network_interface" in k and "association" not in k
    ]
    vms = [
        k
        for k in graphdict.keys()
        if any(
            vm_type in k
            for vm_type in [
                "azurerm_virtual_machine",
                "azurerm_linux_virtual_machine",
                "azurerm_windows_virtual_machine",
            ]
        )
    ]

    for vm in vms:
        if not meta_data.get(vm):
            continue

        nic_refs = str(meta_data[vm].get("network_interface_ids", ""))

        for nic in nics:
            nic_name = nic.split(".")[-1]
            if nic in nic_refs or nic_name in nic_refs:
                # Add VM to NIC's connections
                if vm not in result.get(nic, []):
                    result[nic].append(vm)

    return result


def remove_empty_groups(graphdict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Remove empty group nodes from graph.

    Args:
        graphdict: Resource graph dictionary

    Returns:
        Updated graphdict with empty groups removed
    """
    result = dict(graphdict)

    # Find empty groups
    empty_groups = []
    for resource, connections in result.items():
        resource_type = helpers.get_no_module_name(resource).split(".")[0]
        if resource_type in GROUP_NODES and not connections:
            empty_groups.append(resource)

    # Remove empty groups
    for group in empty_groups:
        del result[group]

    return result
