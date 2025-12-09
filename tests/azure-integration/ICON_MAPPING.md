# Azure Resource Icon Mapping

Complete mapping of Azure Terraform resources to their icon files in TerraVision.

## Icon Verification

All icon files have been verified to exist in the repository.

| Terraform Resource | Python Class | Icon File | Path | Size | Status |
|-------------------|--------------|-----------|------|------|--------|
| `azurerm_resource_group` | ResourceGroups | resource-groups.png | `azure/general/` | 11K | ✅ |
| `azurerm_virtual_network` | VirtualNetworks | virtual-networks.png | `azure/network/` | 8.0K | ✅ |
| `azurerm_subnet` | Subnets | subnets.png | `azure/network/` | 60K | ✅ |
| `azurerm_network_security_group` | NetworkSecurityGroupsClassic | network-security-groups-classic.png | `azure/network/` | 8.5K | ✅ |
| `azurerm_service_plan` | AppServicePlans | app-service-plans.png | `azure/web/` | 7.5K | ✅ |
| `azurerm_linux_web_app` | AppServices | app-services.png | `azure/web/` | 30K | ✅ |
| `azurerm_kubernetes_cluster` | KubernetesServices | kubernetes-services.png | `azure/containers/` | 12K | ✅ |
| `azurerm_container_registry` | ContainerRegistries | container-registries.png | `azure/containers/` | 12K | ✅ |
| `azurerm_mssql_server` | SQLServer | sql-server.png | `azure/databases/` | 14K | ✅ |
| `azurerm_mssql_database` | SQLDatabase | sql-database.png | `azure/databases/` | 12K | ✅ |
| `azurerm_storage_account` | StorageAccounts | storage-accounts.png | `azure/storage/` | 2.5K | ✅ |
| `azurerm_key_vault` | KeyVaults | key-vaults.png | `azure/security/` | 24K | ✅ |
| `azurerm_log_analytics_workspace` | LogAnalyticsWorkspaces | log-analytics-workspaces.png | `azure/managementgovernance/` | 5.5K | ✅ |

## Categories

### Containers
- `azurerm_kubernetes_cluster` → KubernetesServices
- `azurerm_container_registry` → ContainerRegistries

### Databases
- `azurerm_mssql_server` → SQLServer
- `azurerm_mssql_database` → SQLDatabase

### General
- `azurerm_resource_group` → ResourceGroups

### Managementgovernance
- `azurerm_log_analytics_workspace` → LogAnalyticsWorkspaces

### Network
- `azurerm_virtual_network` → VirtualNetworks
- `azurerm_subnet` → Subnets
- `azurerm_network_security_group` → NetworkSecurityGroupsClassic

### Security
- `azurerm_key_vault` → KeyVaults

### Storage
- `azurerm_storage_account` → StorageAccounts

### Web
- `azurerm_service_plan` → AppServicePlans
- `azurerm_linux_web_app` → AppServices

## Total Azure Icons Available

- **808 Azure icon files** across 33 service categories
- **13 resources tested** in integration tests
- **100% icon coverage** for tested resources
