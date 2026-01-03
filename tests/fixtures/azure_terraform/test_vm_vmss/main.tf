# Test fixture for User Story 1: Azure Compute Architecture Visualization
# Tests: Resource Group → VNet → Subnet → NSG → VM/VMSS hierarchy

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "rg-terravision-test"
  location = "East US"
}

# Virtual Network
resource "azurerm_virtual_network" "main" {
  name                = "vnet-terravision-test"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# Subnet
resource "azurerm_subnet" "main" {
  name                 = "subnet-main"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

# Network Security Group
resource "azurerm_network_security_group" "main" {
  name                = "nsg-terravision-test"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "allow-ssh"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# Associate NSG with Subnet
resource "azurerm_subnet_network_security_group_association" "main" {
  subnet_id                 = azurerm_subnet.main.id
  network_security_group_id = azurerm_network_security_group.main.id
}

# Network Interface for VM
resource "azurerm_network_interface" "vm" {
  name                = "nic-vm-test"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
  }
}

# Virtual Machine
resource "azurerm_linux_virtual_machine" "main" {
  name                = "vm-terravision-test"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B1s"
  admin_username      = "adminuser"

  network_interface_ids = [
    azurerm_network_interface.vm.id,
  ]

  admin_ssh_key {
    username   = "adminuser"
    public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCyFrHcRkppkmMfc2CD7UJO0lzdwauQU5GRfI94aDbf12rsSvsGROLp38JCj/2DofcJhxfzyT9i8+TXpv2t6o25Ql3J9j8zphOxGvMzNa7ekjxZI50P9YPTSP2VY98wH6oPTi2grR1IaUG9vvOufCS8qnQLSiJXOLFHLf/1tl/whhOvBU2B46l5XwC8RXfFk82i/3uRU8Bn5Xv9f6fzxV2Wi+eLuJkDiMrhp/+fEThC/Fwdz0QL3nw1vR/krrQx4mPLh5GacaGzi1y3R3p+s8rJ7bFIYwpyZqKq0ECIzlE9OLWu3ZlfnWzQbpOXatwJ63O0PUU1p+0uDtkMFqvuujnt terravision-test"
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

  disable_password_authentication = true
}

# Public IP for Load Balancer
resource "azurerm_public_ip" "lb" {
  name                = "pip-lb-test"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

# Load Balancer
resource "azurerm_lb" "main" {
  name                = "lb-terravision-test"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"

  frontend_ip_configuration {
    name                 = "frontend"
    public_ip_address_id = azurerm_public_ip.lb.id
  }
}

# Backend Address Pool
resource "azurerm_lb_backend_address_pool" "main" {
  loadbalancer_id = azurerm_lb.main.id
  name            = "vmss-backend-pool"
}

# Virtual Machine Scale Set
resource "azurerm_linux_virtual_machine_scale_set" "main" {
  name                = "vmss-terravision-test"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Standard_B1s"
  instances           = 3
  admin_username      = "adminuser"

  # Deploy across availability zones
  zones = ["1", "2", "3"]

  admin_ssh_key {
    username   = "adminuser"
    public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCyFrHcRkppkmMfc2CD7UJO0lzdwauQU5GRfI94aDbf12rsSvsGROLp38JCj/2DofcJhxfzyT9i8+TXpv2t6o25Ql3J9j8zphOxGvMzNa7ekjxZI50P9YPTSP2VY98wH6oPTi2grR1IaUG9vvOufCS8qnQLSiJXOLFHLf/1tl/whhOvBU2B46l5XwC8RXfFk82i/3uRU8Bn5Xv9f6fzxV2Wi+eLuJkDiMrhp/+fEThC/Fwdz0QL3nw1vR/krrQx4mPLh5GacaGzi1y3R3p+s8rJ7bFIYwpyZqKq0ECIzlE9OLWu3ZlfnWzQbpOXatwJ63O0PUU1p+0uDtkMFqvuujnt terravision-test"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "18.04-LTS"
    version   = "latest"
  }

  os_disk {
    storage_account_type = "Standard_LRS"
    caching              = "ReadWrite"
  }

  network_interface {
    name    = "vmss-nic"
    primary = true

    ip_configuration {
      name      = "internal"
      primary   = true
      subnet_id = azurerm_subnet.main.id

      # Associate with Load Balancer backend pool
      load_balancer_backend_address_pool_ids = [
        azurerm_lb_backend_address_pool.main.id
      ]
    }
  }

  disable_password_authentication = true
}

# Output for verification
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "vnet_name" {
  value = azurerm_virtual_network.main.name
}

output "vm_name" {
  value = azurerm_linux_virtual_machine.main.name
}

output "vmss_name" {
  value = azurerm_linux_virtual_machine_scale_set.main.name
}
