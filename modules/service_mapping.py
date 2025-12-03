"""
Service mapping for cross-provider categorization.

This module provides canonical service categories that map provider-specific
resource types (aws_instance, azurerm_virtual_machine, google_compute_instance)
to semantic categories (compute.vm, network.lb, storage.object) for consistent
diagram organization across providers.
"""

from enum import Enum
from typing import Dict, Set


class ServiceCategory(Enum):
    """Canonical service categories for cross-provider semantic grouping"""

    # Compute
    COMPUTE_VM = "compute.vm"
    COMPUTE_CONTAINER = "compute.container"
    COMPUTE_SERVERLESS = "compute.serverless"
    COMPUTE_BATCH = "compute.batch"

    # Network
    NETWORK_VPC = "network.vpc"
    NETWORK_SUBNET = "network.subnet"
    NETWORK_LB = "network.lb"
    NETWORK_GATEWAY = "network.gateway"
    NETWORK_CDN = "network.cdn"
    NETWORK_DNS = "network.dns"
    NETWORK_FIREWALL = "network.firewall"

    # Storage
    STORAGE_OBJECT = "storage.object"
    STORAGE_BLOCK = "storage.block"
    STORAGE_FILE = "storage.file"
    STORAGE_ARCHIVE = "storage.archive"

    # Database
    DATABASE_RELATIONAL = "database.relational"
    DATABASE_NOSQL = "database.nosql"
    DATABASE_CACHE = "database.cache"
    DATABASE_DATAWAREHOUSE = "database.datawarehouse"
    DATABASE_GRAPH = "database.graph"

    # Security
    SECURITY_FIREWALL = "security.firewall"
    SECURITY_IAM = "security.iam"
    SECURITY_SECRETS = "security.secrets"
    SECURITY_KEYS = "security.keys"
    SECURITY_CERT = "security.cert"

    # Analytics
    ANALYTICS_STREAMING = "analytics.streaming"
    ANALYTICS_BATCH = "analytics.batch"
    ANALYTICS_BI = "analytics.bi"
    ANALYTICS_ETL = "analytics.etl"

    # ML/AI
    ML_TRAINING = "ml.training"
    ML_INFERENCE = "ml.inference"
    ML_NOTEBOOK = "ml.notebook"
    ML_FEATURE_STORE = "ml.feature_store"

    # Integration
    INTEGRATION_QUEUE = "integration.queue"
    INTEGRATION_EVENTBUS = "integration.eventbus"
    INTEGRATION_API = "integration.api"
    INTEGRATION_WORKFLOW = "integration.workflow"

    # Management
    MANAGEMENT_MONITORING = "management.monitoring"
    MANAGEMENT_LOGGING = "management.logging"
    MANAGEMENT_AUTOMATION = "management.automation"
    MANAGEMENT_COST = "management.cost"

    # Application
    APP_CONTAINER_REGISTRY = "app.container_registry"
    APP_ARTIFACT_REGISTRY = "app.artifact_registry"
    APP_CODE_REPO = "app.code_repo"

    # Media
    MEDIA_TRANSCODE = "media.transcode"
    MEDIA_STREAMING = "media.streaming"

    # IoT
    IOT_CORE = "iot.core"
    IOT_ANALYTICS = "iot.analytics"

    # Quantum
    QUANTUM_COMPUTE = "quantum.compute"

    # Robotics
    ROBOTICS_APP = "robotics.app"

    # Blockchain
    BLOCKCHAIN_NETWORK = "blockchain.network"

    # Generic (fallback)
    GENERIC = "generic"


