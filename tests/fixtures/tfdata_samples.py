"""Fixture factories for generating tfdata test samples.

This module provides fixture factory functions for creating tfdata dictionaries
with varying complexity levels for unit and integration testing.

tfdata structure:
    {
        "graphdict": dict[str, list[str]],  # Adjacency list
        "metadata": dict[str, dict],         # Resource metadata
        "all_resource": list[dict],          # Raw resource data
        "annotations": dict                  # User annotations
    }
"""

from typing import Any, Dict, List


def minimal_tfdata() -> Dict[str, Any]:
    """Create minimal valid tfdata structure for basic tests.

    Returns:
        dict: tfdata with empty graphdict, metadata, and required keys
    """
    return {
        "graphdict": {},
        "meta_data": {},
        "original_metadata": {},
        "node_list": [],
        "hidden": [],
        "all_resource": [],
    }


def vpc_tfdata(
    vpc_count: int = 1,
    subnet_count: int = 2,
    endpoint_count: int = 0,
    nat_gateway_count: int = 0,
) -> Dict[str, Any]:
    """Create tfdata with AWS VPC resources.

    Args:
        vpc_count: Number of VPCs to create
        subnet_count: Number of subnets per VPC
        endpoint_count: Number of VPC endpoints per VPC
        nat_gateway_count: Number of NAT gateways per VPC

    Returns:
        dict: tfdata with AWS VPC, subnets, endpoints, and NAT gateways
    """
    graphdict = {}
    meta_data = {}
    original_metadata = {}
    node_list = []
    all_resource = []

    for vpc_idx in range(vpc_count):
        vpc_id = f"aws_vpc.vpc{vpc_idx}"
        node_list.append(vpc_id)
        graphdict[vpc_id] = []
        meta_data[vpc_id] = {
            "name": f"vpc{vpc_idx}",
            "type": "aws_vpc",
            "provider": "aws",
            "cidr_block": f"10.{vpc_idx}.0.0/16",
        }
        original_metadata[vpc_id] = meta_data[vpc_id].copy()
        all_resource.append(
            {
                "address": vpc_id,
                "type": "aws_vpc",
                "name": f"vpc{vpc_idx}",
                "values": {"cidr_block": f"10.{vpc_idx}.0.0/16"},
            }
        )

        # Add subnets for this VPC
        for subnet_idx in range(subnet_count):
            subnet_id = f"aws_subnet.vpc{vpc_idx}_subnet{subnet_idx}"
            node_list.append(subnet_id)
            graphdict[subnet_id] = [vpc_id]
            meta_data[subnet_id] = {
                "name": f"vpc{vpc_idx}_subnet{subnet_idx}",
                "type": "aws_subnet",
                "provider": "aws",
                "vpc_id": vpc_id,
                "cidr_block": f"10.{vpc_idx}.{subnet_idx}.0/24",
            }
            original_metadata[subnet_id] = meta_data[subnet_id].copy()
            all_resource.append(
                {
                    "address": subnet_id,
                    "type": "aws_subnet",
                    "name": f"vpc{vpc_idx}_subnet{subnet_idx}",
                    "values": {
                        "vpc_id": vpc_id,
                        "cidr_block": f"10.{vpc_idx}.{subnet_idx}.0/24",
                    },
                }
            )

        # Add VPC endpoints
        for ep_idx in range(endpoint_count):
            endpoint_id = f"aws_vpc_endpoint.vpc{vpc_idx}_endpoint{ep_idx}"
            node_list.append(endpoint_id)
            graphdict[endpoint_id] = []
            meta_data[endpoint_id] = {
                "name": f"vpc{vpc_idx}_endpoint{ep_idx}",
                "type": "aws_vpc_endpoint",
                "provider": "aws",
                "vpc_id": vpc_id,
                "service_name": f"com.amazonaws.vpce.{vpc_idx}.s3",
            }
            original_metadata[endpoint_id] = meta_data[endpoint_id].copy()
            all_resource.append(
                {
                    "address": endpoint_id,
                    "type": "aws_vpc_endpoint",
                    "name": f"vpc{vpc_idx}_endpoint{ep_idx}",
                    "values": {
                        "vpc_id": vpc_id,
                        "service_name": f"com.amazonaws.vpce.{vpc_idx}.s3",
                    },
                }
            )

        # Add NAT gateways
        for nat_idx in range(nat_gateway_count):
            nat_id = f"aws_nat_gateway.vpc{vpc_idx}_nat{nat_idx}"
            node_list.append(nat_id)
            graphdict[nat_id] = []
            # NAT gateway requires subnet
            if subnet_count > 0:
                subnet_ref = f"aws_subnet.vpc{vpc_idx}_subnet0"
                graphdict[nat_id].append(subnet_ref)
            meta_data[nat_id] = {
                "name": f"vpc{vpc_idx}_nat{nat_idx}",
                "type": "aws_nat_gateway",
                "provider": "aws",
                "subnet_id": f"aws_subnet.vpc{vpc_idx}_subnet0"
                if subnet_count > 0
                else None,
            }
            original_metadata[nat_id] = meta_data[nat_id].copy()
            all_resource.append(
                {
                    "address": nat_id,
                    "type": "aws_nat_gateway",
                    "name": f"vpc{vpc_idx}_nat{nat_idx}",
                    "values": {
                        "subnet_id": f"aws_subnet.vpc{vpc_idx}_subnet0"
                        if subnet_count > 0
                        else None
                    },
                }
            )

    return {
        "graphdict": graphdict,
        "meta_data": meta_data,
        "original_metadata": original_metadata,
        "node_list": node_list,
        "hidden": [],
        "all_resource": all_resource,
    }


