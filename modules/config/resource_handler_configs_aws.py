"""AWS-specific resource handler configurations.

Defines transformation pipelines for AWS resources.
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
    # ============================================================================
    # Feature 002: AWS Handler Refinement - Top 80% Common Patterns
    # ============================================================================
    # Pure Config-Driven Handler (1/14)
    "aws_elasticache_replication_group": {
        "description": "Pure Config-Driven: Link ElastiCache to subnet groups (consolidation via AWS_CONSOLIDATED_NODES)",
        "transformations": [
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
    # Hybrid Handlers (11/14)
    # REMOVED: API Gateway handlers don't add value since integration URIs aren't resolved in terraform plan
    # The baseline already shows Lambda → Integration connections via Terraform dependencies
    # "aws_api_gateway_rest_api": {
    #     "description": "Clean up API Gateway deployments/stages (consolidation via AWS_CONSOLIDATED_NODES)",
    #     "transformations": [
    #         {
    #             "operation": "delete_nodes",
    #             "params": {
    #                 "resource_pattern": "aws_api_gateway_stage",
    #                 "remove_from_parents": True,
    #             },
    #         },
    #         {
    #             "operation": "delete_nodes",
    #             "params": {
    #                 "resource_pattern": "aws_api_gateway_deployment",
    #                 "remove_from_parents": True,
    #             },
    #         },
    #     ],
    # },
    # REMOVED: API Gateway v2 handler - same issue as REST API (URIs not resolved in terraform plan)
    # "aws_apigatewayv2_api": {
    #     "description": "Clean up API Gateway v2 stages (consolidation via AWS_CONSOLIDATED_NODES)",
    #     "transformations": [
    #         {
    #             "operation": "delete_nodes",
    #             "params": {
    #                 "resource_pattern": "aws_apigatewayv2_stage",
    #                 "remove_from_parents": True,
    #             },
    #         },
    #     ],
    # },
    "aws_cloudwatch_event_rule": {
        "description": "Hybrid: Link EventBridge rules to targets (Lambda, SNS, SQS, Step Functions)",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_cloudwatch_event_target",
                    "target_pattern": "aws_lambda_function",
                    "metadata_key": "arn",
                    "metadata_value_pattern": "function:",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_cloudwatch_event_target",
                    "target_pattern": "aws_sns_topic",
                    "metadata_key": "arn",
                    "metadata_value_pattern": "sns:",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_cloudwatch_event_target",
                    "target_pattern": "aws_sqs_queue",
                    "metadata_key": "arn",
                    "metadata_value_pattern": "sqs:",
                },
            },
        ],
        "additional_handler_function": "aws_handle_eventbridge_targets",
    },
    "aws_sns_topic": {
        "description": "Hybrid: Link SNS topics to subscriptions (Lambda, SQS, email, HTTP)",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_sns_topic_subscription",
                    "target_pattern": "aws_lambda_function",
                    "metadata_key": "endpoint",
                    "metadata_value_pattern": "function:",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_sns_topic_subscription",
                    "target_pattern": "aws_sqs_queue",
                    "metadata_key": "endpoint",
                    "metadata_value_pattern": "sqs:",
                },
            },
        ],
        "additional_handler_function": "aws_handle_sns_subscriptions",
    },
    "aws_lambda_event_source_mapping": {
        "description": "Hybrid: Link Lambda ESM to DynamoDB Streams, Kinesis, SQS",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_lambda_event_source_mapping",
                    "target_pattern": "aws_dynamodb_table",
                    "metadata_key": "event_source_arn",
                    "metadata_value_pattern": "dynamodb:",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_lambda_event_source_mapping",
                    "target_pattern": "aws_kinesis_stream",
                    "metadata_key": "event_source_arn",
                    "metadata_value_pattern": "kinesis:",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_lambda_event_source_mapping",
                    "target_pattern": "aws_sqs_queue",
                    "metadata_key": "event_source_arn",
                    "metadata_value_pattern": "sqs:",
                },
            },
        ],
        "additional_handler_function": "aws_handle_lambda_esm",
    },
    "aws_cognito_user_pool": {
        "description": "Hybrid: Link Cognito User Pools to Lambda triggers and App Clients",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_cognito_user_pool",
                    "target_pattern": "aws_lambda_function",
                    "metadata_key": "lambda_config",
                    "metadata_value_pattern": "arn:aws:lambda",
                },
            },
        ],
        "additional_handler_function": "aws_handle_cognito_triggers",
    },
    "aws_wafv2_web_acl": {
        "description": "Hybrid: Link WAF Web ACLs to protected resources (ALB, CloudFront, API Gateway)",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_wafv2_web_acl_association",
                    "target_pattern": "aws_lb",
                    "metadata_key": "resource_arn",
                    "metadata_value_pattern": "loadbalancer",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_wafv2_web_acl_association",
                    "target_pattern": "aws_cloudfront_distribution",
                    "metadata_key": "resource_arn",
                    "metadata_value_pattern": "distribution",
                },
            },
        ],
        "additional_handler_function": "aws_handle_waf_associations",
    },
    "aws_sagemaker_endpoint": {
        "description": "Hybrid: Link SageMaker endpoints to models (consolidation via AWS_CONSOLIDATED_NODES)",
        "transformations": [
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "aws_sagemaker_endpoint_configuration",
                    "remove_from_parents": True,
                },
            },
        ],
        "additional_handler_function": "aws_handle_sagemaker_models",
    },
    "aws_s3_bucket_notification": {
        "description": "Hybrid: Link S3 bucket notifications to Lambda, SNS, SQS",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_s3_bucket_notification",
                    "target_pattern": "aws_lambda_function",
                    "metadata_key": "lambda_function",
                    "metadata_value_pattern": "arn:aws:lambda",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_s3_bucket_notification",
                    "target_pattern": "aws_sns_topic",
                    "metadata_key": "topic",
                    "metadata_value_pattern": "arn:aws:sns",
                },
            },
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_s3_bucket_notification",
                    "target_pattern": "aws_sqs_queue",
                    "metadata_key": "queue",
                    "metadata_value_pattern": "arn:aws:sqs",
                },
            },
        ],
        "additional_handler_function": "aws_handle_s3_notifications",
    },
    "aws_secretsmanager_secret": {
        "description": "Hybrid: Link Secrets Manager to rotation Lambda functions",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_secretsmanager_secret_rotation",
                    "target_pattern": "aws_lambda_function",
                    "metadata_key": "rotation_lambda_arn",
                    "metadata_value_pattern": "function:",
                },
            },
        ],
        "additional_handler_function": "aws_handle_secrets_manager",
    },
    "aws_glue_catalog_table": {
        "description": "Hybrid: Link Glue Catalog tables to databases and S3 buckets",
        "transformations": [
            {
                "operation": "link_by_metadata_pattern",
                "params": {
                    "source_pattern": "aws_glue_catalog_table",
                    "target_pattern": "aws_s3_bucket",
                    "metadata_key": "storage_descriptor",
                    "metadata_value_pattern": "s3://",
                },
            },
        ],
        "additional_handler_function": "aws_handle_glue_catalog",
    },
    "aws_appsync_graphql_api": {
        "description": "Hybrid: Link AppSync APIs to data sources (consolidation via AWS_CONSOLIDATED_NODES)",
        "transformations": [
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "aws_appsync_resolver",
                    "remove_from_parents": True,
                },
            },
        ],
        "additional_handler_function": "aws_handle_appsync_datasources",
    },
    # Pure Function Handlers (2/14)
    "aws_sfn_state_machine": {
        "description": "Pure Function: Parse state machine ASL JSON to extract Lambda/service invocations",
        # Complex conditional logic for ASL parsing, state traversal, and selective linking
        # Cannot be expressed with generic transformers due to nested JSON parsing
        "additional_handler_function": "aws_handle_step_functions",
    },
    "aws_kinesis_firehose_delivery_stream": {
        "description": "Pure Function: Parse Firehose configuration for S3/Redshift/Elasticsearch destinations",
        # Domain-specific parsing of complex nested configuration blocks
        # Multiple conditional branches based on destination type
        "additional_handler_function": "aws_handle_firehose",
    },
}
