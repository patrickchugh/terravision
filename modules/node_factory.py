"""
NodeFactory for resolving Terraform resource types to Diagrams classes.

This module provides dynamic resource class resolution with a fallback chain:
1. Provider-specific class (e.g., diagrams.aws.compute.EC2)
2. Generic category class (e.g., diagrams.generic.compute.Compute)
3. Blank fallback (diagrams.generic.blank.Blank)
"""

from typing import Any, Optional
from functools import lru_cache
import importlib
import logging

logger = logging.getLogger(__name__)


class NodeFactory:
    """
    Factory for resolving Terraform resource types to Diagrams classes.

    Handles dynamic import of resource_classes modules with fallback logic.
    """

    @staticmethod
    @lru_cache(maxsize=256)
    def resolve(
        provider: str, resource_type: str, category: Optional[str] = None
    ) -> Any:
        """
        Resolve resource type to Diagrams class.

        Args:
            provider: Provider ID (e.g., 'aws', 'azure', 'gcp')
            resource_type: Terraform type (e.g., 'aws_instance')
            category: Optional service category (e.g., 'compute')

        Returns:
            Diagrams resource class (e.g., diagrams.aws.compute.EC2)

        Resolution Strategy:
        1. Try provider-specific class: resource_classes.{provider}.{category}.{ClassName}
        2. Try generic class: resource_classes.generic.{category}.{ClassName}
        3. Fallback: resource_classes.generic.blank.Blank
        """
        # Determine category if not provided
        if category is None:
            try:
                from modules.service_mapping import ServiceMapping

                category_enum = ServiceMapping.get_category(resource_type)
                category = category_enum.value.split(".")[
                    0
                ]  # 'compute.vm' -> 'compute'
            except ImportError:
                # Fallback to generic if service_mapping not available
                category = "generic"

        # Guess class name from resource type
        class_name = NodeFactory._resource_type_to_class_name(resource_type, provider)

        # 1. Try provider-specific class
        provider_module_path = f"resource_classes.{provider}.{category}"
        try:
            module = importlib.import_module(provider_module_path)
            if hasattr(module, class_name):
                return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.debug(
                f"Provider-specific class not found: {provider_module_path}.{class_name} - {e}"
            )

        # 2. Try generic class
        generic_module_path = f"resource_classes.generic.{category}"
        try:
            module = importlib.import_module(generic_module_path)
            # Try specific class name first, then fall back to generic category name
            if hasattr(module, class_name):
                return getattr(module, class_name)
            # Try capitalized category name (e.g., 'Compute', 'Network')
            if category:
                generic_class_name = category.capitalize()
                if hasattr(module, generic_class_name):
                    return getattr(module, generic_class_name)
        except (ImportError, AttributeError) as e:
            logger.debug(
                f"Generic class not found: {generic_module_path}.{class_name} - {e}"
            )

        # 3. Fallback to blank
        try:
            from resource_classes.generic.blank import Blank

            logger.debug(f"Using Blank fallback for {resource_type}")
            return Blank
        except ImportError:
            # Last resort: return a simple class
            logger.warning(
                f"Blank class not found, creating fallback for {resource_type}"
            )
            return type("GenericNode", (), {})

    @staticmethod
    def _resource_type_to_class_name(resource_type: str, provider: str) -> str:
        """
        Convert Terraform resource type to Python class name.

        Args:
            resource_type: Terraform type (e.g., 'aws_instance', 'azurerm_virtual_machine')
            provider: Provider ID (e.g., 'aws', 'azure', 'gcp')

        Returns:
            Python class name (e.g., 'EC2', 'VirtualMachine', 'ComputeInstance')

        Examples:
            'aws_instance' -> 'EC2'  (via mapping)
            'aws_s3_bucket' -> 'S3'
            'azurerm_virtual_machine' -> 'VirtualMachine'
            'google_compute_instance' -> 'ComputeInstance'
        """
        # Hard-coded mappings for common abbreviations
        ABBREV_MAP = {
            # AWS
            "aws_instance": "EC2",
            "aws_s3_bucket": "S3",
            "aws_db_instance": "RDS",
            "aws_lambda_function": "Lambda",
            "aws_dynamodb_table": "DynamoDB",
            "aws_vpc": "VPC",
            "aws_lb": "ELB",
            "aws_elb": "ELB",
            "aws_alb": "ApplicationLoadBalancer",
            "aws_ecs_service": "ECS",
            "aws_ecs_task_definition": "ECS",
            "aws_eks_cluster": "EKS",
            "aws_sqs_queue": "SQS",
            "aws_sns_topic": "SNS",
            "aws_kinesis_stream": "Kinesis",
            "aws_api_gateway_rest_api": "APIGateway",
            "aws_cloudfront_distribution": "CloudFront",
            "aws_route53_zone": "Route53",
            "aws_security_group": "SecurityGroup",
            "aws_iam_role": "IAM",
            "aws_kms_key": "KMS",
            "aws_ecr_repository": "ECR",
            "aws_efs_file_system": "EFS",
            "aws_ebs_volume": "EBS",
            "aws_rds_cluster": "Aurora",
            "aws_elasticache_cluster": "ElastiCache",
            "aws_redshift_cluster": "Redshift",
            "aws_emr_cluster": "EMR",
            "aws_glue_job": "Glue",
            "aws_sagemaker_notebook_instance": "Sagemaker",
            "aws_batch_job_definition": "Batch",
            "aws_sfn_state_machine": "StepFunctions",
            # Azure
            "azurerm_virtual_machine": "VirtualMachine",
            "azurerm_linux_virtual_machine": "VirtualMachine",
            "azurerm_windows_virtual_machine": "VirtualMachine",
            "azurerm_kubernetes_cluster": "AKS",
            "azurerm_container_group": "ContainerInstances",
            "azurerm_function_app": "Functions",
            "azurerm_virtual_network": "VirtualNetwork",
            "azurerm_subnet": "Subnet",
            "azurerm_load_balancer": "LoadBalancer",
            "azurerm_application_gateway": "ApplicationGateway",
            "azurerm_storage_account": "StorageAccounts",
            "azurerm_managed_disk": "ManagedDisks",
            "azurerm_sql_server": "SQLServer",
            "azurerm_cosmosdb_account": "CosmosDB",
            "azurerm_redis_cache": "RedisCache",
            "azurerm_container_registry": "ContainerRegistry",
            "azurerm_key_vault": "KeyVault",
            # GCP
            "google_compute_instance": "ComputeEngine",
            "google_kubernetes_cluster": "GKE",
            "google_cloud_run_service": "CloudRun",
            "google_cloudfunctions_function": "CloudFunctions",
            "google_compute_network": "VPC",
            "google_compute_subnetwork": "Subnetwork",
            "google_compute_backend_service": "LoadBalancing",
            "google_storage_bucket": "GCS",
            "google_sql_database_instance": "CloudSQL",
            "google_bigquery_dataset": "BigQuery",
            "google_pubsub_topic": "PubSub",
            "google_container_registry": "GCR",
            "google_secret_manager_secret": "SecretManager",
        }

        if resource_type in ABBREV_MAP:
            return ABBREV_MAP[resource_type]

        # Generic conversion: strip provider prefix, PascalCase
        # 'azurerm_network_security_group' -> 'NetworkSecurityGroup'
        # 'google_compute_firewall' -> 'ComputeFirewall'
        provider_prefixes = {
            "aws": ["aws_"],
            "azure": ["azurerm_", "azuread_"],
            "azurerm": ["azurerm_", "azuread_"],
            "gcp": ["google_"],
            "google": ["google_"],
        }

        # Strip provider prefix
        parts = resource_type
        for prefix in provider_prefixes.get(provider, []):
            if parts.startswith(prefix):
                parts = parts[len(prefix) :]
                break

        # Convert to PascalCase
        words = parts.split("_")
        return "".join(word.capitalize() for word in words)

    @staticmethod
    def clear_cache():
        """Clear the LRU cache (useful for testing)"""
        NodeFactory.resolve.cache_clear()
