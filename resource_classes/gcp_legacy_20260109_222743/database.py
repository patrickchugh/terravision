from . import _GCP


class _Database(_GCP):
    _type = "database"
    _icon_dir = "resources/gcp/database"


class Bigtable(_Database):
    _icon = "bigtable.png"


class Datastore(_Database):
    _icon = "datastore.png"


class Firestore(_Database):
    _icon = "firestore.png"


class Memorystore(_Database):
    _icon = "memorystore.png"


class Spanner(_Database):
    _icon = "spanner.png"


class SQL(_Database):
    _icon = "sql.png"


# Aliases

BigTable = Bigtable

# Terraform aliases
google_bigtable_instance = Bigtable
google_bigtable_table = Bigtable
google_datastore_index = Datastore
google_firestore_database = Firestore
google_firestore_document = Firestore
google_redis_instance = Memorystore
google_spanner_instance = Spanner
google_spanner_database = Spanner
google_sql_database_instance = SQL
google_sql_database = SQL