def vnet_tfdata(
    vnet_count: int = 1, subnet_count: int = 2, nsg_count: int = 0, lb_count: int = 0
) -> Dict[str, Any]:
    """Create tfdata with Azure VNet resources.

    Args:
        vnet_count: Number of VNets to create
        subnet_count: Number of subnets per VNet
        nsg_count: Number of network security groups
        lb_count: Number of load balancers

    Returns:
        dict: tfdata with Azure VNet, subnets, NSGs, and load balancers
    """
    graphdict = {}
    meta_data = {}
    original_metadata = {}
    node_list = []
    all_resource = []

    for vnet_idx in range(vnet_count):
        vnet_id = f"azurerm_virtual_network.vnet{vnet_idx}"
        node_list.append(vnet_id)
        graphdict[vnet_id] = []
        meta_data[vnet_id] = {
            "name": f"vnet{vnet_idx}",
            "type": "azurerm_virtual_network",
            "provider": "azurerm",
            "address_space": [f"10.{vnet_idx}.0.0/16"],
        }
        original_metadata[vnet_id] = meta_data[vnet_id].copy()
        all_resource.append(
            {
                "address": vnet_id,
                "type": "azurerm_virtual_network",
                "name": f"vnet{vnet_idx}",
                "values": {"address_space": [f"10.{vnet_idx}.0.0/16"]},
            }
        )

        # Add subnets for this VNet
        for subnet_idx in range(subnet_count):
            subnet_id = f"azurerm_subnet.vnet{vnet_idx}_subnet{subnet_idx}"
            node_list.append(subnet_id)
            graphdict[subnet_id] = [vnet_id]
            meta_data[subnet_id] = {
                "name": f"vnet{vnet_idx}_subnet{subnet_idx}",
                "type": "azurerm_subnet",
                "provider": "azurerm",
                "virtual_network_name": f"vnet{vnet_idx}",
                "address_prefixes": [f"10.{vnet_idx}.{subnet_idx}.0/24"],
            }
            original_metadata[subnet_id] = meta_data[subnet_idx].copy()
            all_resource.append(
                {
                    "address": subnet_id,
                    "type": "azurerm_subnet",
                    "name": f"vnet{vnet_idx}_subnet{subnet_idx}",
                    "values": {
                        "virtual_network_name": f"vnet{vnet_idx}",
                        "address_prefixes": [f"10.{vnet_idx}.{subnet_idx}.0/24"],
                    },
                }
            )

    # Add network security groups
    for nsg_idx in range(nsg_count):
        nsg_id = f"azurerm_network_security_group.nsg{nsg_idx}"
        node_list.append(nsg_id)
        graphdict[nsg_id] = []
        meta_data[nsg_id] = {
            "name": f"nsg{nsg_idx}",
            "type": "azurerm_network_security_group",
            "provider": "azurerm",
        }
        original_metadata[nsg_id] = meta_data[nsg_id].copy()
        all_resource.append(
            {
                "address": nsg_id,
                "type": "azurerm_network_security_group",
                "name": f"nsg{nsg_idx}",
                "values": {},
            }
        )

    # Add load balancers
    for lb_idx in range(lb_count):
        lb_id = f"azurerm_lb.lb{lb_idx}"
        node_list.append(lb_id)
        graphdict[lb_id] = []
        sku = "Basic" if lb_idx % 2 == 0 else "Standard"
        meta_data[lb_id] = {
            "name": f"lb{lb_idx}",
            "type": "azurerm_lb",
            "provider": "azurerm",
            "sku": sku,
        }
        original_metadata[lb_id] = meta_data[lb_id].copy()
        all_resource.append(
            {
                "address": lb_id,
                "type": "azurerm_lb",
                "name": f"lb{lb_idx}",
                "values": {"sku": sku},
            }
        )

    return {
        "graphdict": graphdict,
        "meta_data": meta_data,
        "original_metadata": original_metadata,
        "node_list": node_list,
        "hidden": [],
        "all_resource": all_resource,
    }


