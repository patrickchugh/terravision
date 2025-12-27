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
}
