"""
GCP Networking category - VPC, Load Balancing, Cloud DNS, Cloud CDN.

Icon Resolution:
- All networking resources use category icon (2-color): resource_images/gcp/category/networking.png
"""

from . import _GCP


class _Networking(_GCP):
    _type = "networking"
    _icon_dir = "resource_images/gcp/category"
    _icon = "networking.png"


class VPC(_Networking):
    """Virtual Private Cloud network."""

    pass


class Subnet(_Networking):
    """VPC subnet."""

    pass


class Firewall(_Networking):
    """Firewall rules."""

    pass


class CloudNAT(_Networking):
    """Cloud NAT for outbound connectivity."""

    pass


class CloudRouter(_Networking):
    """Cloud Router for dynamic routing."""

    pass


class CloudVPN(_Networking):
    """Cloud VPN for site-to-site connectivity."""

    pass


class CloudInterconnect(_Networking):
    """Cloud Interconnect for dedicated connections."""

    pass


class LoadBalancing(_Networking):
    """Cloud Load Balancing."""

    pass


class CloudDNS(_Networking):
    """Cloud DNS managed DNS."""

    pass


class CloudCDN(_Networking):
    """Cloud CDN content delivery."""

    pass


class CloudArmor(_Networking):
    """Cloud Armor WAF and DDoS protection."""

    pass


class TrafficDirector(_Networking):
    """Traffic Director service mesh."""

    pass


class ServiceDirectory(_Networking):
    """Service Directory for service discovery."""

    pass


class PrivateServiceConnect(_Networking):
    """Private Service Connect for private endpoints."""

    pass


class NetworkConnectivityCenter(_Networking):
    """Network Connectivity Center hub."""

    pass


# Aliases
Network = VPC
Subnetwork = Subnet

# Terraform resource aliases
# Note: google_compute_network, google_compute_subnetwork, google_compute_firewall
# are defined in groups.py as Cluster classes for zone rendering
google_compute_router = CloudRouter
google_compute_router_nat = CloudNAT
google_compute_vpn_gateway = CloudVPN
google_compute_vpn_tunnel = CloudVPN
google_compute_ha_vpn_gateway = CloudVPN
google_compute_external_vpn_gateway = CloudVPN
google_compute_interconnect_attachment = CloudInterconnect
google_compute_global_forwarding_rule = LoadBalancing
google_compute_forwarding_rule = LoadBalancing
google_compute_backend_service = LoadBalancing
google_compute_backend_bucket = LoadBalancing
google_compute_url_map = LoadBalancing
google_compute_target_http_proxy = LoadBalancing
google_compute_target_https_proxy = LoadBalancing
google_compute_target_pool = LoadBalancing
google_compute_health_check = LoadBalancing
google_compute_region_health_check = LoadBalancing
google_dns_managed_zone = CloudDNS
google_dns_record_set = CloudDNS
google_compute_security_policy = CloudArmor
google_service_directory_namespace = ServiceDirectory
google_service_directory_service = ServiceDirectory
google_compute_service_attachment = PrivateServiceConnect
google_network_connectivity_hub = NetworkConnectivityCenter
google_network_connectivity_spoke = NetworkConnectivityCenter