def gcp_network_tfdata(
    network_count: int = 1,
    subnet_count: int = 2,
    firewall_count: int = 0,
    lb_count: int = 0,
) -> Dict[str, Any]:
    """Create tfdata with GCP VPC network resources.

    Args:
        network_count: Number of VPC networks to create
        subnet_count: Number of subnets per network
        firewall_count: Number of firewall rules
        lb_count: Number of load balancers

    Returns:
        dict: tfdata with GCP networks, subnets, firewalls, and load balancers
    """
    graphdict = {}
    meta_data = {}
    original_metadata = {}
    node_list = []
    all_resource = []

    for net_idx in range(network_count):
        net_id = f"google_compute_network.network{net_idx}"
        node_list.append(net_id)
        graphdict[net_id] = []
        meta_data[net_id] = {
            "name": f"network{net_idx}",
            "type": "google_compute_network",
            "provider": "google",
            "auto_create_subnetworks": False,
        }
        original_metadata[net_id] = meta_data[net_id].copy()
        all_resource.append(
            {
                "address": net_id,
                "type": "google_compute_network",
                "name": f"network{net_idx}",
                "values": {"auto_create_subnetworks": False},
            }
        )

        # Add subnets for this network
        for subnet_idx in range(subnet_count):
            subnet_id = f"google_compute_subnetwork.net{net_idx}_subnet{subnet_idx}"
            node_list.append(subnet_id)
            graphdict[subnet_id] = [net_id]
            meta_data[subnet_id] = {
                "name": f"net{net_idx}_subnet{subnet_idx}",
                "type": "google_compute_subnetwork",
                "provider": "google",
                "network": net_id,
                "ip_cidr_range": f"10.{net_idx}.{subnet_idx}.0/24",
            }
            original_metadata[subnet_id] = meta_data[subnet_idx].copy()
            all_resource.append(
                {
                    "address": subnet_id,
                    "type": "google_compute_subnetwork",
                    "name": f"net{net_idx}_subnet{subnet_idx}",
                    "values": {
                        "network": net_id,
                        "ip_cidr_range": f"10.{net_idx}.{subnet_idx}.0/24",
                    },
                }
            )

    # Add firewall rules
    for fw_idx in range(firewall_count):
        fw_id = f"google_compute_firewall.firewall{fw_idx}"
        node_list.append(fw_id)
        graphdict[fw_id] = []
        direction = "INGRESS" if fw_idx % 2 == 0 else "EGRESS"
        meta_data[fw_id] = {
            "name": f"firewall{fw_idx}",
            "type": "google_compute_firewall",
            "provider": "google",
            "direction": direction,
            "network": f"google_compute_network.network0"
            if network_count > 0
            else None,
        }
        original_metadata[fw_id] = meta_data[fw_id].copy()
        all_resource.append(
            {
                "address": fw_id,
                "type": "google_compute_firewall",
                "name": f"firewall{fw_idx}",
                "values": {
                    "direction": direction,
                    "network": f"google_compute_network.network0"
                    if network_count > 0
                    else None,
                },
            }
        )

    # Add load balancers
    for lb_idx in range(lb_count):
        lb_id = f"google_compute_forwarding_rule.lb{lb_idx}"
        node_list.append(lb_id)
        graphdict[lb_id] = []
        # Alternate between HTTP, TCP, and internal LBs
        if lb_idx % 3 == 0:
            lb_type = "HTTP(S)"
            scheme = "EXTERNAL"
        elif lb_idx % 3 == 1:
            lb_type = "TCP"
            scheme = "EXTERNAL"
        else:
            lb_type = "Internal"
            scheme = "INTERNAL"

        meta_data[lb_id] = {
            "name": f"lb{lb_idx}",
            "type": "google_compute_forwarding_rule",
            "provider": "google",
            "load_balancing_scheme": scheme,
            "ip_protocol": "TCP" if lb_type == "TCP" else "HTTP",
        }
        original_metadata[lb_id] = meta_data[lb_id].copy()
        all_resource.append(
            {
                "address": lb_id,
                "type": "google_compute_forwarding_rule",
                "name": f"lb{lb_idx}",
                "values": {
                    "load_balancing_scheme": scheme,
                    "ip_protocol": "TCP" if lb_type == "TCP" else "HTTP",
                },
            }
        )

    return {
        "graphdict": graphdict,
        "meta_data": meta_data,
        "original_metadata": original_metadata,
        "node_list": node_list,
        "hidden": [],
        "all_resource": all_resource,
    }


