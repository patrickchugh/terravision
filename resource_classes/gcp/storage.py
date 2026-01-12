"""
GCP Storage category - Cloud Storage, Filestore, Persistent Disk.

Icon Resolution:
- Cloud Storage uses unique icon (4-color): resource_images/gcp/unique/cloud-storage.png
- Hyperdisk uses unique icon (4-color): resource_images/gcp/unique/hyperdisk.png
- Other storage resources use category icon (2-color): resource_images/gcp/category/storage.png
"""

from . import _GCP


class _Storage(_GCP):
    _type = "storage"
    _icon_dir = "resource_images/gcp/category"
    _icon = "storage.png"


class CloudStorage(_Storage):
    """Cloud Storage object storage - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "cloud-storage.png"


class Hyperdisk(_Storage):
    """Hyperdisk high-performance block storage - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "hyperdisk.png"


class Filestore(_Storage):
    """Filestore managed NFS."""

    _icon = "storage.png"


class PersistentDisk(_Storage):
    """Persistent Disk block storage."""

    _icon = "storage.png"


class LocalSSD(_Storage):
    """Local SSD for high-performance temporary storage."""

    _icon = "storage.png"


class Backup(_Storage):
    """Backup and DR service."""

    _icon = "storage.png"


class TransferService(_Storage):
    """Storage Transfer Service."""

    _icon = "storage.png"


class TransferAppliance(_Storage):
    """Transfer Appliance for offline data transfer."""

    _icon = "storage.png"


# Aliases
GCS = CloudStorage
Bucket = CloudStorage
Storage = CloudStorage
SSD = LocalSSD

# Terraform resource aliases
google_storage_bucket = CloudStorage
google_storage_bucket_object = CloudStorage
google_storage_bucket_iam_binding = CloudStorage
google_storage_bucket_iam_member = CloudStorage
google_filestore_instance = Filestore
google_compute_disk = PersistentDisk
google_compute_region_disk = PersistentDisk
google_storage_transfer_job = TransferService
google_backup_dr_management_server = Backup
