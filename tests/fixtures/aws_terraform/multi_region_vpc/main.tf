# Two regions: a primary VPC through the default provider and a disaster
# recovery VPC through an aliased provider. TerraVision draws each VPC in a
# box for its region.
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

provider "aws" {
  alias  = "dr"
  region = "eu-west-1"
}

resource "aws_vpc" "primary" {
  cidr_block = "10.40.0.0/16"
}

resource "aws_subnet" "primary_app" {
  vpc_id            = aws_vpc.primary.id
  cidr_block        = "10.40.1.0/24"
  availability_zone = "us-east-1a"
}

resource "aws_instance" "primary_app" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.primary_app.id
}

resource "aws_vpc" "dr" {
  provider   = aws.dr
  cidr_block = "10.41.0.0/16"
}

resource "aws_subnet" "dr_app" {
  provider          = aws.dr
  vpc_id            = aws_vpc.dr.id
  cidr_block        = "10.41.1.0/24"
  availability_zone = "eu-west-1a"
}

resource "aws_instance" "dr_app" {
  provider      = aws.dr
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.dr_app.id
}