def multicloud_tfdata() -> Dict[str, Any]:
    """Create tfdata with mixed AWS, Azure, and GCP resources.

    Returns:
        dict: tfdata combining resources from all three providers
    """
    aws_data = vpc_tfdata(vpc_count=1, subnet_count=1)
    azure_data = vnet_tfdata(vnet_count=1, subnet_count=1)
    gcp_data = gcp_network_tfdata(network_count=1, subnet_count=1)

    # Merge all data
    graphdict = {}
    graphdict.update(aws_data["graphdict"])
    graphdict.update(azure_data["graphdict"])
    graphdict.update(gcp_data["graphdict"])

    meta_data = {}
    meta_data.update(aws_data["meta_data"])
    meta_data.update(azure_data["meta_data"])
    meta_data.update(gcp_data["meta_data"])

    original_metadata = {}
    original_metadata.update(aws_data["original_metadata"])
    original_metadata.update(azure_data["original_metadata"])
    original_metadata.update(gcp_data["original_metadata"])

    node_list = aws_data["node_list"] + azure_data["node_list"] + gcp_data["node_list"]

    all_resource = (
        aws_data["all_resource"] + azure_data["all_resource"] + gcp_data["all_resource"]
    )

    return {
        "graphdict": graphdict,
        "meta_data": meta_data,
        "original_metadata": original_metadata,
        "node_list": node_list,
        "hidden": [],
        "all_resource": all_resource,
    }
