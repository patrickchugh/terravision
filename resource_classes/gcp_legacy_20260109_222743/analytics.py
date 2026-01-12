from . import _GCP


class _Analytics(_GCP):
    _type = "analytics"
    _icon_dir = "resources/gcp/analytics"


class Bigquery(_Analytics):
    _icon = "bigquery.png"


class Composer(_Analytics):
    _icon = "composer.png"


class DataCatalog(_Analytics):
    _icon = "data-catalog.png"


class DataFusion(_Analytics):
    _icon = "data-fusion.png"


class Dataflow(_Analytics):
    _icon = "dataflow.png"


class Datalab(_Analytics):
    _icon = "datalab.png"


class Dataprep(_Analytics):
    _icon = "dataprep.png"


class Dataproc(_Analytics):
    _icon = "dataproc.png"


class Genomics(_Analytics):
    _icon = "genomics.png"


class Looker(_Analytics):
    _icon = "looker.png"


class Pubsub(_Analytics):
    _icon = "pubsub.png"


# Aliases

BigQuery = Bigquery
PubSub = Pubsub

# Terraform aliases
google_bigquery_dataset = Bigquery
google_bigquery_table = Bigquery
google_bigquery_job = Bigquery
google_composer_environment = Composer
google_data_catalog_entry = DataCatalog
google_data_fusion_instance = DataFusion
google_dataflow_job = Dataflow
google_dataproc_cluster = Dataproc
google_dataproc_job = Dataproc
google_pubsub_topic = Pubsub
google_pubsub_subscription = Pubsub
