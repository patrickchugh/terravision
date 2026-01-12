"""
GCP Data Analytics category - BigQuery, Dataflow, Dataproc, Pub/Sub.

Icon Resolution:
- BigQuery uses unique icon (4-color): resource_images/gcp/unique/bigquery.png
- Looker uses unique icon (4-color): resource_images/gcp/unique/looker.png
- Other analytics resources use category icon (2-color): resource_images/gcp/category/analytics.png
"""

from . import _GCP


class _Analytics(_GCP):
    _type = "analytics"
    _icon_dir = "resource_images/gcp/category"
    _icon = "analytics.png"


class BigQuery(_Analytics):
    """BigQuery data warehouse - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "bigquery.png"


class Looker(_Analytics):
    """Looker BI platform - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "looker.png"


class Dataflow(_Analytics):
    """Dataflow stream/batch processing."""

    _icon = "analytics.png"


class Dataproc(_Analytics):
    """Dataproc managed Spark/Hadoop."""

    _icon = "analytics.png"


class PubSub(_Analytics):
    """Pub/Sub messaging service."""

    _icon = "analytics.png"


class DataCatalog(_Analytics):
    """Data Catalog for metadata management."""

    _icon = "analytics.png"


class Composer(_Analytics):
    """Cloud Composer managed Airflow."""

    _icon = "analytics.png"


class DataFusion(_Analytics):
    """Data Fusion ETL service."""

    _icon = "analytics.png"


class Dataplex(_Analytics):
    """Dataplex data governance."""

    _icon = "analytics.png"


class DataprocMetastore(_Analytics):
    """Dataproc Metastore for Hive."""

    _icon = "analytics.png"


class Datalab(_Analytics):
    """Datalab notebooks (deprecated)."""

    _icon = "analytics.png"


class Dataprep(_Analytics):
    """Dataprep data preparation."""

    _icon = "analytics.png"


class Genomics(_Analytics):
    """Life Sciences API for genomics."""

    _icon = "analytics.png"


class Healthcare(_Analytics):
    """Healthcare API for FHIR/HL7."""

    _icon = "analytics.png"


# Aliases
BQ = BigQuery
Bigquery = BigQuery
Pubsub = PubSub
Datawarehouse = BigQuery

# Terraform resource aliases
google_bigquery_dataset = BigQuery
google_bigquery_table = BigQuery
google_bigquery_job = BigQuery
google_bigquery_data_transfer_config = BigQuery
google_bigquery_connection = BigQuery
google_bigquery_reservation = BigQuery
google_dataflow_job = Dataflow
google_dataproc_cluster = Dataproc
google_dataproc_job = Dataproc
google_pubsub_topic = PubSub
google_pubsub_subscription = PubSub
google_pubsub_schema = PubSub
google_data_catalog_entry = DataCatalog
google_data_catalog_tag_template = DataCatalog
google_composer_environment = Composer
google_data_fusion_instance = DataFusion
google_dataplex_lake = Dataplex
google_dataplex_zone = Dataplex
google_dataplex_asset = Dataplex
google_dataproc_metastore_service = DataprocMetastore
google_healthcare_dataset = Healthcare
google_healthcare_fhir_store = Healthcare
google_healthcare_hl7_v2_store = Healthcare
