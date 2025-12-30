from . import _AWS


class _Network(_AWS):
    _type = "network"
    _icon_dir = "resource_images/aws/network"


class APIGatewayEndpoint(_Network):
    _icon = "api-gateway-endpoint.png"


class APIGateway(_Network):
    _icon = "api-gateway.png"


class AppMesh(_Network):
    _icon = "app-mesh.png"


class ClientVpn(_Network):
    _icon = "client-vpn.png"


class CloudMap(_Network):
    _icon = "cloud-map.png"


class CloudFrontDownloadDistribution(_Network):
    _icon = "cloudfront-download-distribution.png"


class CloudFrontEdgeLocation(_Network):
    _icon = "cloudfront-edge-location.png"


class CloudFrontStreamingDistribution(_Network):
    _icon = "cloudfront-streaming-distribution.png"


class CloudFront(_Network):
    _icon = "cloudfront.png"


class DirectConnect(_Network):
    _icon = "direct-connect.png"


class ElasticLoadBalancing(_Network):
    _icon = "elastic-load-balancing.png"


class ElbApplicationLoadBalancer(_Network):
    _icon = "elb-application-load-balancer.png"


class ElbClassicLoadBalancer(_Network):
    _icon = "elb-classic-load-balancer.png"


class ElbNetworkLoadBalancer(_Network):
    _icon = "elb-network-load-balancer.png"


class Endpoint(_Network):
    _icon = "endpoint.png"


class GlobalAccelerator(_Network):
    _icon = "global-accelerator.png"


class InternetGateway(_Network):
    _icon = "internet-gateway.png"


class Nacl(_Network):
    _icon = "nacl.png"


class NATGateway(_Network):
    _icon = "nat-gateway.png"


class NetworkingAndContentDelivery(_Network):
    _icon = "networking-and-content-delivery.png"


class PrivateSubnet(_Network):
    _icon = "private-subnet.png"


class Privatelink(_Network):
    _icon = "privatelink.png"


class PublicSubnet(_Network):
    _icon = "public-subnet.png"


class Route53HostedZone(_Network):
    _icon = "route-53-hosted-zone.png"


class Route53(_Network):
    _icon = "route-53.png"


class RouteTable(_Network):
    _icon = "route-table.png"


class SiteToSiteVpn(_Network):
    _icon = "site-to-site-vpn.png"


class TransitGateway(_Network):
    _icon = "transit-gateway.png"


class VPCCustomerGateway(_Network):
    _icon = "vpc-customer-gateway.png"


class VPCElasticNetworkAdapter(_Network):
    _icon = "vpc-elastic-network-adapter.png"


class VPCElasticNetworkInterface(_Network):
    _icon = "vpc-elastic-network-interface.png"


class VPCFlowLogs(_Network):
    _icon = "vpc-flow-logs.png"


class VPCPeering(_Network):
    _icon = "vpc-peering.png"


class VPCRouter(_Network):
    _icon = "vpc-router.png"


class VPCTrafficMirroring(_Network):
    _icon = "vpc-traffic-mirroring.png"


class VPC(_Network):
    _icon = "vpc.png"


class VpnConnection(_Network):
    _icon = "vpn-connection.png"


class VpnGateway(_Network):
    _icon = "vpn-gateway.png"


# Aliases

CF = CloudFront
ELB = ElasticLoadBalancing
GAX = GlobalAccelerator

# Terraform aliases
aws_api_gateway_rest_api = APIGateway
aws_api_gateway_stage = APIGateway
aws_api_gateway_deployment = APIGateway
aws_api_gateway_resource = APIGateway
aws_api_gateway_method = APIGateway
aws_api_gateway_integration = APIGateway
aws_apigatewayv2_api = APIGateway
aws_apigatewayv2_stage = APIGateway
aws_apigatewayv2_integration = APIGateway
aws_apigatewayv2_route = APIGateway
aws_appmesh_mesh = AppMesh
aws_appmesh_virtual_node = AppMesh
aws_appmesh_gateway_route = AppMesh
aws_ec2_client_vpn_endpoint = ClientVpn
aws_service_discovery_service = CloudMap
aws_cloudfront_distribution = CloudFront
# aws_cloudfront_origin_access_identity = CloudFront
aws_dx_gateway = DirectConnect
aws_dx_gateway_association_proposal = DirectConnect
aws_dx_gateway_association = DirectConnect
aws_dx_connection = DirectConnect
aws_dx = DirectConnect
aws_lb_target_group = ElasticLoadBalancing
aws_lb_listener = ElasticLoadBalancing
aws_lb = ElasticLoadBalancing
aws_elb = ElbClassicLoadBalancer
aws_lb_alb = ElbApplicationLoadBalancer
aws_lb_nlb = ElbNetworkLoadBalancer
aws_alb = ElbApplicationLoadBalancer
aws_nlb = ElbNetworkLoadBalancer
aws_vpc_endpoint = Endpoint
aws_vpc_endpoint_service = Endpoint
aws_globalaccelerator_accelerator = GlobalAccelerator
aws_globalaccelerator_listener = GlobalAccelerator
aws_internet_gateway = InternetGateway
aws_egress_only_internet_gateway = InternetGateway
aws_network_acl = Nacl
aws_network_acl_rule = Nacl
aws_nat_gateway = NATGateway
aws_route53_zone = Route53
aws_route53_record = Route53
aws_route53_health_check = Route53
# aws_route_table = RouteTable
# aws_route = RouteTable
aws_route_table_association = RouteTable
aws_vpn_connection = SiteToSiteVpn
aws_vpn_gateway = VpnGateway
aws_customer_gateway = VPCCustomerGateway
aws_ec2_transit_gateway = TransitGateway
aws_ec2_transit_gateway_vpc_attachment = TransitGateway
aws_vpc_peering_connection = VPCPeering
aws_vpc_peering_connection_accepter = VPCPeering
aws_network_interface = VPCElasticNetworkInterface
aws_efs_mount_target = VPCElasticNetworkInterface
aws_vpc_flow_log = VPCFlowLogs
