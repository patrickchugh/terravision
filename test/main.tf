module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  azs = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d"]

  cidr = "10.100.0.0/16"

  private_subnets = ["10.100.64.0/20", "10.100.80.0/20", "10.100.96.0/20", "10.100.112.0/20"]
  public_subnets  = ["10.100.128.0/20", "10.100.144.0/20", "10.100.160.0/20", "10.100.176.0/20", "10.100.0.0/20", "10.100.16.0/20", "10.100.32.0/20", "10.100.48.0/20"]

  create_database_subnet_group = false
  enable_dns_hostnames         = true
  enable_dns_support           = true
  enable_nat_gateway           = true

  enable_vpn_gateway = false

  map_public_ip_on_launch = true

  propagate_private_route_tables_vgw = false
  propagate_public_route_tables_vgw  = false

  secondary_cidr_blocks = ["100.64.0.0/24"]

  single_nat_gateway = true
}
