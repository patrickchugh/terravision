# Mirrors user's pattern: include root, read account vars, local source
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  environment  = local.account_vars.locals.environment
}

terraform {
  # Use a real public module to test remote git source + include pattern.
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git//?ref=v5.9.0"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}
