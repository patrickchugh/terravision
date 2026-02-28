terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# =============================================================================
# Local module sources
# =============================================================================

# 1. Local relative path (current directory)
module "local_vpc" {
  source     = "./modules/local_vpc"
  cidr_block = var.vpc_cidr
  name       = "local-vpc"
}

# =============================================================================
# Terraform Registry sources
# =============================================================================

# 2. Public registry
module "registry_vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.0"

  name = "registry-vpc"
  cidr = var.vpc_cidr
}

# 3. Public registry with // subfolder
module "registry_subfolder" {
  source = "terraform-aws-modules/iam/aws//modules/iam-user"

  name = "registry-iam-user"
}

# =============================================================================
# GitHub shorthand sources (github.com/owner/repo)
# =============================================================================

# 4. GitHub shorthand - bare domain/owner/repo
module "github_short" {
  source = "github.com/terraform-aws-modules/terraform-aws-s3-bucket"

  bucket = "github-short-test-bucket"
}

# 5. GitHub shorthand with // subfolder
module "github_short_subfolder" {
  source = "github.com/terraform-aws-modules/terraform-aws-iam//modules/iam-user"

  name = "github-short-iam-user"
}

# 6. GitHub shorthand with path subfolder (no //)
module "github_short_path" {
  source = "github.com/terraform-aws-modules/terraform-aws-iam/modules/iam-role"

  name = "github-short-role"
}

# 7. GitHub shorthand with ?ref tag
module "github_short_ref" {
  source = "github.com/terraform-aws-modules/terraform-aws-vpc?ref=v5.1.0"

  name = "github-short-ref-vpc"
  cidr = var.vpc_cidr
}

# =============================================================================
# git::https sources (bare, subfolder, ref, combined)
# =============================================================================

# 8. git::https - bare .git
module "git_https_sg" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-security-group.git"

  name   = "git-https-sg"
  vpc_id = module.registry_vpc.vpc_id
}

# 9. git::https with // subfolder
module "git_https_iam_policy" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-policy"

  name = "git-https-subfolder-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = ["*"]
    }]
  })
}

# 10. git::https with ?ref tag
module "git_https_vpc_ref" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v5.1.0"

  name = "git-https-ref-vpc"
  cidr = var.vpc_cidr
}

# 11. git::https with // subfolder AND ?ref tag
module "git_https_iam_account_ref" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-account?ref=v5.30.0"

  account_alias = "test-account-alias"
}

# =============================================================================
# git::https additional combinations
# =============================================================================

# 12. git::https - different repo (ALB)
module "git_https_alb" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-alb.git"

  name               = "git-https-alb"
  vpc_id             = module.registry_vpc.vpc_id
  subnets            = module.registry_vpc.public_subnets
  security_groups    = [module.git_https_sg.security_group_id]
  load_balancer_type = "application"
}

# 13. git::https with // subfolder (iam-group)
module "git_https_iam_group" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-group"

  name = "git-https-admin-group"
}

# 14. git::https with ?ref tag (different version)
module "git_https_vpc_ref_v5" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v5.0.0"

  name = "git-https-ref-v5-vpc"
  cidr = var.vpc_cidr
}

# 15. git::https with // subfolder AND ?ref tag
module "git_https_readonly_ref" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-read-only-policy?ref=v5.30.0"

  allowed_services = ["s3", "ec2", "rds"]
}

# =============================================================================
# GitLab sources (no shorthand -- must use git::https://)
# =============================================================================

# 16. GitLab - bare git::https
module "gitlab_vpc" {
  source = "git::https://gitlab.com/claranet-pcp/terraform/aws/tf-aws-vpc.git?ref=v1.0.0"

  customer        = "test"
  envname         = "dev"
  vpc_cidr        = var.vpc_cidr
  domain_name     = "test.local"
  private_subnets = ["10.0.1.0/24"]
  public_subnets  = ["10.0.2.0/24"]
}

# 17. GitLab - git::https with ?ref tag
module "gitlab_s3" {
  source = "git::https://gitlab.com/devinitly/terraform/modules/terraform-aws-s3-bucket.git?ref=master"

  bucket_name       = "gitlab-s3-test-bucket"
  region            = var.aws_region
  versioning_status = true
}


# =============================================================================
# Terraform Cloud private registry (requires TF_TOKEN_app_terraform_io env var)
# =============================================================================

# 19. Terraform Cloud registry (requires TF_TOKEN_app_terraform_io env var)
module "tfc_test" {
  source  = "app.terraform.io/patrickchugh/test-module/aws"
  version = "1.0.0"

  bucket_name = "tfc-test-bucket"
}

# =============================================================================
# Edge cases for caching bug (module name == subfolder name)
# =============================================================================

# 20. Module name matches subfolder name (the bug scenario)
module "iam-user" {
  source = "github.com/terraform-aws-modules/terraform-aws-iam//modules/iam-user"

  name = "cache-bug-iam-user"
}

# 21. Module name matches subfolder with git::https
module "iam-policy" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-policy"

  name = "cache-bug-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup"]
      Resource = ["*"]
    }]
  })
}

# 22. Module name matches subfolder with git:: prefix
module "iam-group" {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-group"

  name = "cache-bug-admin-group"
}