class ServiceMapping:
    """Maps provider-specific resource types to canonical categories"""

    _mappings: Dict[str, ServiceCategory] = {
        # AWS Compute
        "aws_instance": ServiceCategory.COMPUTE_VM,
        "aws_ecs_task_definition": ServiceCategory.COMPUTE_CONTAINER,
        "aws_ecs_service": ServiceCategory.COMPUTE_CONTAINER,
        "aws_eks_cluster": ServiceCategory.COMPUTE_CONTAINER,
        "aws_lambda_function": ServiceCategory.COMPUTE_SERVERLESS,
        "aws_batch_job_definition": ServiceCategory.COMPUTE_BATCH,
        "aws_batch_compute_environment": ServiceCategory.COMPUTE_BATCH,
        # AWS Network
        "aws_vpc": ServiceCategory.NETWORK_VPC,
        "aws_subnet": ServiceCategory.NETWORK_SUBNET,
        "aws_lb": ServiceCategory.NETWORK_LB,
        "aws_elb": ServiceCategory.NETWORK_LB,
        "aws_alb": ServiceCategory.NETWORK_LB,
        "aws_internet_gateway": ServiceCategory.NETWORK_GATEWAY,
        "aws_nat_gateway": ServiceCategory.NETWORK_GATEWAY,
        "aws_vpn_gateway": ServiceCategory.NETWORK_GATEWAY,
        "aws_cloudfront_distribution": ServiceCategory.NETWORK_CDN,
        "aws_route53_zone": ServiceCategory.NETWORK_DNS,
        "aws_route53_record": ServiceCategory.NETWORK_DNS,
        # AWS Storage
        "aws_s3_bucket": ServiceCategory.STORAGE_OBJECT,
        "aws_ebs_volume": ServiceCategory.STORAGE_BLOCK,
        "aws_efs_file_system": ServiceCategory.STORAGE_FILE,
        "aws_glacier_vault": ServiceCategory.STORAGE_ARCHIVE,
        # AWS Database
        "aws_db_instance": ServiceCategory.DATABASE_RELATIONAL,
        "aws_rds_cluster": ServiceCategory.DATABASE_RELATIONAL,
        "aws_dynamodb_table": ServiceCategory.DATABASE_NOSQL,
        "aws_elasticache_cluster": ServiceCategory.DATABASE_CACHE,
        "aws_redshift_cluster": ServiceCategory.DATABASE_DATAWAREHOUSE,
        "aws_neptune_cluster": ServiceCategory.DATABASE_GRAPH,
        # AWS Security
        "aws_security_group": ServiceCategory.SECURITY_FIREWALL,
        "aws_network_acl": ServiceCategory.SECURITY_FIREWALL,
        "aws_iam_role": ServiceCategory.SECURITY_IAM,
        "aws_iam_policy": ServiceCategory.SECURITY_IAM,
        "aws_iam_user": ServiceCategory.SECURITY_IAM,
        "aws_iam_group": ServiceCategory.SECURITY_IAM,
        "aws_secretsmanager_secret": ServiceCategory.SECURITY_SECRETS,
        "aws_kms_key": ServiceCategory.SECURITY_KEYS,
        "aws_acm_certificate": ServiceCategory.SECURITY_CERT,
        # AWS Analytics
        "aws_kinesis_stream": ServiceCategory.ANALYTICS_STREAMING,
        "aws_kinesis_firehose_delivery_stream": ServiceCategory.ANALYTICS_STREAMING,
        "aws_emr_cluster": ServiceCategory.ANALYTICS_BATCH,
        "aws_quicksight_user": ServiceCategory.ANALYTICS_BI,
        "aws_glue_job": ServiceCategory.ANALYTICS_ETL,
        "aws_glue_crawler": ServiceCategory.ANALYTICS_ETL,
        # AWS ML/AI
        "aws_sagemaker_notebook_instance": ServiceCategory.ML_NOTEBOOK,
        "aws_sagemaker_model": ServiceCategory.ML_INFERENCE,
        "aws_sagemaker_training_job": ServiceCategory.ML_TRAINING,
        # AWS Integration
        "aws_sqs_queue": ServiceCategory.INTEGRATION_QUEUE,
        "aws_sns_topic": ServiceCategory.INTEGRATION_EVENTBUS,
        "aws_api_gateway_rest_api": ServiceCategory.INTEGRATION_API,
        "aws_apigatewayv2_api": ServiceCategory.INTEGRATION_API,
        "aws_sfn_state_machine": ServiceCategory.INTEGRATION_WORKFLOW,
        # AWS Management
        "aws_cloudwatch_log_group": ServiceCategory.MANAGEMENT_LOGGING,
        "aws_cloudwatch_metric_alarm": ServiceCategory.MANAGEMENT_MONITORING,
        "aws_ssm_parameter": ServiceCategory.MANAGEMENT_AUTOMATION,
        "aws_ce_cost_category": ServiceCategory.MANAGEMENT_COST,
        # AWS Application
        "aws_ecr_repository": ServiceCategory.APP_CONTAINER_REGISTRY,
        "aws_codecommit_repository": ServiceCategory.APP_CODE_REPO,
        # Azure Compute
        "azurerm_virtual_machine": ServiceCategory.COMPUTE_VM,
        "azurerm_linux_virtual_machine": ServiceCategory.COMPUTE_VM,
        "azurerm_windows_virtual_machine": ServiceCategory.COMPUTE_VM,
        "azurerm_kubernetes_cluster": ServiceCategory.COMPUTE_CONTAINER,
        "azurerm_container_group": ServiceCategory.COMPUTE_CONTAINER,
        "azurerm_function_app": ServiceCategory.COMPUTE_SERVERLESS,
        "azurerm_batch_pool": ServiceCategory.COMPUTE_BATCH,
        # Azure Network
        "azurerm_virtual_network": ServiceCategory.NETWORK_VPC,
        "azurerm_subnet": ServiceCategory.NETWORK_SUBNET,
        "azurerm_load_balancer": ServiceCategory.NETWORK_LB,
        "azurerm_application_gateway": ServiceCategory.NETWORK_LB,
        "azurerm_virtual_network_gateway": ServiceCategory.NETWORK_GATEWAY,
        "azurerm_cdn_profile": ServiceCategory.NETWORK_CDN,
        "azurerm_dns_zone": ServiceCategory.NETWORK_DNS,
        "azurerm_firewall": ServiceCategory.NETWORK_FIREWALL,
        # Azure Storage
        "azurerm_storage_account": ServiceCategory.STORAGE_OBJECT,
        "azurerm_managed_disk": ServiceCategory.STORAGE_BLOCK,
        "azurerm_storage_share": ServiceCategory.STORAGE_FILE,
        # Azure Database
        "azurerm_mysql_server": ServiceCategory.DATABASE_RELATIONAL,
        "azurerm_postgresql_server": ServiceCategory.DATABASE_RELATIONAL,
        "azurerm_mssql_server": ServiceCategory.DATABASE_RELATIONAL,
        "azurerm_cosmosdb_account": ServiceCategory.DATABASE_NOSQL,
        "azurerm_redis_cache": ServiceCategory.DATABASE_CACHE,
        "azurerm_synapse_workspace": ServiceCategory.DATABASE_DATAWAREHOUSE,
        # Azure Security
        "azurerm_network_security_group": ServiceCategory.SECURITY_FIREWALL,
        "azurerm_role_assignment": ServiceCategory.SECURITY_IAM,
        "azurerm_role_definition": ServiceCategory.SECURITY_IAM,
        "azurerm_key_vault": ServiceCategory.SECURITY_SECRETS,
        "azurerm_key_vault_key": ServiceCategory.SECURITY_KEYS,
        "azurerm_key_vault_certificate": ServiceCategory.SECURITY_CERT,
        # Azure Analytics
        "azurerm_stream_analytics_job": ServiceCategory.ANALYTICS_STREAMING,
        "azurerm_hdinsight_hadoop_cluster": ServiceCategory.ANALYTICS_BATCH,
        "azurerm_powerbi_embedded": ServiceCategory.ANALYTICS_BI,
        "azurerm_data_factory": ServiceCategory.ANALYTICS_ETL,
        # Azure ML/AI
        "azurerm_machine_learning_workspace": ServiceCategory.ML_TRAINING,
        "azurerm_cognitive_account": ServiceCategory.ML_INFERENCE,
        # Azure Integration
        "azurerm_storage_queue": ServiceCategory.INTEGRATION_QUEUE,
        "azurerm_eventgrid_topic": ServiceCategory.INTEGRATION_EVENTBUS,
        "azurerm_api_management": ServiceCategory.INTEGRATION_API,
        "azurerm_logic_app_workflow": ServiceCategory.INTEGRATION_WORKFLOW,
        # Azure Management
        "azurerm_log_analytics_workspace": ServiceCategory.MANAGEMENT_LOGGING,
        "azurerm_monitor_metric_alert": ServiceCategory.MANAGEMENT_MONITORING,
        "azurerm_automation_account": ServiceCategory.MANAGEMENT_AUTOMATION,
        # Azure Application
        "azurerm_container_registry": ServiceCategory.APP_CONTAINER_REGISTRY,
        # GCP Compute
        "google_compute_instance": ServiceCategory.COMPUTE_VM,
        "google_kubernetes_cluster": ServiceCategory.COMPUTE_CONTAINER,
        "google_container_cluster": ServiceCategory.COMPUTE_CONTAINER,
        "google_cloud_run_service": ServiceCategory.COMPUTE_SERVERLESS,
        "google_cloudfunctions_function": ServiceCategory.COMPUTE_SERVERLESS,
        # GCP Network
        "google_compute_network": ServiceCategory.NETWORK_VPC,
        "google_compute_subnetwork": ServiceCategory.NETWORK_SUBNET,
        "google_compute_backend_service": ServiceCategory.NETWORK_LB,
        "google_compute_forwarding_rule": ServiceCategory.NETWORK_LB,
        "google_compute_router": ServiceCategory.NETWORK_GATEWAY,
        "google_compute_router_nat": ServiceCategory.NETWORK_GATEWAY,
        "google_compute_vpn_gateway": ServiceCategory.NETWORK_GATEWAY,
        "google_dns_managed_zone": ServiceCategory.NETWORK_DNS,
        "google_compute_firewall": ServiceCategory.NETWORK_FIREWALL,
        # GCP Storage
        "google_storage_bucket": ServiceCategory.STORAGE_OBJECT,
        "google_compute_disk": ServiceCategory.STORAGE_BLOCK,
        "google_filestore_instance": ServiceCategory.STORAGE_FILE,
        # GCP Database
        "google_sql_database_instance": ServiceCategory.DATABASE_RELATIONAL,
        "google_firestore_database": ServiceCategory.DATABASE_NOSQL,
        "google_bigtable_instance": ServiceCategory.DATABASE_NOSQL,
        "google_redis_instance": ServiceCategory.DATABASE_CACHE,
        "google_bigquery_dataset": ServiceCategory.DATABASE_DATAWAREHOUSE,
        # GCP Security
        "google_project_iam_binding": ServiceCategory.SECURITY_IAM,
        "google_project_iam_member": ServiceCategory.SECURITY_IAM,
        "google_secret_manager_secret": ServiceCategory.SECURITY_SECRETS,
        "google_kms_crypto_key": ServiceCategory.SECURITY_KEYS,
        # GCP Analytics
        "google_pubsub_topic": ServiceCategory.ANALYTICS_STREAMING,
        "google_dataproc_cluster": ServiceCategory.ANALYTICS_BATCH,
        "google_dataflow_job": ServiceCategory.ANALYTICS_ETL,
        # GCP ML/AI
        "google_notebooks_instance": ServiceCategory.ML_NOTEBOOK,
        "google_ml_engine_model": ServiceCategory.ML_INFERENCE,
        # GCP Integration
        "google_cloud_tasks_queue": ServiceCategory.INTEGRATION_QUEUE,
        "google_eventarc_trigger": ServiceCategory.INTEGRATION_EVENTBUS,
        "google_api_gateway_api": ServiceCategory.INTEGRATION_API,
        "google_workflows_workflow": ServiceCategory.INTEGRATION_WORKFLOW,
        # GCP Management
        "google_logging_project_sink": ServiceCategory.MANAGEMENT_LOGGING,
        "google_monitoring_alert_policy": ServiceCategory.MANAGEMENT_MONITORING,
        # GCP Application
        "google_artifact_registry_repository": ServiceCategory.APP_ARTIFACT_REGISTRY,
        "google_container_registry": ServiceCategory.APP_CONTAINER_REGISTRY,
        "google_sourcerepo_repository": ServiceCategory.APP_CODE_REPO,
    }

    @classmethod
    def get_category(cls, resource_type: str) -> ServiceCategory:
        """
        Get canonical category for resource type.

        Args:
            resource_type: Terraform type (e.g., 'aws_instance')

        Returns:
            ServiceCategory enum (defaults to GENERIC if unknown)
        """
        return cls._mappings.get(resource_type, ServiceCategory.GENERIC)

    @classmethod
    def get_resources_by_category(cls, category: ServiceCategory) -> Set[str]:
        """
        Get all resource types in a category.

        Args:
            category: ServiceCategory enum

        Returns:
            Set of resource type strings
        """
        return {rt for rt, cat in cls._mappings.items() if cat == category}

    @classmethod
    def register(cls, resource_type: str, category: ServiceCategory) -> None:
        """
        Register custom resource type mapping.

        Enables plugin extensibility (FR-008).

        Args:
            resource_type: Terraform type
            category: Canonical category
        """
        cls._mappings[resource_type] = category
