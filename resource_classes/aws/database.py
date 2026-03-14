from . import _AWS


class _Database(_AWS):
    _type = "database"
    _icon_dir = "resource_images/aws/database"


#
class Aurora(_Database):
    _icon = "aurora-instance.png"


class AuroraMysql(_Database):
    _icon = "aurora-instance.png"


class AuroraPostgres(_Database):
    _icon = "aurora-instance.png"


class DatabaseMigrationService(_Database):
    _icon = "database-migration-service.png"


class Database(_Database):
    _icon = "database.png"


class DocumentDB(_Database):
    _icon = "documentdb-mongodb-compatibility.png"


class DynamodbDax(_Database):
    _icon = "dynamodb-dax.png"


class DynamodbGlobalSecondaryIndex(_Database):
    _icon = "dynamodb-global-secondary-index.png"


class DynamodbTable(_Database):
    _icon = "dynamodb-table.png"


class Dynamodb(_Database):
    _icon = "dynamodb.png"


class Elasticache(_Database):
    _icon = "elasticache.png"


class Neptune(_Database):
    _icon = "neptune.png"


class QuantumLedgerDatabaseQldb(_Database):
    _icon = "quantum-ledger-database-qldb.png"


class RDSOnVmware(_Database):
    _icon = "rds-on-vmware.png"


class RDS(_Database):
    _icon = "rds.png"


class RDSInstance(_Database):
    _icon = "rds-instance.png"


class RDSPostgresql(_Database):
    _icon = "rds-postgresql-instance.png"


class RDSMysql(_Database):
    _icon = "rds-mysql-instance.png"


class RDSMariadb(_Database):
    _icon = "rds-mariadb-instance.png"


class RDSOracle(_Database):
    _icon = "rds-oracle-instance.png"


class RDSSqlServer(_Database):
    _icon = "rds-sql-server-instance.png"


class Redshift(_Database):
    _icon = "redshift.png"


class Timestream(_Database):
    _icon = "timestream.png"


# Aliases

DMS = DatabaseMigrationService
DAX = DynamodbDax
DynamodbGSI = DynamodbGlobalSecondaryIndex
DB = Database
DDB = Dynamodb
ElastiCache = Elasticache
QLDB = QuantumLedgerDatabaseQldb

# Terraform resource mappings
aws_rds_cluster = RDS
aws_rds = RDS
aws_rds_aurora = Aurora
aws_db_instance = RDS
aws_dms_replication_instance = DatabaseMigrationService
aws_docdb_cluster = DocumentDB
aws_dax_cluster = DynamodbDax
aws_dynamodb_table = DynamodbTable
aws_dynamodb_global_table = Dynamodb
aws_elasticache_cluster = ElastiCache
aws_neptune_cluster = Neptune
aws_qldb_ledger = QuantumLedgerDatabaseQldb
aws_redshift_cluster = Redshift
aws_elasticache_replication_group = Elasticache
aws_rds_postgres = RDSPostgresql
aws_rds_aurora_mysql = AuroraMysql
aws_rds_aurora_postgres = AuroraPostgres
aws_rds_mysql = RDSMysql
aws_rds_mariadb = RDSMariadb
aws_rds_oracle = RDSOracle
aws_rds_sqlserver = RDSSqlServer
