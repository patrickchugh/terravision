"""
GCP Databases category - Cloud SQL, Spanner, AlloyDB, Firestore, Bigtable.

Icon Resolution:
- Cloud SQL uses unique icon (4-color): resource_images/gcp/unique/cloud-sql.png
- Cloud Spanner uses unique icon (4-color): resource_images/gcp/unique/cloud-spanner.png
- AlloyDB uses unique icon (4-color): resource_images/gcp/unique/alloydb.png
- Other database resources use category icon (2-color): resource_images/gcp/category/databases.png
"""

from . import _GCP


class _Databases(_GCP):
    _type = "databases"
    _icon_dir = "resource_images/gcp/category"
    _icon = "databases.png"


class CloudSQL(_Databases):
    """Cloud SQL managed relational database - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "cloud-sql.png"


class Spanner(_Databases):
    """Cloud Spanner globally distributed database - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "cloud-spanner.png"


class AlloyDB(_Databases):
    """AlloyDB for PostgreSQL - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "alloydb.png"


class Firestore(_Databases):
    """Firestore NoSQL document database."""

    _icon = "databases.png"


class Bigtable(_Databases):
    """Cloud Bigtable wide-column NoSQL."""

    _icon = "databases.png"


class Memorystore(_Databases):
    """Memorystore for Redis/Memcached."""

    _icon = "databases.png"


class DatabaseMigrationService(_Databases):
    """Database Migration Service."""

    _icon = "databases.png"


class Datastream(_Databases):
    """Datastream for change data capture."""

    _icon = "databases.png"


# Aliases
SQL = CloudSQL
CloudSpanner = Spanner

# Terraform resource aliases
google_sql_database_instance = CloudSQL
google_sql_database = CloudSQL
google_sql_user = CloudSQL
google_spanner_instance = Spanner
google_spanner_database = Spanner
google_alloydb_cluster = AlloyDB
google_alloydb_instance = AlloyDB
google_firestore_database = Firestore
google_firestore_document = Firestore
google_bigtable_instance = Bigtable
google_bigtable_table = Bigtable
google_redis_instance = Memorystore
google_memcache_instance = Memorystore
google_database_migration_service_connection_profile = DatabaseMigrationService
google_datastream_stream = Datastream
google_datastream_connection_profile = Datastream
