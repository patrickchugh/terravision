# Test fixture for User Story 2: Azure Networking and Load Balancing
# Tests: Application Gateway, Load Balancer, Backend Pools, Traffic Distribution

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
  name     = "rg-terravision-lb-test"
  location = "East US"
}

# Virtual Network
resource "azurerm_virtual_network" "main" {
  name                = "vnet-terravision-lb-test"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# Subnet for backend VMs
resource "azurerm_subnet" "backend" {
  name                 = "subnet-backend"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

# Subnet for Application Gateway
resource "azurerm_subnet" "appgw" {
  name                 = "subnet-appgw"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]
}

# Public IP for Load Balancer
resource "azurerm_public_ip" "lb" {
  name                = "pip-lb-test"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1", "2", "3"]
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

# Load Balancer Backend Address Pool
resource "azurerm_lb_backend_address_pool" "main" {
  loadbalancer_id = azurerm_lb.main.id
  name            = "backend-pool"
}

# Load Balancer Probe
resource "azurerm_lb_probe" "main" {
  loadbalancer_id = azurerm_lb.main.id
  name            = "http-probe"
  protocol        = "Http"
  port            = 80
  request_path    = "/"
}

# Load Balancer Rule
resource "azurerm_lb_rule" "main" {
  loadbalancer_id                = azurerm_lb.main.id
  name                           = "http-rule"
  protocol                       = "Tcp"
  frontend_port                  = 80
  backend_port                   = 80
  frontend_ip_configuration_name = "frontend"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.main.id]
  probe_id                       = azurerm_lb_probe.main.id
}

# Network Interfaces for backend VMs
resource "azurerm_network_interface" "backend" {
  count               = 3
  name                = "nic-backend-${count.index + 1}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.backend.id
    private_ip_address_allocation = "Dynamic"
  }
}

# Associate NICs with Load Balancer Backend Pool
resource "azurerm_network_interface_backend_address_pool_association" "main" {
  count                   = 3
  network_interface_id    = azurerm_network_interface.backend[count.index].id
  ip_configuration_name   = "internal"
  backend_address_pool_id = azurerm_lb_backend_address_pool.main.id
}

# Backend VMs
resource "azurerm_linux_virtual_machine" "backend" {
  count               = 3
  name                = "vm-backend-${count.index + 1}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B1s"
  admin_username      = "adminuser"
  zone                = tostring(count.index + 1)

  network_interface_ids = [
    azurerm_network_interface.backend[count.index].id,
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

# Public IP for Application Gateway
resource "azurerm_public_ip" "appgw" {
  name                = "pip-appgw-test"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

# Application Gateway
resource "azurerm_application_gateway" "main" {
  name                = "appgw-terravision-test"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku {
    name     = "Standard_v2"
    tier     = "Standard_v2"
    capacity = 2
  }

  gateway_ip_configuration {
    name      = "gateway-ip-config"
    subnet_id = azurerm_subnet.appgw.id
  }

  frontend_port {
    name = "frontend-port"
    port = 80
  }

  frontend_ip_configuration {
    name                 = "frontend-ip-config"
    public_ip_address_id = azurerm_public_ip.appgw.id
  }

  backend_address_pool {
    name = "backend-pool"
    ip_addresses = [
      azurerm_network_interface.backend[0].private_ip_address,
      azurerm_network_interface.backend[1].private_ip_address,
      azurerm_network_interface.backend[2].private_ip_address,
    ]
  }

  backend_http_settings {
    name                  = "backend-http-settings"
    cookie_based_affinity = "Disabled"
    port                  = 80
    protocol              = "Http"
    request_timeout       = 60
  }

  http_listener {
    name                           = "http-listener"
    frontend_ip_configuration_name = "frontend-ip-config"
    frontend_port_name             = "frontend-port"
    protocol                       = "Http"
  }

  request_routing_rule {
    name                       = "routing-rule"
    rule_type                  = "Basic"
    http_listener_name         = "http-listener"
    backend_address_pool_name  = "backend-pool"
    backend_http_settings_name = "backend-http-settings"
    priority                   = 100
  }
}

# Output for verification
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "lb_frontend_ip" {
  value = azurerm_public_ip.lb.ip_address
}

output "appgw_frontend_ip" {
  value = azurerm_public_ip.appgw.ip_address
}
