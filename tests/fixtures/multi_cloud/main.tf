# Multi-Cloud Terraform Test Fixture
# Purpose: Test multi-cloud provider detection and separate diagram generation
# This fixture contains both AWS and Azure resources

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

# AWS Provider Configuration
provider "aws" {
  region = "us-east-1"
}

# Azure Provider Configuration
provider "azurerm" {
  features {}
}

# ==========================================
# AWS Resources
# ==========================================

# AWS VPC
resource "aws_vpc" "test" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "terravision-test-vpc"
    Environment = "test"
    Purpose     = "terravision-multi-cloud-fixture"
  }
}

# AWS Subnet
resource "aws_subnet" "test" {
  vpc_id                  = aws_vpc.test.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "terravision-test-subnet"
  }
}

# AWS Security Group
resource "aws_security_group" "test" {
  name        = "terravision-test-sg"
  description = "Test security group for TerraVision"
  vpc_id      = aws_vpc.test.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "terravision-test-sg"
  }
}

# AWS EC2 Instance
resource "aws_instance" "test" {
  ami           = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2
  instance_type = "t2.micro"
  subnet_id     = aws_subnet.test.id
  vpc_security_group_ids = [aws_security_group.test.id]

  tags = {
    Name        = "terravision-test-instance"
    Environment = "test"
  }
}

# AWS S3 Bucket
resource "aws_s3_bucket" "test" {
  bucket = "terravision-test-bucket-aws"

  tags = {
    Name        = "terravision-test-bucket"
    Environment = "test"
  }
}

# AWS RDS Instance
resource "aws_db_instance" "test" {
  identifier             = "terravision-test-db"
  engine                 = "postgres"
  engine_version         = "14.7"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  db_name                = "terravisiontest"
  username               = "testadmin"
  password               = "testpassword123"
  skip_final_snapshot    = true
  vpc_security_group_ids = [aws_security_group.test.id]
  db_subnet_group_name   = aws_db_subnet_group.test.name

  tags = {
    Name = "terravision-test-rds"
  }
}

# AWS DB Subnet Group
resource "aws_db_subnet_group" "test" {
  name       = "terravision-test-db-subnet-group"
  subnet_ids = [aws_subnet.test.id, aws_subnet.test2.id]

  tags = {
    Name = "terravision-test-db-subnet-group"
  }
}

# Second AWS Subnet for RDS (requires multiple AZs)
resource "aws_subnet" "test2" {
  vpc_id            = aws_vpc.test.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-east-1b"

  tags = {
    Name = "terravision-test-subnet-2"
  }
}

# ==========================================
# Azure Resources
# ==========================================

# Azure Resource Group
resource "azurerm_resource_group" "test" {
  name     = "terravision-test-rg"
  location = "East US"

  tags = {
    environment = "test"
    purpose     = "terravision-multi-cloud-fixture"
  }
}

# Azure Virtual Network
resource "azurerm_virtual_network" "test" {
  name                = "terravision-test-vnet"
  address_space       = ["10.1.0.0/16"]
  location            = azurerm_resource_group.test.location
  resource_group_name = azurerm_resource_group.test.name
}

# Azure Subnet
resource "azurerm_subnet" "test" {
  name                 = "terravision-test-subnet"
  resource_group_name  = azurerm_resource_group.test.name
  virtual_network_name = azurerm_virtual_network.test.name
  address_prefixes     = ["10.1.1.0/24"]
}

# Azure Network Interface
resource "azurerm_network_interface" "test" {
  name                = "terravision-test-nic"
  location            = azurerm_resource_group.test.location
  resource_group_name = azurerm_resource_group.test.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.test.id
    private_ip_address_allocation = "Dynamic"
  }
}

# Azure Virtual Machine
resource "azurerm_linux_virtual_machine" "test" {
  name                = "terravision-test-vm"
  resource_group_name = azurerm_resource_group.test.name
  location            = azurerm_resource_group.test.location
  size                = "Standard_B1s"
  admin_username      = "adminuser"

  network_interface_ids = [
    azurerm_network_interface.test.id,
  ]

  admin_ssh_key {
    username   = "adminuser"
    public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3"
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "18.04-LTS"
    version   = "latest"
  }
}

# Azure Storage Account
resource "azurerm_storage_account" "test" {
  name                     = "terravisionteststorage"
  resource_group_name      = azurerm_resource_group.test.name
  location                 = azurerm_resource_group.test.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = {
    environment = "test"
  }
}

# Azure SQL Server
resource "azurerm_mssql_server" "test" {
  name                         = "terravision-test-sqlserver"
  resource_group_name          = azurerm_resource_group.test.name
  location                     = azurerm_resource_group.test.location
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = "P@ssw0rd123!"

  tags = {
    environment = "test"
  }
}

# Azure SQL Database
resource "azurerm_mssql_database" "test" {
  name      = "terravision-test-db"
  server_id = azurerm_mssql_server.test.id
  sku_name  = "Basic"

  tags = {
    environment = "test"
  }
}
