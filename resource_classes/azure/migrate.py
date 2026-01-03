from . import _Azure


class _Migrate(_Azure):
    _type = "migrate"
    _icon_dir = "resource_images/azure/migrate"


class AzureDataboxGateway(_Migrate):
    _icon = "azure-databox-gateway.png"


class AzureMigrate(_Migrate):
    _icon = "azure-migrate.png"


class AzureStackEdge(_Migrate):
    _icon = "azure-stack-edge.png"


class CostManagementAndBilling(_Migrate):
    _icon = "cost-management-and-billing.png"


class DataBox(_Migrate):
    _icon = "data-box.png"


class RecoveryServicesVaults(_Migrate):
    _icon = "recovery-services-vaults.png"


# Aliases

# Terraform aliases
azurerm_site_recovery_fabric = AzureMigrate
azurerm_site_recovery_replicated_vm = AzureMigrate
azurerm_recovery_services_vault = RecoveryServicesVaults
