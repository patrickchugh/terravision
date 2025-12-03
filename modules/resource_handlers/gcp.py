"""GCP resource-specific handlers for Terraform graph processing.

Handles special cases for GCP resources including VPC networks, subnets,
firewall rules, load balancers, and Cloud DNS.
"""

from typing import Dict, List, Any
import modules.cloud_config as cloud_config
import modules.helpers as helpers
from modules.exceptions import MissingResourceError
from modules.utils.graph_utils import ensure_metadata
import copy
import click


def gcp_handle_network_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP VPC Network and subnet relationships.

    Processes VPC network/subnet structures. Note that GCP subnets are regional
    resources that can span multiple availability zones, unlike AWS.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VPC network/subnet relationships configured

    Raises:
        MissingResourceError: When subnets exist but no VPC networks are found
    """
    # Find all VPC networks and subnets
    networks = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "google_compute_network"
    )
    subnets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "google_compute_subnetwork"
    )

    # Validate prerequisites: subnets require VPC networks
    if subnets and not networks:
        raise MissingResourceError(
            "google_compute_network",
            context={
                "handler": "gcp_handle_network_subnets",
                "subnet_count": len(subnets),
                "message": "Found subnets but no VPC networks to attach them to",
            },
        )

    # Process each subnet to ensure proper VPC network relationships
    for subnet in subnets:
        try:
            # Get subnet's network attribute from metadata
            subnet_metadata = tfdata.get("original_metadata", {}).get(subnet, {})
            network_ref = subnet_metadata.get("network")
            region = subnet_metadata.get("region")

            if not network_ref:
                click.echo(
                    click.style(
                        f"WARNING: Subnet {subnet} missing network reference",
                        fg="yellow",
                    )
                )
                continue

            # Find matching VPC network by reference
            matching_network = None
            for network in networks:
                if (
                    network_ref in network
                    or helpers.get_no_module_name(network) in network_ref
                ):
                    matching_network = network
                    break

            if matching_network:
                # Ensure subnet is connected to VPC network
                if subnet not in tfdata["graphdict"][matching_network]:
                    tfdata["graphdict"][matching_network].append(subnet)

                # Update subnet metadata with network and region information
                if subnet in tfdata["meta_data"]:
                    tfdata["meta_data"][subnet]["network"] = helpers.get_no_module_name(
                        matching_network
                    )
                    if region:
                        tfdata["meta_data"][subnet]["region"] = region

                # Handle subnet mode (auto-mode vs custom-mode)
                network_original_metadata = tfdata.get("original_metadata", {}).get(
                    matching_network, {}
                )
                auto_create = network_original_metadata.get(
                    "auto_create_subnetworks", False
                )
                if auto_create and subnet in tfdata["meta_data"]:
                    tfdata["meta_data"][subnet]["mode"] = "auto"
                elif subnet in tfdata["meta_data"]:
                    tfdata["meta_data"][subnet]["mode"] = "custom"

            else:
                click.echo(
                    click.style(
                        f"WARNING: Could not find VPC network for subnet {subnet} (ref: {network_ref})",
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


def gcp_handle_firewall(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Firewall rule relationships.

    Processes firewall rules associated with VPC networks, including
    ingress/egress rules, target tags, and service accounts. GCP firewall
    rules should wrap the resources they protect, similar to NSGs.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with firewall relationships configured
    """
    # Find all firewall rules
    firewalls = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "google_compute_firewall"
    )

    if not firewalls:
        return tfdata

    # Process each firewall rule
    for firewall in firewalls:
        try:
            firewall_metadata = tfdata.get("original_metadata", {}).get(firewall, {})
            network_ref = firewall_metadata.get("network")
            direction = firewall_metadata.get("direction", "INGRESS")
            target_tags = firewall_metadata.get("target_tags", [])

            if not network_ref:
                click.echo(
                    click.style(
                        f"WARNING: Firewall {firewall} missing network reference",
                        fg="yellow",
                    )
                )
                continue

            # Find matching VPC network
            matching_network = None
            networks = helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "google_compute_network"
            )

            for network in networks:
                if (
                    network_ref in network
                    or helpers.get_no_module_name(network) in network_ref
                ):
                    matching_network = network
                    break

            if not matching_network:
                click.echo(
                    click.style(
                        f"WARNING: Could not find VPC network for firewall {firewall} (ref: {network_ref})",
                        fg="yellow",
                    )
                )
                continue

            # Update firewall metadata with direction and network info
            if firewall in tfdata["meta_data"]:
                tfdata["meta_data"][firewall]["direction"] = direction
                tfdata["meta_data"][firewall]["network"] = helpers.get_no_module_name(
                    matching_network
                )
                if target_tags:
                    tfdata["meta_data"][firewall]["target_tags"] = target_tags

            # Find compute instances with matching tags
            instances = helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "google_compute_instance"
            )

            for instance in instances:
                instance_metadata = tfdata.get("original_metadata", {}).get(
                    instance, {}
                )
                instance_tags = instance_metadata.get("tags", [])
                instance_network = instance_metadata.get("network")

                # Check if instance is in the same network and has matching tags
                network_match = instance_network and (
                    network_ref in instance_network
                    or matching_network in instance_network
                )

                tag_match = (
                    not target_tags  # Apply to all if no target tags
                    or any(tag in instance_tags for tag in target_tags)
                )

                if network_match and tag_match:
                    # Firewall should wrap the instance, not be a child
                    if instance not in tfdata["graphdict"][firewall]:
                        tfdata["graphdict"][firewall].append(instance)

                    # Remove reverse connection if it exists
                    if firewall in tfdata["graphdict"].get(instance, []):
                        tfdata["graphdict"][instance].remove(firewall)

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process firewall {firewall}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    return tfdata


