locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  environment  = local.account_vars.locals.environment
}

terraform {
  source = "${get_parent_terragrunt_dir()}/modules//vpc"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  vpc_cidr    = "10.0.0.0/16"
  environment = local.environment
}
