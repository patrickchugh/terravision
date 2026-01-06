# Azure Kubernetes Service (AKS) Test Configuration
# User Story 3: Azure Container and Kubernetes Services
# Tests: AKS cluster in VNet, ACR connection, node pool zone expansion

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
}

# Resource Group
resource "azurerm_resource_group" "aks" {
  name     = "rg-aks-test"
  location = "eastus"
}

# Virtual Network for AKS
resource "azurerm_virtual_network" "aks" {
  name                = "vnet-aks"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.aks.location
  resource_group_name = azurerm_resource_group.aks.name
}

# Subnet for AKS nodes
resource "azurerm_subnet" "aks_nodes" {
  name                 = "snet-aks-nodes"
  resource_group_name  = azurerm_resource_group.aks.name
  virtual_network_name = azurerm_virtual_network.aks.name
  address_prefixes     = ["10.0.1.0/24"]
}

# Azure Container Registry
resource "azurerm_container_registry" "acr" {
  name                = "acrakstest"
  resource_group_name = azurerm_resource_group.aks.name
  location            = azurerm_resource_group.aks.location
  sku                 = "Standard"
  admin_enabled       = false
}

# AKS Cluster with VNet integration and multiple node pools
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "aks-cluster"
  location            = azurerm_resource_group.aks.location
  resource_group_name = azurerm_resource_group.aks.name
  dns_prefix          = "akstest"

  default_node_pool {
    name                = "default"
    node_count          = 3
    vm_size             = "Standard_DS2_v2"
    vnet_subnet_id      = azurerm_subnet.aks_nodes.id
    zones               = ["1", "2", "3"]
    enable_auto_scaling = true
    min_count           = 1
    max_count           = 5
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    load_balancer_sku = "standard"
  }
}

# Additional node pool for workloads (spans zones)
resource "azurerm_kubernetes_cluster_node_pool" "workload" {
  name                  = "workload"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.aks.id
  vm_size               = "Standard_DS3_v2"
  node_count            = 3
  zones                 = ["1", "2", "3"]
  vnet_subnet_id        = azurerm_subnet.aks_nodes.id

  enable_auto_scaling = true
  min_count           = 1
  max_count           = 10
}

# Role assignment for ACR pull from AKS
resource "azurerm_role_assignment" "aks_acr" {
  principal_id                     = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.acr.id
  skip_service_principal_aad_check = true
}

# Log Analytics Workspace for AKS monitoring
resource "azurerm_log_analytics_workspace" "aks" {
  name                = "law-aks-monitoring"
  location            = azurerm_resource_group.aks.location
  resource_group_name = azurerm_resource_group.aks.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# Storage Account for AKS persistent volumes
resource "azurerm_storage_account" "aks" {
  name                     = "stakstest"
  resource_group_name      = azurerm_resource_group.aks.name
  location                 = azurerm_resource_group.aks.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
