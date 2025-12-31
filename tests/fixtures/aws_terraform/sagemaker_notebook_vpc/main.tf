# SageMaker Notebook Instance in VPC Pattern
# Tests: SageMaker notebook instance VPC placement, subnet placement, security group connections
# Expected: Notebook instance inside VPC/subnet with security group

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

# Subnet
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
}

# Security Group for Notebook
resource "aws_security_group" "notebook_sg" {
  name   = "sagemaker-notebook-sg"
  vpc_id = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# IAM role for SageMaker
resource "aws_iam_role" "sagemaker_role" {
  name = "sagemaker-notebook-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# S3 bucket for notebook storage
resource "aws_s3_bucket" "notebook_storage" {
  bucket = "sagemaker-notebook-storage"
}

# SageMaker Notebook Instance in VPC
resource "aws_sagemaker_notebook_instance" "ml_notebook" {
  name          = "ml-research-notebook"
  role_arn      = aws_iam_role.sagemaker_role.arn
  instance_type = "ml.t3.medium"

  # VPC configuration
  subnet_id         = aws_subnet.private.id
  security_groups   = [aws_security_group.notebook_sg.id]
  direct_internet_access = "Disabled"

  # S3 storage
  default_code_repository = "https://github.com/example/ml-notebooks"
}
