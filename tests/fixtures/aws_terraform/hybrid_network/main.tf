# A hybrid, multi-VPC network: Direct Connect and a site-to-site VPN from a
# corporate data centre to a Transit Gateway, central inspection and egress
# VPCs, and spoke VPCs. plan.json and graph.dot were made offline with the mock
# credentials below (terraform plan, show -json, graph), so tests need neither
# Terraform nor AWS access.

terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "mock"
  secret_key                  = "mock"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
}

locals {
  azs = ["us-east-1a", "us-east-1b"]
}

# ---------- Hybrid connectivity ----------

resource "aws_customer_gateway" "datacentre_router" {
  bgp_asn    = 65010
  ip_address = "203.0.113.10"
  type       = "ipsec.1"
}

resource "aws_dx_connection" "primary" {
  name      = "corporate-dx-primary"
  bandwidth = "10Gbps"
  location  = "EqDC2"
}

resource "aws_dx_gateway" "corporate" {
  name            = "corporate"
  amazon_side_asn = "64512"
}

resource "aws_dx_transit_virtual_interface" "corporate" {
  connection_id  = aws_dx_connection.primary.id
  dx_gateway_id  = aws_dx_gateway.corporate.id
  name           = "corporate-transit-vif"
  vlan           = 100
  address_family = "ipv4"
  bgp_asn        = 65010
}

resource "aws_dx_gateway_association" "hub" {
  dx_gateway_id         = aws_dx_gateway.corporate.id
  associated_gateway_id = aws_ec2_transit_gateway.hub.id
  allowed_prefixes      = ["10.100.0.0/14"]
}

resource "aws_vpn_connection" "ipsec_vpn" {
  customer_gateway_id = aws_customer_gateway.datacentre_router.id
  transit_gateway_id  = aws_ec2_transit_gateway.hub.id
  type                = "ipsec.1"
}

# ---------- Transit Gateway ----------

resource "aws_ec2_transit_gateway" "hub" {
  description                     = "Network hub"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
}

resource "aws_ec2_transit_gateway_route_table" "spokes" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
}

resource "aws_ec2_transit_gateway_route_table" "inspection" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
}

resource "aws_ec2_transit_gateway_route" "spokes_default" {
  destination_cidr_block         = "0.0.0.0/0"
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.spokes.id
}

resource "aws_ec2_transit_gateway_route" "inspection_default" {
  destination_cidr_block         = "0.0.0.0/0"
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.egress.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.inspection.id
}

# ---------- Inspection VPC ----------

resource "aws_vpc" "inspection" {
  cidr_block = "10.100.0.0/24"
}

resource "aws_subnet" "inspection_tgw" {
  count             = 2
  vpc_id            = aws_vpc.inspection.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet("10.100.0.128/27", 1, count.index)
}

resource "aws_subnet" "firewall" {
  count             = 2
  vpc_id            = aws_vpc.inspection.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet("10.100.0.0/25", 1, count.index)
}

resource "aws_ec2_transit_gateway_vpc_attachment" "inspection" {
  transit_gateway_id     = aws_ec2_transit_gateway.hub.id
  vpc_id                 = aws_vpc.inspection.id
  subnet_ids             = aws_subnet.inspection_tgw[*].id
  appliance_mode_support = "enable"
}

resource "aws_networkfirewall_rule_group" "allowed_domains" {
  capacity = 100
  name     = "allowed-domains"
  type     = "STATEFUL"
  rule_group {
    rules_source {
      rules_source_list {
        generated_rules_type = "ALLOWLIST"
        target_types         = ["TLS_SNI", "HTTP_HOST"]
        targets              = [".amazonaws.com"]
      }
    }
  }
}

resource "aws_networkfirewall_firewall_policy" "central" {
  name = "central"
  firewall_policy {
    stateless_default_actions          = ["aws:forward_to_sfe"]
    stateless_fragment_default_actions = ["aws:forward_to_sfe"]
    stateful_rule_group_reference {
      resource_arn = aws_networkfirewall_rule_group.allowed_domains.arn
    }
  }
}

resource "aws_networkfirewall_firewall" "inspection" {
  name                = "inspection"
  firewall_policy_arn = aws_networkfirewall_firewall_policy.central.arn
  vpc_id              = aws_vpc.inspection.id
  dynamic "subnet_mapping" {
    for_each = aws_subnet.firewall[*].id
    content {
      subnet_id = subnet_mapping.value
    }
  }
}

# ---------- Egress VPC ----------

resource "aws_vpc" "egress" {
  cidr_block = "10.100.1.0/24"
}

resource "aws_subnet" "egress_tgw" {
  count             = 2
  vpc_id            = aws_vpc.egress.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet("10.100.1.128/27", 1, count.index)
}

resource "aws_subnet" "egress_public" {
  count             = 2
  vpc_id            = aws_vpc.egress.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet("10.100.1.0/25", 1, count.index)
}

resource "aws_internet_gateway" "egress" {
  vpc_id = aws_vpc.egress.id
}

resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"
}

resource "aws_nat_gateway" "egress" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.egress_public[count.index].id
}

