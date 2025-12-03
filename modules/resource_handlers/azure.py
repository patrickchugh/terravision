"""Azure resource-specific handlers for Terraform graph processing.

Handles special cases for Azure resources including virtual networks, subnets,
network security groups, load balancers, and application gateways.
"""

from typing import Dict, List, Any
import modules.cloud_config as cloud_config
import modules.helpers as helpers
from modules.exceptions import MissingResourceError
from modules.utils.graph_utils import ensure_metadata
import copy
import click


def azure_handle_vnet_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Virtual Network and subnet relationships.

    Processes VNet/subnet structures similar to AWS VPC/subnet handling.
    Creates proper parent-child relationships between VNets and subnets.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VNet/subnet relationships configured

    Raises:
        MissingResourceError: When subnets exist but no VNets are found
    """
    # Find all VNet and subnet resources
    vnets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_virtual_network"
    )
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_subnet")

    # Validate prerequisites: subnets require VNets
    if subnets and not vnets:
        raise MissingResourceError(
            "azurerm_virtual_network",
            context={
                "handler": "azure_handle_vnet_subnets",
                "subnet_count": len(subnets),
                "message": "Found subnets but no VNets to attach them to",
            },
        )

    # Process each subnet to ensure proper VNet relationships
    for subnet in subnets:
        try:
            # Get subnet's virtual_network_name attribute from metadata
            subnet_metadata = tfdata.get("original_metadata", {}).get(subnet, {})
            vnet_ref = subnet_metadata.get("virtual_network_name")

            if not vnet_ref:
                click.echo(
                    click.style(
                        f"WARNING: Subnet {subnet} missing virtual_network_name reference",
                        fg="yellow",
                    )
                )
                continue

            # Find matching VNet by reference
            matching_vnet = None
            for vnet in vnets:
                if vnet_ref in vnet or helpers.get_no_module_name(vnet) in vnet_ref:
                    matching_vnet = vnet
                    break

            if matching_vnet:
                # Ensure subnet is connected to VNet
                if subnet not in tfdata["graphdict"][matching_vnet]:
                    tfdata["graphdict"][matching_vnet].append(subnet)

                # Update subnet metadata with VNet information
                if subnet in tfdata["meta_data"]:
                    tfdata["meta_data"][subnet]["vnet"] = helpers.get_no_module_name(
                        matching_vnet
                    )
            else:
                click.echo(
                    click.style(
                        f"WARNING: Could not find VNet for subnet {subnet} (ref: {vnet_ref})",
                        fg="yellow",
                    )
                )

        except (KeyError, TypeError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process subnet {subnet}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    return tfdata


def azure_handle_nsg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Network Security Group relationships.

    Processes NSG associations with subnets and NICs, reverses connections,
    and handles security rule processing. NSGs should wrap resources rather
    than be children of them.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with NSG relationships configured
    """
    # Find all NSG resources and associations
    nsgs = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_security_group"
    )
    nsg_subnet_associations = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_subnet_network_security_group_association"
    )
    nsg_nic_associations = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_network_interface_security_group_association"
    )

    if not nsgs:
        return tfdata

    # Process subnet-level NSG associations
    for association in nsg_subnet_associations:
        try:
            assoc_metadata = tfdata.get("original_metadata", {}).get(association, {})
            nsg_ref = assoc_metadata.get("network_security_group_id")
            subnet_ref = assoc_metadata.get("subnet_id")

            if not (nsg_ref and subnet_ref):
                click.echo(
                    click.style(
                        f"WARNING: NSG subnet association {association} missing required references",
                        fg="yellow",
                    )
                )
                continue

            # Find matching NSG and subnet
            matching_nsg = None
            matching_subnet = None

            for nsg in nsgs:
                if nsg_ref in nsg or helpers.get_no_module_name(nsg) in nsg_ref:
                    matching_nsg = nsg
                    break

            for subnet in helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "azurerm_subnet"
            ):
                if (
                    subnet_ref in subnet
                    or helpers.get_no_module_name(subnet) in subnet_ref
                ):
                    matching_subnet = subnet
                    break

            # Reverse the connection: NSG should contain subnet, not the other way around
            if matching_nsg and matching_subnet:
                # Remove subnet -> NSG connection if it exists
                if matching_nsg in tfdata["graphdict"].get(matching_subnet, []):
                    tfdata["graphdict"][matching_subnet].remove(matching_nsg)

                # Add NSG -> subnet connection
                if matching_subnet not in tfdata["graphdict"][matching_nsg]:
                    tfdata["graphdict"][matching_nsg].append(matching_subnet)

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process NSG subnet association {association}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    # Process NIC-level NSG associations
    for association in nsg_nic_associations:
        try:
            assoc_metadata = tfdata.get("original_metadata", {}).get(association, {})
            nsg_ref = assoc_metadata.get("network_security_group_id")
            nic_ref = assoc_metadata.get("network_interface_id")

            if not (nsg_ref and nic_ref):
                continue

            # Find matching NSG and NIC
            matching_nsg = None
            matching_nic = None

            for nsg in nsgs:
                if nsg_ref in nsg or helpers.get_no_module_name(nsg) in nsg_ref:
                    matching_nsg = nsg
                    break

            for nic in helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "azurerm_network_interface"
            ):
                if nic_ref in nic or helpers.get_no_module_name(nic) in nic_ref:
                    matching_nic = nic
                    break

            # Reverse the connection: NSG should contain NIC
            if matching_nsg and matching_nic:
                if matching_nsg in tfdata["graphdict"].get(matching_nic, []):
                    tfdata["graphdict"][matching_nic].remove(matching_nsg)

                if matching_nic not in tfdata["graphdict"][matching_nsg]:
                    tfdata["graphdict"][matching_nsg].append(matching_nic)

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process NSG NIC association {association}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    return tfdata


