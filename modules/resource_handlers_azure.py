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

        # NOTE: VM placement into subnets now happens in match_resources()
        # after create_multiple_resources() completes numbering

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
    """Handle Azure VM Scale Set relationships and zone placement.

    Creates availability zone containers for VMSS instances that are expanded
    across multiple zones.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VMSS relationships and zone containers configured
    """
    # Find all VMSS resources (including numbered instances)
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

    # Separate numbered and non-numbered VMSS
    numbered_vmss = [v for v in vmss_list if "~" in v]
    unnumbered_vmss = [v for v in vmss_list if "~" not in v]

    # Handle non-numbered VMSS (original logic)
    for vmss in unnumbered_vmss:
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

    # Handle numbered VMSS - create zone containers
    if numbered_vmss:
        # Group numbered VMSS by base name
        vmss_by_base = {}
        for vmss in numbered_vmss:
            base_name = vmss.split("~")[0]
            if base_name not in vmss_by_base:
                vmss_by_base[base_name] = []
            vmss_by_base[base_name].append(vmss)

        for base_name, instances in vmss_by_base.items():
            # Get metadata from first instance
            if instances and tfdata["meta_data"].get(instances[0]):
                metadata = tfdata["meta_data"][instances[0]]
                zones_attr = metadata.get("zones", [])

                # Only create zone containers if zones attribute exists and has values
                if zones_attr and isinstance(zones_attr, list):
                    # Find parent subnet for this VMSS
                    parent_subnet = None
                    network_profile = metadata.get("network_profile", "")
                    for subnet in subnets:
                        subnet_name = subnet.split(".")[-1]
                        if subnet in str(network_profile) or subnet_name in str(
                            network_profile
                        ):
                            parent_subnet = subnet
                            break

                    if parent_subnet:
                        # Create zone container for each instance
                        for i, vmss_instance in enumerate(sorted(instances), start=1):
                            if i <= len(zones_attr):
                                zone_id = zones_attr[i - 1]
                                # Create zone node name
                                zone_node = f"tv_azurerm_zone.zone_{zone_id}"

                                # Create zone node in graphdict if it doesn't exist
                                if zone_node not in tfdata["graphdict"]:
                                    tfdata["graphdict"][zone_node] = []
                                    tfdata["meta_data"][zone_node] = {
                                        "zone_id": zone_id,
                                        "name": f"Availability Zone {zone_id}",
                                    }

                                # Place VMSS instance inside zone
                                if vmss_instance not in tfdata["graphdict"][zone_node]:
                                    tfdata["graphdict"][zone_node].append(vmss_instance)

                                # Remove VMSS instance from subnet direct children
                                if vmss_instance in tfdata["graphdict"].get(
                                    parent_subnet, []
                                ):
                                    tfdata["graphdict"][parent_subnet].remove(
                                        vmss_instance
                                    )

                                # Add zone to subnet if not already there
                                if zone_node not in tfdata["graphdict"].get(
                                    parent_subnet, []
                                ):
                                    tfdata["graphdict"][parent_subnet].append(zone_node)

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

    # Place VMs into subnets (runs after numbering to handle numbered VMs correctly)
    tfdata = place_vms_in_subnets(tfdata)

    # Create availability zone containers for numbered VM instances
    # This must run AFTER place_vms_in_subnets so VMs are in subnet
    tfdata = create_vm_zone_containers(tfdata)

    # Create availability zone containers for numbered VMSS instances
    # This must run AFTER create_multiple_resources so numbered instances exist
    tfdata = create_zone_containers(tfdata)

    # Connect Load Balancers and Application Gateways to backend VMs
    tfdata = connect_lb_to_backend_vms(tfdata)

    # Clean up orphaned resources
    tfdata["graphdict"] = remove_empty_groups(tfdata["graphdict"])

    return tfdata


