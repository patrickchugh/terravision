locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  environment  = local.account_vars.locals.environment
}

terraform {
  source = "${get_parent_terragrunt_dir()}/modules//ec2"
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
  subnet_id   = dependency.vpc.outputs.subnet_id
  environment = local.environment
}
