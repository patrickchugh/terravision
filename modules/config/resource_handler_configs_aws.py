"""AWS-specific resource handler configurations.

Defines transformation pipelines for AWS resources in a config-driven manner.
Patterns support wildcards via substring matching.
"""

RESOURCE_HANDLER_CONFIGS = {
    "aws_eks_node_group": {
        "description": "Expand EKS node groups to numbered instances per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_eks_node_group",
                    "subnet_key": "subnet_ids",
                    "skip_if_numbered": True,
                },
            },
        ],
    },
    "aws_eks_fargate_profile": {
        "description": "Expand Fargate profiles to numbered instances per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_eks_fargate_profile",
                    "subnet_key": "subnet_ids",
                    "skip_if_numbered": True,
                },
            },
        ],
    },
    "aws_autoscaling_group": {
        "description": "Expand autoscaling groups to numbered instances per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_autoscaling_group",
                    "subnet_key": "vpc_zone_identifier",
                    "skip_if_numbered": True,
                },
            },
        ],
    },
    "random_string": {
        "description": "Remove random string resources",
        "transformations": [
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "random_string.",
                    "remove_from_parents": True,
                },
            },
        ],
    },
    "aws_vpc_endpoint": {
        "description": "Move VPC endpoints into VPC parent and delete endpoint nodes",
        "transformations": [
            {
                "operation": "move_to_parent",
                "params": {
                    "resource_pattern": "aws_vpc_endpoint",
                    "from_parent_pattern": "aws_subnet",
                    "to_parent_pattern": "aws_vpc.",
                },
            },
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "aws_vpc_endpoint",
                    "remove_from_parents": False,
                },
            },
        ],
    },
    "aws_db_subnet_group": {
        "description": "Move DB subnet groups from subnets to VPC, redirect to security groups",
        "transformations": [
            {
                "operation": "move_to_vpc_parent",
                "params": {
                    "resource_pattern": "aws_db_subnet_group",
                },
            },
            {
                "operation": "redirect_to_security_group",
                "params": {
                    "resource_pattern": "aws_db_subnet_group",
                },
            },
        ],
    },
    "aws_": {
        "description": "Group shared AWS services into shared services group",
        "transformations": [
            {
                "operation": "group_shared_services",
                "params": {
                    "service_patterns": [
                        "aws_acm_certificate",
                        "aws_cloudwatch_log_group",
                        "aws_ecr_repository",
                        "aws_efs_file_system",
                        "aws_ssm_parameter",
                        "aws_kms_key",
                        "aws_eip",
                    ],
                    "group_name": "aws_group.shared_services",
                },
            },
        ],
    },
    "aws_cloudfront_distribution": {
        "description": "Connect CloudFront to load balancers and handle origins",
        "transformations": [
            {
                "operation": "link_via_shared_child",
                "params": {
                    "source_pattern": "aws_cloudfront",
                    "target_pattern": "aws_lb",
                    "remove_intermediate": False,
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_cloudfront",
                    "target_resource": "aws_acm_certificate.acm",
                    "metadata_key": "viewer_certificate",
                    "metadata_value_pattern": "acm_certificate_arn",
                },
            },
        ],
        "additional_handler_function": "handle_cf_origins",
    },
    "aws_api_gateway_rest_api": {
        "description": "Config-Only: Link consolidated API Gateway to Lambda via shared lambda_permission connection",
        "transformations": [
            {
                "operation": "link_via_common_connection",
                "params": {
                    "source_pattern": "aws_api_gateway_integration",
                    "target_pattern": "aws_lambda_function",
                    "remove_shared_connection": False,
                },
            },
        ],
    },
    "aws_subnet": {
        "description": "Create availability zone nodes and link to subnets",
        "handler_execution_order": "before",  # Run custom function FIRST to prepare metadata
        "additional_handler_function": "aws_prepare_subnet_az_metadata",
        "transformations": [
            # Insert AZ nodes between VPC and subnet (VPC→subnet becomes VPC→AZ→subnet)
            # This transformer handles both unlinking and relinking in one operation
            {
                "operation": "insert_intermediate_node",
                "params": {
                    "parent_pattern": "aws_vpc",
                    "child_pattern": "aws_subnet",
                    "intermediate_node_generator": "generate_az_node_name",
                    "create_if_missing": True,
                },
            },
        ],
    },
    "aws_lambda_function": {
        "description": "Move Lambda functions from subnets to VPC level to avoid duplication",
        "transformations": [
            {
                "operation": "move_to_vpc_parent",
                "params": {
                    "resource_pattern": "aws_lambda_function",
                },
            },
        ],
    },
    "aws_appautoscaling_target": {
        "description": "Handle autoscaling target relationships and counts",
        # Pure function handler - logic is too specific for generic transformers
        # Handles: 1) Count propagation from subnet to ASG/services
        #          2) Connection redirection (subnet→service becomes subnet→ASG)
        "additional_handler_function": "aws_handle_autoscaling",
    },
    "aws_efs_file_system": {
        "description": "Handle EFS mount targets and file system relationships",
        "transformations": [
            {
                "operation": "bidirectional_link",
                "params": {
                    "source_pattern": "aws_efs_mount_target",
                    "target_pattern": "aws_efs_file_system",
                    "cleanup_reverse": True,
                },
            },
        ],
        "additional_handler_function": "aws_handle_efs",
    },
    "aws_security_group": {
        "description": "Process security group relationships and reverse connections",
        "additional_handler_function": "aws_handle_sg",
    },
    "aws_lb": {
        "description": "Handle load balancer type variants and connections",
        "additional_handler_function": "aws_handle_lb",
    },
    "aws_ecs": {
        "description": "Handle ECS service configurations",
        "additional_handler_function": "aws_handle_ecs",
    },
    "aws_eks": {
        "description": "Handle EKS cluster and node group configurations",
        "additional_handler_function": "aws_handle_eks",
    },
    "helm_release": {
        "description": "Handle helm release resources",
        "additional_handler_function": "helm_release_handler",
    },
    "aws_elasticache_replication_group": {
        "description": "Pure Config-Driven: Expand replication groups to numbered instances per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_elasticache_replication_group",
                    "subnet_key": "subnet_group_name",
                    "skip_if_numbered": True,
                    "inherit_connections": False,
                },
            },
            {
                "operation": "move_to_vpc_parent",
                "params": {
                    "resource_pattern": "aws_elasticache_subnet_group",
                },
            },
            {
                "operation": "redirect_to_security_group",
                "params": {
                    "resource_pattern": "aws_elasticache_subnet_group",
                },
            },
        ],
    },
    "aws_elasticache_cluster": {
        "description": "Pure Config-Driven: Expand ElastiCache clusters to numbered instances per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_elasticache_cluster",
                    "subnet_key": "subnet_group_name",
                    "skip_if_numbered": True,
                    "inherit_connections": False,
                },
            },
        ],
    },
    "aws_wafv2_web_acl": {
        "description": "Hybrid: Link WAF Web ACLs to protected resources via association parsing",
        # Problem: WAF association doesn't create Terraform dependencies
        # Solution: Parse aws_wafv2_web_acl_association to create WAF → ALB/CloudFront connections
        "additional_handler_function": "aws_handle_waf_associations",
    },
    "aws_sagemaker_endpoint": {
        "description": "Config-Only: Delete endpoint_configuration (consolidation via AWS_CONSOLIDATED_NODES)",
        "transformations": [
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "aws_sagemaker_endpoint_configuration",
                    "remove_from_parents": True,
                },
            },
        ],
    },
    "aws_s3_bucket": {
        "description": "Pure Function: Group S3 buckets by region for cross-region replication scenarios",
        "additional_handler_function": "aws_handle_s3_cross_region_grouping",
    },
    "aws_s3_bucket_notification": {
        "description": "Config-Only: Link S3 notifications to targets + create transitive S3 bucket → target links",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_s3_bucket_notification",
                    "target_resource": "aws_lambda_function",
                    "metadata_key": "lambda_function",
                    "metadata_value_pattern": "arn:aws:lambda",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_s3_bucket_notification",
                    "target_resource": "aws_sns_topic",
                    "metadata_key": "topic",
                    "metadata_value_pattern": "arn:aws:sns",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_s3_bucket_notification",
                    "target_resource": "aws_sqs_queue",
                    "metadata_key": "queue",
                    "metadata_value_pattern": "arn:aws:sqs",
                },
            },
            # Create transitive links: S3 bucket → Lambda (via notification intermediate)
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "aws_s3_bucket",
                    "intermediate_pattern": "aws_s3_bucket_notification",
                    "target_pattern": "aws_lambda_function",
                    "remove_intermediate": False,
                },
            },
            # Create transitive links: S3 bucket → SNS (via notification intermediate)
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "aws_s3_bucket",
                    "intermediate_pattern": "aws_s3_bucket_notification",
                    "target_pattern": "aws_sns_topic",
                    "remove_intermediate": False,
                },
            },
            # Create transitive links: S3 bucket → SQS (via notification intermediate)
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "aws_s3_bucket",
                    "intermediate_pattern": "aws_s3_bucket_notification",
                    "target_pattern": "aws_sqs_queue",
                    "remove_intermediate": False,
                },
            },
        ],
    },
    "aws_secretsmanager_secret": {
        "description": "Hybrid: Link Secrets Manager to rotation Lambda functions",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_secretsmanager_secret_rotation",
                    "target_resource": "aws_lambda_function",
                    "metadata_key": "rotation_lambda_arn",
                    "metadata_value_pattern": "function:",
                },
            },
        ],
    },
    "aws_glue_catalog_table": {
        "description": "Hybrid: Link Glue Catalog tables to databases and S3 buckets",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_glue_catalog_table",
                    "target_resource": "aws_s3_bucket",
                    "metadata_key": "storage_descriptor",
                    "metadata_value_pattern": "s3://",
                },
            },
        ],
        "additional_handler_function": "aws_handle_glue_catalog",
    },
    "aws_appsync_graphql_api": {
        "description": "Config-Only: Consolidate AppSync resources + delete resolver nodes (consolidation via AWS_CONSOLIDATED_NODES)",
        "transformations": [
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "aws_appsync_resolver",
                    "remove_from_parents": True,
                },
            },
        ],
    },
    "aws_kinesis_firehose_delivery_stream": {
        "description": "Pure Function: Parse Firehose configuration for S3/Redshift/Elasticsearch destinations",
        # TEMPORARILY COMMENTED OUT FOR FUTURE IMPLEMENTATION
        # "additional_handler_function": "aws_handle_firehose",
    },
    "aws_lambda_event_source_mapping": {
        "description": "Pure Function: Create direct connections from event sources (SQS, Kinesis, DynamoDB) to Lambda functions",
        # Creates transitive links and removes intermediary mapping node
        # Handles multiple event source types (SQS, Kinesis, DynamoDB Streams)
        "additional_handler_function": "aws_handle_lambda_event_source_mapping",
    },
}