resource "aws_ec2_transit_gateway_vpc_attachment" "egress" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  vpc_id             = aws_vpc.egress.id
  subnet_ids         = aws_subnet.egress_tgw[*].id
}

# ---------- Production VPC ----------

resource "aws_vpc" "production" {
  cidr_block = "10.110.0.0/16"
}

resource "aws_subnet" "production_tgw" {
  vpc_id            = aws_vpc.production.id
  availability_zone = local.azs[0]
  cidr_block        = "10.110.0.0/28"
}

resource "aws_subnet" "production_app" {
  count             = 2
  vpc_id            = aws_vpc.production.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet("10.110.16.0/20", 1, count.index)
}

resource "aws_ec2_transit_gateway_vpc_attachment" "production" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  vpc_id             = aws_vpc.production.id
  subnet_ids         = [aws_subnet.production_tgw.id]
}

resource "aws_security_group" "orders_alb" {
  vpc_id = aws_vpc.production.id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
}

resource "aws_security_group" "orders_tasks" {
  vpc_id = aws_vpc.production.id
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.orders_alb.id]
  }
}

resource "aws_lb" "orders_internal" {
  name               = "orders-internal"
  internal           = true
  load_balancer_type = "application"
  subnets            = aws_subnet.production_app[*].id
  security_groups    = [aws_security_group.orders_alb.id]
}

resource "aws_lb_target_group" "orders" {
  name        = "orders"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.production.id
}

resource "aws_lb_listener" "orders" {
  load_balancer_arn = aws_lb.orders_internal.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = "arn:aws:acm:us-east-1:111111111111:certificate/mock"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.orders.arn
  }
}

resource "aws_ecs_cluster" "orders" {
  name = "orders"
}

resource "aws_ecs_task_definition" "orders" {
  family                   = "orders"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  container_definitions = jsonencode([{
    name         = "orders"
    image        = "orders:latest"
    portMappings = [{ containerPort = 8080 }]
  }])
}

resource "aws_ecs_service" "orders" {
  name            = "orders"
  cluster         = aws_ecs_cluster.orders.id
  task_definition = aws_ecs_task_definition.orders.arn
  desired_count   = 2
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.production_app[*].id
    security_groups = [aws_security_group.orders_tasks.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.orders.arn
    container_name   = "orders"
    container_port   = 8080
  }
}

resource "aws_db_subnet_group" "orders" {
  subnet_ids = aws_subnet.production_app[*].id
}

resource "aws_db_instance" "orders" {
  identifier           = "orders"
  engine               = "postgres"
  instance_class       = "db.t4g.medium"
  allocated_storage    = 50
  username             = "orders"
  password             = "mock-password-not-real"
  db_subnet_group_name = aws_db_subnet_group.orders.name
  skip_final_snapshot  = true
}

# ---------- Development VPC ----------

resource "aws_vpc" "development" {
  cidr_block = "10.120.0.0/16"
}

resource "aws_subnet" "development_tgw" {
  vpc_id            = aws_vpc.development.id
  availability_zone = local.azs[0]
  cidr_block        = "10.120.0.0/28"
}

resource "aws_subnet" "development_app" {
  vpc_id            = aws_vpc.development.id
  availability_zone = local.azs[0]
  cidr_block        = "10.120.16.0/20"
}

resource "aws_ec2_transit_gateway_vpc_attachment" "development" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  vpc_id             = aws_vpc.development.id
  subnet_ids         = [aws_subnet.development_tgw.id]
}

resource "aws_instance" "dev_workloads" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.medium"
  subnet_id     = aws_subnet.development_app.id
}

# ---------- Shared services VPC ----------

resource "aws_vpc" "shared_services" {
  cidr_block = "10.130.0.0/16"
}

resource "aws_subnet" "shared_tgw" {
  vpc_id            = aws_vpc.shared_services.id
  availability_zone = local.azs[0]
  cidr_block        = "10.130.0.0/28"
}

resource "aws_subnet" "shared_endpoints" {
  count             = 2
  vpc_id            = aws_vpc.shared_services.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet("10.130.1.0/24", 1, count.index)
}

resource "aws_ec2_transit_gateway_vpc_attachment" "shared_services" {
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  vpc_id             = aws_vpc.shared_services.id
  subnet_ids         = [aws_subnet.shared_tgw.id]
}

resource "aws_vpc_endpoint" "ssm" {
  vpc_id            = aws_vpc.shared_services.id
  service_name      = "com.amazonaws.us-east-1.ssm"
  vpc_endpoint_type = "Interface"
  subnet_ids        = aws_subnet.shared_endpoints[*].id
}

resource "aws_directory_service_directory" "corporate_ad" {
  name     = "corp.example.com"
  password = "MockPassword123!"
  type     = "MicrosoftAD"
  vpc_settings {
    vpc_id     = aws_vpc.shared_services.id
    subnet_ids = aws_subnet.shared_endpoints[*].id
  }
}

# ---------- Shared services ----------

resource "aws_kms_key" "network" {
  description = "Network logs"
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  name       = "vpc-flow-logs"
  kms_key_id = aws_kms_key.network.arn
}
