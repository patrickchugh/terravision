from . import _AWS


class _Migration(_AWS):
    _type = "migration"
    _icon_dir = "resource_images/aws/migration"


class ApplicationDiscoveryService(_Migration):
    _icon = "application-discovery-service.png"


class CloudendureMigration(_Migration):
    _icon = "cloudendure-migration.png"


class DatabaseMigrationService(_Migration):
    _icon = "database-migration-service.png"


class Datasync(_Migration):
    _icon = "datasync.png"


class MigrationAndTransfer(_Migration):
    _icon = "migration-and-transfer.png"


class MigrationHub(_Migration):
    _icon = "migration-hub.png"


class ServerMigrationService(_Migration):
    _icon = "server-migration-service.png"


class SnowballEdge(_Migration):
    _icon = "snowball-edge.png"


class Snowball(_Migration):
    _icon = "snowball.png"


class Snowmobile(_Migration):
    _icon = "snowmobile.png"


class TransferForSftp(_Migration):
    _icon = "transfer-for-sftp.png"


# Aliases

ADS = ApplicationDiscoveryService
CEM = CloudendureMigration
DMS = DatabaseMigrationService
MAT = MigrationAndTransfer
SMS = ServerMigrationService

# Terraform aliases
aws_dms_endpoint = DatabaseMigrationService
aws_dms_replication_instance = DatabaseMigrationService
aws_dms_replication_task = DatabaseMigrationService
aws_datasync_agent = Datasync
aws_datasync_location_s3 = Datasync
aws_datasync_task = Datasync
aws_storagegateway_gateway = MigrationAndTransfer
aws_transfer_server = TransferForSftp
aws_transfer_user = TransferForSftp
