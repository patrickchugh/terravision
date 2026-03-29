# Mirrors user's exact pattern from issue #114:
# - locals with read_terragrunt_config(find_in_parent_folders("account.hcl"))
# - include "root" with find_in_parent_folders("root.hcl")
# - dependency blocks referencing other modules
# - inputs wiring dependency outputs to variables

locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  environment  = local.account_vars.locals.environment
  tags = {
    Service     = "data-stores"
    Environment = local.environment
    Component   = "PostgreSQL"
  }
}

terraform {
  # Use a real public module to test remote git source + include pattern.
  # This is the exact pattern from issue #114 (just a public repo instead of private).
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-rds.git//modules/db_subnet_group?ref=v6.1.1"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "vpc" {
  config_path = "../../networking/vpc"

  mock_outputs = {
    vpc_id    = "vpc-mock-12345"
    subnet_id = "subnet-mock-12345"
  }
}

inputs = {
  vpc_id    = dependency.vpc.outputs.vpc_id
  subnet_id = dependency.vpc.outputs.subnet_id
}
