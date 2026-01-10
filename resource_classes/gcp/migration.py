"""
GCP Migration category - Migrate to Virtual Machines, Database Migration Service.

Icon Resolution:
- All migration resources use category icon (2-color): resource_images/gcp/category/migration.png
"""

from . import _GCP


class _Migration(_GCP):
    _type = "migration"
    _icon_dir = "resource_images/gcp/category"
    _icon = "migration.png"


class MigrateForCompute(_Migration):
    """Migrate to Virtual Machines."""

    pass


class MigrateComputeEngine(_Migration):
    """Migrate CE (legacy alias)."""

    pass


class MigrateForContainers(_Migration):
    """Migrate to Containers."""

    pass


class DatabaseMigrationService(_Migration):
    """Database Migration Service."""

    pass


class TransferAppliance(_Migration):
    """Transfer Appliance physical data transfer."""

    pass


class StorageTransferService(_Migration):
    """Storage Transfer Service."""

    pass


class BigQueryDataTransfer(_Migration):
    """BigQuery Data Transfer Service."""

    pass


class BatchCompute(_Migration):
    """Batch for HPC workloads."""

    pass


class VMware(_Migration):
    """VMware Engine for migration."""

    pass


# Aliases
DMS = DatabaseMigrationService
MigrateForVMs = MigrateForCompute
CE = MigrateComputeEngine

# Terraform resource aliases
google_database_migration_service_connection_profile = DatabaseMigrationService
google_database_migration_service_migration_job = DatabaseMigrationService
google_storage_transfer_job = StorageTransferService
google_bigquery_data_transfer_config = BigQueryDataTransfer
google_vmwareengine_private_cloud = VMware
google_vmwareengine_cluster = VMware
google_vmwareengine_network = VMware
google_batch_job = BatchCompute