def create_vm_zone_containers(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Create availability zone containers for numbered VM instances.

    This function runs AFTER create_multiple_resources, so numbered VM instances
    like vm~1, vm~2, vm~3 already exist. It creates zone containers and places
    each instance in its corresponding zone.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with zone containers created
    """
    # Find all numbered VM instances (individual VMs, not VMSS)
    numbered_vms = [
        k
        for k in tfdata["graphdict"].keys()
        if (
            "azurerm_linux_virtual_machine" in k
            or "azurerm_windows_virtual_machine" in k
            or "azurerm_virtual_machine" in k
        )
        and "~" in k
        and "scale_set" not in k  # Exclude VMSS
    ]

    if not numbered_vms:
        return tfdata

    # Find subnets
    subnets = [
        s
        for s in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        )
        if "association" not in s
    ]

    # Group VMs by subnet
    vms_by_subnet = {}
    for vm in numbered_vms:
        # Find which subnet contains this VM
        vm_subnet = None
        for subnet in subnets:
            if vm in tfdata["graphdict"].get(subnet, []):
                vm_subnet = subnet
                break

        if vm_subnet:
            if vm_subnet not in vms_by_subnet:
                vms_by_subnet[vm_subnet] = []
            vms_by_subnet[vm_subnet].append(vm)

    # For each subnet with zoned VMs, create zone containers
    for subnet, vms in vms_by_subnet.items():
        # Check if VMs have zone attributes
        zones_used = {}
        for vm in vms:
            vm_metadata = tfdata["meta_data"].get(vm, {})
            zone = vm_metadata.get("zone", "")
            if zone:
                # Remove quotes if present
                zone = str(zone).strip('"').strip("'")

                # Resolve count.index expressions for numbered instances
                # e.g., "${tostring(count.index + 1)}" with vm~2 should become "2"
                if "count.index" in zone and "~" in vm:
                    # Extract instance number from vm~X
                    instance_num = int(vm.split("~")[1])
                    # count.index is 0-based, so instance 1 has count.index = 0
                    count_index = instance_num - 1
                    # Replace count.index with the actual value
                    zone = zone.replace("count.index", str(count_index))
                    # Evaluate simple expressions like "0 + 1" -> "1"
                    # Remove ${} and tostring() wrappers
                    zone = zone.replace("${", "").replace("}", "")
                    zone = zone.replace("tostring(", "").replace(")", "")
                    # Evaluate the expression
                    try:
                        zone = str(eval(zone))
                    except Exception:
                        # If evaluation fails, keep original
                        pass

                if zone not in zones_used:
                    zones_used[zone] = []
                zones_used[zone].append(vm)

        # If no zones found, skip this subnet
        if not zones_used:
            continue

        # Create zone containers
        for zone_id, zone_vms in zones_used.items():
            zone_name = f"tv_azurerm_zone.zone{zone_id}"

            # Create zone container node
            if zone_name not in tfdata["graphdict"]:
                tfdata["graphdict"][zone_name] = []
                tfdata["meta_data"][zone_name] = {
                    "zone_id": zone_id,
                    "type": "tv_azurerm_zone",
                }

            # Move VMs from subnet to zone
            for vm in zone_vms:
                if vm in tfdata["graphdict"].get(subnet, []):
                    tfdata["graphdict"][subnet].remove(vm)

                if vm not in tfdata["graphdict"][zone_name]:
                    tfdata["graphdict"][zone_name].append(vm)

            # Add zone to subnet
            if zone_name not in tfdata["graphdict"].get(subnet, []):
                tfdata["graphdict"][subnet].append(zone_name)

    return tfdata


def create_zone_containers(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Create availability zone containers for numbered zonal resources (VMSS, AKS node pools).

    This function runs AFTER create_multiple_resources, so numbered instances
    like vmss~1, vmss~2, vmss~3 or node_pool~1, node_pool~2, node_pool~3 already exist.
    It creates zone containers and places each instance in its corresponding zone.

    Supported resource types:
    - azurerm_linux_virtual_machine_scale_set
    - azurerm_windows_virtual_machine_scale_set
    - azurerm_virtual_machine_scale_set
    - azurerm_kubernetes_cluster_node_pool

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with zone containers created
    """
    # Resource types that support zones
    ZONAL_RESOURCE_TYPES = [
        "azurerm_linux_virtual_machine_scale_set",
        "azurerm_windows_virtual_machine_scale_set",
        "azurerm_virtual_machine_scale_set",
        "azurerm_kubernetes_cluster_node_pool",
    ]

    # Find all numbered zonal instances
    numbered_zonal = [
        k
        for k in tfdata["graphdict"].keys()
        if any(res_type in k for res_type in ZONAL_RESOURCE_TYPES) and "~" in k
    ]

    if not numbered_zonal:
        return tfdata

    # Find subnets
    subnets = [
        s
        for s in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        )
        if "association" not in s
    ]

    # Group numbered resources by base name
    resources_by_base = {}
    for resource in numbered_zonal:
        base_name = resource.split("~")[0]
        if base_name not in resources_by_base:
            resources_by_base[base_name] = []
        resources_by_base[base_name].append(resource)

    for base_name, instances in resources_by_base.items():
        # Get zones from metadata
        metadata = tfdata["meta_data"].get(base_name) or tfdata.get(
            "original_metadata", {}
        ).get(base_name, {})
        if not metadata:
            metadata = tfdata["meta_data"].get(instances[0], {})

        zones_attr_raw = metadata.get("zones", []) if metadata else []

        # zones might be a string representation of a list, convert it
        if isinstance(zones_attr_raw, str):
            try:
                zones_attr = literal_eval(zones_attr_raw)
            except:
                zones_attr = []
        else:
            zones_attr = zones_attr_raw

        # Get subnet reference from all_resource (original Terraform config)
        subnet_ref = None
        res_type_parts = base_name.split(".")
        res_type = res_type_parts[0]
        res_name = res_type_parts[1] if len(res_type_parts) > 1 else None

        if res_name:
            for file_path, resources in tfdata.get("all_resource", {}).items():
                if not isinstance(resources, list):
                    continue
                for res_block in resources:
                    if res_type in res_block and res_name in res_block.get(
                        res_type, {}
                    ):
                        res_data = res_block[res_type][res_name]

                        # Try different subnet reference patterns based on resource type
                        subnet_id_raw = None

                        # AKS node pools use vnet_subnet_id directly
                        if "kubernetes_cluster_node_pool" in res_type:
                            subnet_id_raw = res_data.get("vnet_subnet_id", "")

                        # VMSS uses network_interface.ip_configuration.subnet_id
                        if not subnet_id_raw:
                            ni = res_data.get("network_interface", [{}])
                            if ni and isinstance(ni, list) and len(ni) > 0:
                                ipc = ni[0].get("ip_configuration", [{}])
                                if ipc and isinstance(ipc, list) and len(ipc) > 0:
                                    subnet_id_raw = ipc[0].get("subnet_id", "")

                        # Extract subnet name from ${azurerm_subnet.main.id}
                        if subnet_id_raw:
                            match = re.search(
                                r"\$?\{?([^.]+\.[^.}]+)", str(subnet_id_raw)
                            )
                            if match:
                                subnet_ref = match.group(1)
                        break
                if subnet_ref:
                    break

        if zones_attr and isinstance(zones_attr, list):

            # Only create zone containers if zones attribute exists and has values
            if zones_attr and isinstance(zones_attr, list) and subnet_ref:
                # Use the subnet reference from all_resource
                parent_subnet = subnet_ref if subnet_ref in subnets else None

                # Fallback: check which subnet contains any instance
                if not parent_subnet:
                    for subnet in subnets:
                        for instance in instances:
                            if instance in tfdata["graphdict"].get(subnet, []):
                                parent_subnet = subnet
                                break
                        if parent_subnet:
                            break

                if parent_subnet:
                    # Create zone container for each instance
                    for i, res_instance in enumerate(sorted(instances), start=1):
                        if i <= len(zones_attr):
                            zone_id = zones_attr[i - 1]
                            # Create zone node name
                            zone_node = f"tv_azurerm_zone.zone_{zone_id}"

                            # Create zone node in graphdict if it doesn't exist
                            if zone_node not in tfdata["graphdict"]:
                                tfdata["graphdict"][zone_node] = []
                                tfdata["meta_data"][zone_node] = {
                                    "zone_id": zone_id,
                                    "name": f"Availability Zone {zone_id}",
                                }

                            # Place instance inside zone
                            if res_instance not in tfdata["graphdict"][zone_node]:
                                tfdata["graphdict"][zone_node].append(res_instance)

                            # Remove instance from subnet direct children
                            if res_instance in tfdata["graphdict"].get(
                                parent_subnet, []
                            ):
                                tfdata["graphdict"][parent_subnet].remove(res_instance)

                            # Add zone to subnet if not already there
                            if zone_node not in tfdata["graphdict"].get(
                                parent_subnet, []
                            ):
                                tfdata["graphdict"][parent_subnet].append(zone_node)

                    # Remove the base node after creating numbered instances in zones
                    if base_name in tfdata["graphdict"]:
                        # Check if any resources connect TO the base node
                        base_connections = tfdata["graphdict"][base_name]

                        # Delete the base node from graphdict
                        del tfdata["graphdict"][base_name]

                        # Remove base node from any parent's children list
                        for node in tfdata["graphdict"]:
                            if base_name in tfdata["graphdict"][node]:
                                tfdata["graphdict"][node].remove(base_name)

                        # If the base node had connections, expand them to numbered instances
                        # For example, if base VMSS → Load Balancer, then vmss~1 → LB, vmss~2 → LB, vmss~3 → LB
                        if base_connections:
                            for instance in instances:
                                if instance not in tfdata["graphdict"]:
                                    tfdata["graphdict"][instance] = []
                                # Add base node's connections to each numbered instance
                                for conn in base_connections:
                                    if conn not in tfdata["graphdict"][instance]:
                                        tfdata["graphdict"][instance].append(conn)

    return tfdata


