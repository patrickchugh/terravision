from . import _GCP


class _Migration(_GCP):
    _type = "migration"
    _icon_dir = "resources/gcp/migration"


class MigrateComputeEngine(_Migration):
    _icon = "migrate-compute-engine.png"


class TransferAppliance(_Migration):
    _icon = "transfer-appliance.png"


# Aliases

CE = MigrateComputeEngine

# Terraform aliases
google_storage_transfer_job = TransferAppliance
