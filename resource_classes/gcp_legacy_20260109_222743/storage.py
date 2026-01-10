from . import _GCP


class _Storage(_GCP):
    _type = "storage"
    _icon_dir = "resources/gcp/storage"


class Filestore(_Storage):
    _icon = "filestore.png"


class LocalSSD(_Storage):
    _icon = "local-ssd.png"


class PersistentDisk(_Storage):
    _icon = "persistent-disk.png"


class Storage(_Storage):
    _icon = "storage.png"


# Aliases

SSD = LocalSSD
GCS = Storage

# Terraform aliases
google_storage_bucket = Storage
google_storage_bucket_object = Storage
google_filestore_instance = Filestore
google_compute_disk = PersistentDisk