def gcp_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Load Balancer configurations.

    Processes various GCP load balancer types including HTTP(S), TCP/SSL,
    internal, and network load balancers through backend services.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with LB configurations
    """
    # Find backend services (core LB component)
    backend_services = sorted(
        helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "google_compute_backend_service"
        )
    )

    if not backend_services:
        return tfdata

    # Process each backend service
    for backend in backend_services:
        try:
            backend_metadata = tfdata.get("original_metadata", {}).get(backend, {})

            # Determine LB type from backend service properties
            load_balancing_scheme = backend_metadata.get(
                "load_balancing_scheme", "EXTERNAL"
            )
            protocol = backend_metadata.get("protocol", "HTTP")

            # Classify LB type
            if load_balancing_scheme == "INTERNAL":
                lb_type = "google_compute_internal_lb"
            elif protocol in ["HTTP", "HTTPS"]:
                lb_type = "google_compute_http_lb"
            elif protocol in ["SSL", "TCP"]:
                lb_type = "google_compute_tcp_lb"
            else:
                lb_type = "google_compute_network_lb"

            # Create LB-specific node name
            renamed_node = f"{lb_type}.lb"

            # Initialize renamed node metadata if needed
            if renamed_node not in tfdata["meta_data"]:
                backend_count = (
                    tfdata.get("meta_data", {}).get(backend, {}).get("count", "1")
                )
                tfdata["meta_data"][renamed_node] = ensure_metadata(
                    resource_id=renamed_node,
                    resource_type=lb_type,
                    provider="gcp",
                    count=str(backend_count),
                )
                # Copy additional metadata from backend service
                for key, value in tfdata.get("meta_data", {}).get(backend, {}).items():
                    if key not in tfdata["meta_data"][renamed_node]:
                        tfdata["meta_data"][renamed_node][key] = value

            # Initialize renamed node in graph if needed
            if renamed_node not in tfdata["graphdict"]:
                tfdata["graphdict"][renamed_node] = []

            # Move connections from backend service to LB node
            for connection in sorted(list(tfdata["graphdict"].get(backend, []))):
                if connection not in tfdata["graphdict"][renamed_node]:
                    tfdata["graphdict"][renamed_node].append(connection)
                    if connection in tfdata["graphdict"][backend]:
                        tfdata["graphdict"][backend].remove(connection)

            # Update parent references to point to renamed node
            parents = sorted(helpers.list_of_parents(tfdata["graphdict"], backend))
            for parent in parents:
                if renamed_node not in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].append(renamed_node)
                if backend in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].remove(backend)

            # Link backend service to renamed LB node
            if renamed_node not in tfdata["graphdict"][backend]:
                tfdata["graphdict"][backend].append(renamed_node)

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process GCP backend service {backend}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    # Process forwarding rules (external IP / entry point)
    forwarding_rules = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "google_compute_forwarding_rule"
    )

    for rule in forwarding_rules:
        try:
            rule_metadata = tfdata.get("original_metadata", {}).get(rule, {})
            backend_service_ref = rule_metadata.get(
                "backend_service"
            ) or rule_metadata.get("target")

            if not backend_service_ref:
                continue

            # Find matching backend service
            for backend in backend_services:
                if (
                    backend_service_ref in backend
                    or helpers.get_no_module_name(backend) in backend_service_ref
                ):
                    # Link forwarding rule to backend service
                    if rule not in tfdata["graphdict"].get(backend, []):
                        tfdata["graphdict"][backend].append(rule)
                    break

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"WARNING: Failed to process forwarding rule {rule}: {str(e)}",
                    fg="yellow",
                )
            )
            continue

    return tfdata


def gcp_handle_cloud_dns(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Cloud DNS managed zones and records.

    Processes Cloud DNS managed zones, record sets, and DNSSEC configurations.
    Groups DNS records under their parent managed zones.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Cloud DNS configured
    """
    # Find all DNS managed zones and record sets
    dns_zones = sorted(
        helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "google_dns_managed_zone"
        )
    )
    dns_records = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "google_dns_record_set"
    )

    if not dns_zones:
        return tfdata

    # Process each managed zone
    for zone in dns_zones:
        try:
            zone_metadata = tfdata.get("original_metadata", {}).get(zone, {})

            # Detect zone type (public, private, forwarding, peering)
            visibility = zone_metadata.get("visibility", "public")

            # Check for special zone types
            peering_config = zone_metadata.get("peering_config")
            forwarding_config = zone_metadata.get("forwarding_config")

            zone_type = "public"
            if peering_config:
                zone_type = "peering"
            elif forwarding_config:
                zone_type = "forwarding"
            elif visibility == "private":
                zone_type = "private"

            # Update zone metadata with type information
            if zone in tfdata["meta_data"]:
                tfdata["meta_data"][zone]["zone_type"] = zone_type
                tfdata["meta_data"][zone]["visibility"] = visibility

                # Add DNSSEC status if configured
                dnssec_config = zone_metadata.get("dnssec_config", {})
                if dnssec_config:
                    dnssec_state = dnssec_config.get("state", "off")
                    tfdata["meta_data"][zone]["dnssec_enabled"] = dnssec_state == "on"

            # Link private zones to VPC networks
            if zone_type == "private":
                private_visibility_config = zone_metadata.get(
                    "private_visibility_config", {}
                )
                networks = private_visibility_config.get("networks", [])

                for network_config in networks:
                    if isinstance(network_config, dict):
                        network_url = network_config.get("network_url")
                        if network_url:
                            # Find matching VPC network
                            vpc_networks = helpers.list_of_dictkeys_containing(
                                tfdata["graphdict"], "google_compute_network"
                            )
                            for vpc in vpc_networks:
                                if (
                                    network_url in vpc
                                    or helpers.get_no_module_name(vpc) in network_url
                                ):
                                    # Link zone to VPC network
                                    if zone not in tfdata["graphdict"].get(vpc, []):
                                        tfdata["graphdict"][vpc].append(zone)
                                    break

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process DNS zone {zone}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    # Process DNS record sets and group under zones
    for record in dns_records:
        try:
            record_metadata = tfdata.get("original_metadata", {}).get(record, {})
            managed_zone = record_metadata.get("managed_zone")
            record_type = record_metadata.get("type", "A")

            if not managed_zone:
                click.echo(
                    click.style(
                        f"WARNING: DNS record {record} missing managed_zone reference",
                        fg="yellow",
                    )
                )
                continue

            # Find matching DNS zone
            matching_zone = None
            for zone in dns_zones:
                if (
                    managed_zone in zone
                    or helpers.get_no_module_name(zone) in managed_zone
                ):
                    matching_zone = zone
                    break

            if matching_zone:
                # Group record under zone
                if record not in tfdata["graphdict"][matching_zone]:
                    tfdata["graphdict"][matching_zone].append(record)

                # Update record metadata
                if record in tfdata["meta_data"]:
                    tfdata["meta_data"][record]["record_type"] = record_type
                    tfdata["meta_data"][record]["managed_zone"] = (
                        helpers.get_no_module_name(matching_zone)
                    )
            else:
                click.echo(
                    click.style(
                        f"WARNING: Could not find DNS zone for record {record} (ref: {managed_zone})",
                        fg="yellow",
                    )
                )

        except (KeyError, TypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"ERROR: Failed to process DNS record {record}: {str(e)}",
                    fg="red",
                    bold=True,
                )
            )
            continue

    return tfdata
