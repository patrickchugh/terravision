from . import _Azure


class _Network(_Azure):
    _type = "network"
    _icon_dir = "resource_images/azure/network"


class ApplicationGateway(_Network):
    _icon = "application-gateway.png"


class ApplicationSecurityGroups(_Network):
    _icon = "application-security-groups.png"


class CDNProfiles(_Network):
    _icon = "cdn-profiles.png"


class Connections(_Network):
    _icon = "connections.png"


class DDOSProtectionPlans(_Network):
    _icon = "ddos-protection-plans.png"


class DNSPrivateZones(_Network):
    _icon = "dns-private-zones.png"


class DNSZones(_Network):
    _icon = "dns-zones.png"


class ExpressrouteCircuits(_Network):
    _icon = "expressroute-circuits.png"


class Firewall(_Network):
    _icon = "firewall.png"


class FrontDoors(_Network):
    _icon = "front-doors.png"


class LoadBalancers(_Network):
    _icon = "load-balancers.png"


class LocalNetworkGateways(_Network):
    _icon = "local-network-gateways.png"


class NetworkInterfaces(_Network):
    _icon = "network-interfaces.png"


class NetworkSecurityGroupsClassic(_Network):
    _icon = "network-security-groups-classic.png"


class NetworkWatcher(_Network):
    _icon = "network-watcher.png"


class OnPremisesDataGateways(_Network):
    _icon = "on-premises-data-gateways.png"


class PrivateEndpoint(_Network):
    _icon = "private-endpoint.png"


class PublicIpAddresses(_Network):
    _icon = "public-ip-addresses.png"


class ReservedIpAddressesClassic(_Network):
    _icon = "reserved-ip-addresses-classic.png"


class RouteFilters(_Network):
    _icon = "route-filters.png"


class RouteTables(_Network):
    _icon = "route-tables.png"


class ServiceEndpointPolicies(_Network):
    _icon = "service-endpoint-policies.png"


class Subnets(_Network):
    _icon = "subnets.png"


class TrafficManagerProfiles(_Network):
    _icon = "traffic-manager-profiles.png"


class VirtualNetworkClassic(_Network):
    _icon = "virtual-network-classic.png"


class VirtualNetworkGateways(_Network):
    _icon = "virtual-network-gateways.png"


class VirtualNetworks(_Network):
    _icon = "virtual-networks.png"


class VirtualWans(_Network):
    _icon = "virtual-wans.png"


# Aliases

# Terraform aliases
azurerm_application_gateway = ApplicationGateway
azurerm_application_security_group = ApplicationSecurityGroups
azurerm_cdn_profile = CDNProfiles
azurerm_cdn_endpoint = CDNProfiles
azurerm_virtual_network_gateway_connection = Connections
azurerm_network_ddos_protection_plan = DDOSProtectionPlans
azurerm_private_dns_zone = DNSPrivateZones
azurerm_dns_zone = DNSZones
azurerm_express_route_circuit = ExpressrouteCircuits
azurerm_firewall = Firewall
azurerm_frontdoor = FrontDoors
azurerm_lb = LoadBalancers
azurerm_local_network_gateway = LocalNetworkGateways
azurerm_network_interface = NetworkInterfaces
azurerm_network_watcher = NetworkWatcher
azurerm_private_endpoint = PrivateEndpoint
azurerm_public_ip = PublicIpAddresses
azurerm_route_table = RouteTables
azurerm_route = RouteTables
# Note: azurerm_subnet alias is defined in groups.py as a Cluster class
azurerm_traffic_manager_profile = TrafficManagerProfiles
azurerm_virtual_network_gateway = VirtualNetworkGateways
# Note: azurerm_virtual_network alias is defined in groups.py as a Cluster class
azurerm_virtual_wan = VirtualWans
azurerm_vpn_gateway = VirtualNetworkGateways
azurerm_network_security_group = NetworkSecurityGroupsClassic
