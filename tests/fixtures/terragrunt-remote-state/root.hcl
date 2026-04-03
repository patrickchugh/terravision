# Root configuration using generate "backend" pattern.
# Tests local modules with dependencies, includes, and cross-module refs.
# Note: remote_state blocks trigger S3 validation at the Terragrunt level
# which requires real bucket access; generate "backend" produces the same
# backend.tf without the Terragrunt-level validation.

generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  backend "s3" {
    bucket = "my-company-terraform-state"
    key    = "${path_relative_to_include()}/terraform.tfstate"
    region = "us-east-1"
  }
}
EOF
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "us-east-1"
}
EOF
}