def place_vms_in_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Place VMs into subnets based on their NIC placements.

    This function runs AFTER create_multiple_resources so numbered VMs exist.
    It places VMs in the same subnet as their NICs for proper visual hierarchy.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VMs placed in subnets
    """
    # Find all subnets
    subnets = [
        s
        for s in helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_subnet"
        )
        if "association" not in s
    ]

    # Find all VMs (numbered and unnumbered)
    vms = []
    for vm_type in [
        "azurerm_virtual_machine",
        "azurerm_linux_virtual_machine",
        "azurerm_windows_virtual_machine",
    ]:
        vms.extend(helpers.list_of_dictkeys_containing(tfdata["graphdict"], vm_type))

    # Find all NICs
    nics = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_interface"
    )
    nics = [n for n in nics if "association" not in n]

    # For each subnet, find VMs whose NICs are in that subnet
    for subnet in subnets:
        subnet_nics = tfdata["graphdict"].get(subnet, [])

        for vm in vms:
            # Check if this VM's NIC is in this subnet
            vm_metadata = tfdata["meta_data"].get(vm, {})
            vm_nic_ids = vm_metadata.get("network_interface_ids", [])

            # Match VM to NIC by checking if any NIC in subnet matches VM's NIC reference
            for nic in subnet_nics:
                if "azurerm_network_interface" in nic:
                    # Check if this NIC is referenced by the VM
                    nic_name = helpers.get_no_module_name(nic)
                    if nic in str(vm_nic_ids) or nic_name in str(vm_nic_ids):
                        # Place VM in subnet if not already there
                        if vm not in tfdata["graphdict"].get(subnet, []):
                            tfdata["graphdict"][subnet].append(vm)
                        break

    # Clean up base NIC nodes that were numbered - remove them from subnets
    # This handles the case where the base NIC was added to subnet before numbering occurred
    for subnet in subnets:
        subnet_children = tfdata["graphdict"].get(subnet, [])[:]
        for child in subnet_children:
            if (
                "azurerm_network_interface" in child
                and "~" not in child
                and "association" not in child
            ):
                # Check if this base NIC has numbered instances
                # Handle both formats: base~1 and base[0]~1 (from count)
                child_prefix = child.rsplit(".", 1)[0]  # Get resource type prefix
                child_name = (
                    child.rsplit(".", 1)[1] if "." in child else ""
                )  # Get resource name

                numbered_versions = [
                    k
                    for k in tfdata["graphdict"].keys()
                    if "~" in k and child_name in k and "azurerm_network_interface" in k
                ]
                # If numbered versions exist, remove the base node reference
                if numbered_versions:
                    tfdata["graphdict"][subnet].remove(child)

    return tfdata


def connect_lb_to_backend_vms(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Connect Load Balancers and Application Gateways to backend VMs.

    This function runs AFTER create_multiple_resources so numbered VMs and NICs exist.
    It creates direct connections from LB/AppGW to backend VMs, bypassing association
    resources which are implementation details.

    The connection path is: LB → Association → NIC → VM
    We want to show: LB → VM (direct logical connection)

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with LB connections to backend VMs
    """
    # Find all Load Balancers (consolidated from azurerm_lb and azurerm_lb_backend_address_pool)
    load_balancers = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_lb"
    )
    load_balancers = [
        lb
        for lb in load_balancers
        if "association" not in lb and "probe" not in lb and "rule" not in lb
    ]

    # Find all Application Gateways
    app_gateways = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_application_gateway"
    )

    # Find all association resources (numbered and base)
    associations = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"],
        "azurerm_network_interface_backend_address_pool_association",
    )

    # Find all VMs (numbered)
    vms = []
    for vm_type in [
        "azurerm_virtual_machine",
        "azurerm_linux_virtual_machine",
        "azurerm_windows_virtual_machine",
    ]:
        vms.extend(helpers.list_of_dictkeys_containing(tfdata["graphdict"], vm_type))

    # Find all NICs
    nics = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_interface"
    )
    nics = [nic for nic in nics if "association" not in nic]

    # Process each Load Balancer
    for lb in load_balancers:
        lb_connections = tfdata["graphdict"].get(lb, [])
        backend_vms = []

        # Check if LB connects to any association resources
        lb_associations = [conn for conn in lb_connections if "association" in conn]

        # Find backend VMs using the original Terraform metadata
        # Association resources link NICs to backend pools via count index
        # We need to find which VMs use which NICs

        # Get the backend pool metadata to understand the relationship
        # Look in all_resource for the association definition
        for file_path, resources in tfdata.get("all_resource", {}).items():
            if not isinstance(resources, list):
                continue
            for res_block in resources:
                # Check if this block defines an association resource
                if (
                    "azurerm_network_interface_backend_address_pool_association"
                    in res_block
                ):
                    assoc_configs = res_block.get(
                        "azurerm_network_interface_backend_address_pool_association", {}
                    )

                    # Iterate through each association resource definition (e.g., "main")
                    for assoc_name, assoc_config in assoc_configs.items():
                        nic_ref = assoc_config.get("network_interface_id", "")

                        # Extract the NIC resource name from the reference
                        # Format: ${azurerm_network_interface.backend[count.index].id}
                        nic_match = re.search(
                            r"azurerm_network_interface\.(\w+)", str(nic_ref)
                        )
                        if nic_match:
                            nic_base_name = nic_match.group(1)

                            # Find all NICs matching this base name
                            matching_nics = [
                                nic for nic in nics if f".{nic_base_name}" in nic
                            ]

                            # For each NIC, find the VM that uses it
                            # Match by index pattern - NIC backend[0]~1 matches VM backend[0]~1
                            for nic in matching_nics:
                                nic_pattern = nic.split("azurerm_network_interface.")[
                                    -1
                                ]  # Get "backend[0]~1"

                                for vm in vms:
                                    vm_pattern = (
                                        vm.split("azurerm_linux_virtual_machine.")[-1]
                                        if "linux" in vm
                                        else (
                                            vm.split(
                                                "azurerm_windows_virtual_machine."
                                            )[-1]
                                            if "windows" in vm
                                            else vm.split("azurerm_virtual_machine.")[
                                                -1
                                            ]
                                        )
                                    )

                                    # Match if they have the same index pattern (e.g., backend[0]~1)
                                    if nic_pattern == vm_pattern:
                                        if vm not in backend_vms:
                                            backend_vms.append(vm)
                                        break

        # Add direct connections from LB to VMs
        for vm in backend_vms:
            if vm not in tfdata["graphdict"][lb]:
                tfdata["graphdict"][lb].append(vm)

        # Remove association connections (they're implementation details)
        for assoc in lb_associations:
            if assoc in tfdata["graphdict"][lb]:
                tfdata["graphdict"][lb].remove(assoc)

    # Process Application Gateways - convert NIC connections to VM connections
    for appgw in app_gateways:
        appgw_connections = tfdata["graphdict"].get(appgw, [])
        backend_vms = []

        # Find NICs that AppGW connects to
        appgw_nics = [
            conn for conn in appgw_connections if "azurerm_network_interface" in conn
        ]

        # For each NIC, find the VM that uses it
        for nic in appgw_nics:
            nic_pattern = nic.split("azurerm_network_interface.")[
                -1
            ]  # Get "backend[0]~1"

            for vm in vms:
                vm_pattern = (
                    vm.split("azurerm_linux_virtual_machine.")[-1]
                    if "linux" in vm
                    else (
                        vm.split("azurerm_windows_virtual_machine.")[-1]
                        if "windows" in vm
                        else vm.split("azurerm_virtual_machine.")[-1]
                    )
                )

                # Match if they have the same index pattern (e.g., backend[0]~1)
                if nic_pattern == vm_pattern:
                    if vm not in backend_vms:
                        backend_vms.append(vm)
                    break

        # Add direct connections from AppGW to VMs
        for vm in backend_vms:
            if vm not in tfdata["graphdict"][appgw]:
                tfdata["graphdict"][appgw].append(vm)

        # Remove NIC connections (replace with VM connections)
        for nic in appgw_nics:
            if nic in tfdata["graphdict"][appgw]:
                tfdata["graphdict"][appgw].remove(nic)

    # Clean up association resources from the graph entirely
    for assoc in associations:
        tfdata["graphdict"].pop(assoc, None)
        tfdata["meta_data"].pop(assoc, None)

        # Remove from any parent connections
        for node in list(tfdata["graphdict"].keys()):
            if assoc in tfdata["graphdict"].get(node, []):
                tfdata["graphdict"][node].remove(assoc)

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
