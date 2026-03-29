# Account-level variables — mirrors user's pattern of
# read_terragrunt_config(find_in_parent_folders("account.hcl"))

locals {
  environment = "staging"
  account_id  = "123456789012"
}
