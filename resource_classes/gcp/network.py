from . import _GCP


class _Network(_GCP):
    _type = "network"
    _icon_dir = "resources/gcp/network"


class Armor(_Network):
    _icon = "armor.png"


class CDN(_Network):
    _icon = "cdn.png"


class CloudIDS(_Network):
    _icon = "cloud-ids.png"


class DedicatedInterconnect(_Network):
    _icon = "dedicated-interconnect.png"


class DNS(_Network):
    _icon = "dns.png"


class ExternalIpAddresses(_Network):
    _icon = "external-ip-addresses.png"


class FirewallRules(_Network):
    _icon = "firewall-rules.png"


class LoadBalancing(_Network):
    _icon = "load-balancing.png"


class NAT(_Network):
    _icon = "nat.png"


class NetworkConnectivityCenter(_Network):
    _icon = "network-connectivity-center.png"


class NetworkIntelligenceCenter(_Network):
    _icon = "network-intelligence-center.png"


class NetworkSecurity(_Network):
    _icon = "network-security.png"


class NetworkTiers(_Network):
    _icon = "network-tiers.png"


class NetworkTopology(_Network):
    _icon = "network-topology.png"


class Network(_Network):
    _icon = "network.png"


class PartnerInterconnect(_Network):
    _icon = "partner-interconnect.png"


class PremiumNetworkTier(_Network):
    _icon = "premium-network-tier.png"


class PrivateServiceConnect(_Network):
    _icon = "private-service-connect.png"


class Router(_Network):
    _icon = "router.png"


class Routes(_Network):
    _icon = "routes.png"


class ServiceMesh(_Network):
    _icon = "service-mesh.png"


class StandardNetworkTier(_Network):
    _icon = "standard-network-tier.png"


class TrafficDirector(_Network):
    _icon = "traffic-director.png"


class VirtualPrivateCloud(_Network):
    _icon = "virtual-private-cloud.png"


class VPN(_Network):
    _icon = "vpn.png"


# Aliases

IDS = CloudIDS
PSC = PrivateServiceConnect
VPC = VirtualPrivateCloud

# Terraform aliases
google_compute_network = VirtualPrivateCloud
google_compute_subnetwork = VirtualPrivateCloud
google_compute_firewall = FirewallRules
google_compute_router = Router
google_compute_router_nat = NAT
google_compute_vpn_gateway = VPN
google_compute_vpn_tunnel = VPN
google_compute_address = ExternalIpAddresses
google_compute_global_address = ExternalIpAddresses
google_compute_forwarding_rule = LoadBalancing
google_compute_global_forwarding_rule = LoadBalancing
google_compute_backend_service = LoadBalancing
google_compute_url_map = LoadBalancing
google_compute_target_http_proxy = LoadBalancing
google_compute_target_https_proxy = LoadBalancing
google_dns_managed_zone = DNS
google_dns_record_set = DNS
