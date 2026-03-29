terraform {
  source = "."
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id    = "vpc-mock-12345"
    subnet_id = "subnet-mock-12345"
  }
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

generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  backend "s3" {
    bucket = "my-company-terraform-state"
    key    = "app/terraform.tfstate"
    region = "us-east-1"
  }
}
EOF
}

inputs = {
  subnet_id = dependency.vpc.outputs.subnet_id
}
