from . import _Azure


class _Migration(_Azure):
    _type = "migration"
    _icon_dir = "resource_images/azure/migration"


class AzureDatabaseMigrationServices(_Migration):
    _icon = "azure-database-migration-services.png"


class DataBoxEdge(_Migration):
    _icon = "data-box-edge.png"


class DataBox(_Migration):
    _icon = "data-box.png"


class DatabaseMigrationServices(_Migration):
    _icon = "database-migration-services.png"


class MigrationProjects(_Migration):
    _icon = "migration-projects.png"


class RecoveryServicesVaults(_Migration):
    _icon = "recovery-services-vaults.png"


# Aliases

# Terraform aliases
azurerm_database_migration_service = DatabaseMigrationServices
azurerm_database_migration_project = MigrationProjects
azurerm_recovery_services_vault = RecoveryServicesVaults
