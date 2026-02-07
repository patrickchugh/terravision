resource "aws_vpc" "local" {
  cidr_block = var.cidr_block

  tags = {
    Name = var.name
  }
}

resource "aws_subnet" "local" {
  vpc_id     = aws_vpc.local.id
  cidr_block = var.subnet_cidr

  tags = {
    Name = "${var.name}-subnet"
  }
}

variable "cidr_block" {
  default = "10.0.0.0/16"
}

variable "subnet_cidr" {
  default = "10.0.1.0/24"
}

variable "name" {
  default = "local-vpc"
}