def azure_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Load Balancer type variants and connections.

    Processes load balancer SKUs (Basic, Standard) and their backend pools,
    health probes, and load balancing rules.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with LB variants configured
    """
    # Find all Azure load balancers
    lbs = sorted(helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_lb"))

    if not lbs:
        return tfdata

    # Process each load balancer
    for lb in lbs:
        try:
            lb_metadata = tfdata.get("meta_data", {}).get(lb, {})
            lb_original_metadata = tfdata.get("original_metadata", {}).get(lb, {})

            # Detect SKU type (Basic, Standard, Gateway)
            sku = lb_original_metadata.get("sku", "Basic")
            if isinstance(sku, dict):
                sku = sku.get("name", "Basic")

            # Create SKU-specific node name
            lb_base_name = helpers.get_no_module_name(lb)
            renamed_node = f"azurerm_lb_{sku.lower()}.lb"

            # Initialize renamed node metadata if needed
            if renamed_node not in tfdata["meta_data"]:
                tfdata["meta_data"][renamed_node] = ensure_metadata(
                    resource_id=renamed_node,
                    resource_type=f"azurerm_lb_{sku.lower()}",
                    provider="azure",
                    count=str(lb_metadata.get("count", "1")),
                )
                # Copy additional metadata
                for key, value in lb_metadata.items():
                    if key not in tfdata["meta_data"][renamed_node]:
                        tfdata["meta_data"][renamed_node][key] = value

            # Initialize renamed node in graph if needed
            if renamed_node not in tfdata["graphdict"]:
                tfdata["graphdict"][renamed_node] = []

            # Move connections from original LB to renamed node
            for connection in sorted(list(tfdata["graphdict"].get(lb, []))):
                if connection not in tfdata["graphdict"][renamed_node]:
                    tfdata["graphdict"][renamed_node].append(connection)
                    if connection in tfdata["graphdict"][lb]:
                        tfdata["graphdict"][lb].remove(connection)

            # Update parent references to point to renamed node
            parents = sorted(helpers.list_of_parents(tfdata["graphdict"], lb))
            for parent in parents:
                if renamed_node not in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].append(renamed_node)
                if lb in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].remove(lb)

            # Link original LB to renamed node
            if renamed_node not in tfdata["graphdict"][lb]:
                tfdata["graphdict"][lb].append(renamed_node)

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process Azure LB {lb}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    # Process backend pools
    backend_pools = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_lb_backend_address_pool"
    )

    for pool in backend_pools:
        try:
            pool_metadata = tfdata.get("original_metadata", {}).get(pool, {})
            lb_ref = pool_metadata.get("loadbalancer_id")

            if not lb_ref:
                continue

            # Find matching load balancer
            for lb in lbs:
                if lb_ref in lb or helpers.get_no_module_name(lb) in lb_ref:
                    # Link pool to LB
                    if pool not in tfdata["graphdict"].get(lb, []):
                        tfdata["graphdict"][lb].append(pool)
                    break

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"WARNING: Failed to process backend pool {pool}: {str(e)}",
                    fg="yellow",
                )
            )
            continue

    return tfdata


def azure_handle_app_gateway(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure Application Gateway configurations.

    Processes Application Gateway SKUs, backend pools, HTTP settings,
    listeners, and routing rules.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Application Gateway configured
    """
    # Find all Application Gateways
    app_gateways = sorted(
        helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_application_gateway"
        )
    )

    if not app_gateways:
        return tfdata

    # Process each Application Gateway
    for app_gw in app_gateways:
        try:
            app_gw_metadata = tfdata.get("meta_data", {}).get(app_gw, {})
            app_gw_original_metadata = tfdata.get("original_metadata", {}).get(
                app_gw, {}
            )

            # Detect SKU tier (Standard_v2, WAF_v2, etc.)
            sku = app_gw_original_metadata.get("sku", {})
            if isinstance(sku, dict):
                tier = sku.get("tier", "Standard_v2")
            else:
                tier = "Standard_v2"

            # Normalize tier name
            tier_normalized = tier.lower().replace("_", "")

            # Determine if WAF is enabled
            is_waf = "waf" in tier.lower()

            # Create SKU/tier-specific node name
            app_gw_base_name = helpers.get_no_module_name(app_gw)
            if is_waf:
                renamed_node = f"azurerm_application_gateway_waf.appgw"
            else:
                renamed_node = f"azurerm_application_gateway_{tier_normalized}.appgw"

            # Initialize renamed node metadata if needed
            if renamed_node not in tfdata["meta_data"]:
                tfdata["meta_data"][renamed_node] = ensure_metadata(
                    resource_id=renamed_node,
                    resource_type=f"azurerm_application_gateway_{tier_normalized}",
                    provider="azure",
                    count=str(app_gw_metadata.get("count", "1")),
                )
                # Copy additional metadata
                for key, value in app_gw_metadata.items():
                    if key not in tfdata["meta_data"][renamed_node]:
                        tfdata["meta_data"][renamed_node][key] = value

                # Add tier information
                tfdata["meta_data"][renamed_node]["tier"] = tier
                tfdata["meta_data"][renamed_node]["waf_enabled"] = is_waf

            # Initialize renamed node in graph if needed
            if renamed_node not in tfdata["graphdict"]:
                tfdata["graphdict"][renamed_node] = []

            # Move connections from original app gateway to renamed node
            for connection in sorted(list(tfdata["graphdict"].get(app_gw, []))):
                if connection not in tfdata["graphdict"][renamed_node]:
                    tfdata["graphdict"][renamed_node].append(connection)
                    if connection in tfdata["graphdict"][app_gw]:
                        tfdata["graphdict"][app_gw].remove(connection)

            # Update parent references to point to renamed node
            parents = sorted(helpers.list_of_parents(tfdata["graphdict"], app_gw))
            for parent in parents:
                if renamed_node not in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].append(renamed_node)
                if app_gw in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].remove(app_gw)

            # Link original app gateway to renamed node
            if renamed_node not in tfdata["graphdict"][app_gw]:
                tfdata["graphdict"][app_gw].append(renamed_node)

            # Process WAF configuration if WAF SKU
            if is_waf:
                waf_config = app_gw_original_metadata.get("waf_configuration", {})
                if waf_config and renamed_node in tfdata["meta_data"]:
                    tfdata["meta_data"][renamed_node]["waf_mode"] = waf_config.get(
                        "firewall_mode", "Detection"
                    )
                    tfdata["meta_data"][renamed_node]["waf_enabled"] = waf_config.get(
                        "enabled", True
                    )

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process Application Gateway {app_gw}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    # Process backend address pools
    backend_pools = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "azurerm_application_gateway_backend_address_pool"
    )

    for pool in backend_pools:
        try:
            pool_metadata = tfdata.get("original_metadata", {}).get(pool, {})
            app_gw_name = pool_metadata.get("application_gateway_name")

            if not app_gw_name:
                continue

            # Find matching application gateway
            for app_gw in app_gateways:
                if (
                    app_gw_name in app_gw
                    or helpers.get_no_module_name(app_gw) in app_gw_name
                ):
                    # Link pool to app gateway
                    if pool not in tfdata["graphdict"].get(app_gw, []):
                        tfdata["graphdict"][app_gw].append(pool)
                    break

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"WARNING: Failed to process backend pool {pool}: {str(e)}",
                    fg="yellow",
                )
            )
            continue

    return tfdata
