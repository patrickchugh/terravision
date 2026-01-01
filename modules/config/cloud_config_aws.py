# AWS Cloud Configuration for TerraVision
# Provider: Amazon Web Services (aws provider)
# Architecture: VPC > Availability Zones > Subnets > Resources

from modules.config.resource_handler_configs_aws import RESOURCE_HANDLER_CONFIGS


# Provider metadata
PROVIDER_NAME = "AWS"
PROVIDER_PREFIX = ["aws_"]
ICON_LIBRARY = "aws"

# Any resource names with certain prefixes are consolidated into one node
AWS_CONSOLIDATED_NODES = [
    {
        "aws_route53": {
            "resource_name": "aws_route53_record.route_53",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_cloudwatch_log": {
            "resource_name": "aws_cloudwatch_log_group.cloudwatch",
            "import_location": "resource_classes.aws.management",
            "vpc": False,
        }
    },
    {
        "aws_cloudwatch_event": {
            "resource_name": "aws_cloudwatch_event_rule.eventbridge",
            "import_location": "resource_classes.aws.integration",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_sns_topic": {
            "resource_name": "aws_sns_topic.sns",
            "import_location": "resource_classes.aws.integration",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_api_gateway": {
            "resource_name": "aws_api_gateway_integration.gateway",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
        }
    },
    {
        "aws_acm": {
            "resource_name": "aws_acm_certificate.acm",
            "import_location": "resource_classes.aws.security",
            "vpc": False,
        }
    },
    {
        "aws_ssm_parameter": {
            "resource_name": "aws_ssm_parameter.ssmparam",
            "import_location": "resource_classes.aws.management",
            "vpc": False,
        }
    },
    {
        "aws_dx": {
            "resource_name": "aws_dx_connection.directconnect",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_lb": {
            "resource_name": "aws_lb.elb",
            "import_location": "resource_classes.aws.network",
            "vpc": True,
        }
    },
    {
        "aws_ecs": {
            "resource_name": "aws_ecs_service.ecs",
            "import_location": "resource_classes.aws.compute",
            "vpc": True,
        }
    },
    {
        "aws_internet_gateway": {
            "resource_name": "aws_internet_gateway.igw",
            "import_location": "resource_classes.aws.network",
            "vpc": True,
        }
    },
    {
        "aws_efs_file_system": {
            "resource_name": "aws_efs_file_system.efs",
            "import_location": "resource_classes.aws.storage",
            "vpc": False,
        }
    },
    {
        "aws_kms": {
            "resource_name": "aws_kms_key.kms",
            "import_location": "resource_classes.aws.kms",
            "vpc": False,
        }
    },
    {
        "aws_eip": {
            "resource_name": "aws_eip.elastic_ip",
            "import_location": "resource_classes.eip.eip",
            "vpc": False,
        }
    },
    {
        "aws_autoscaling_policy": {
            "resource_name": "aws_autoscaling_policy.autoscaling_policy",
            "import_location": "resource_classes.aws.compute",
            "vpc": True,
        }
    },
    {
        "aws_sagemaker_endpoint": {
            "resource_name": "aws_sagemaker_endpoint.endpoint",
            "import_location": "resource_classes.aws.ml",
            "vpc": False,
        }
    },
    {
        "aws_appsync_graphql_api": {
            "resource_name": "aws_appsync_graphql_api.graphql_api",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_cognito": {
            "resource_name": "aws_cognito_user_pool.cognito",
            "import_location": "resource_classes.aws.security",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_wafv2": {
            "resource_name": "aws_wafv2_web_acl.waf",
            "import_location": "resource_classes.aws.security",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_waf": {
            "resource_name": "aws_waf_web_acl.waf",
            "import_location": "resource_classes.aws.security",
            "vpc": False,
            "edge_service": True,
        }
    },
]

# List of Group type nodes and order to draw them in
AWS_GROUP_NODES = [
    "aws_vpc",
    "aws_az",
    "aws_group",
    "aws_account",
    "aws_appautoscaling_target",
    "aws_autoscaling_group",
    "aws_subnet",
    "aws_security_group",
    "tv_aws_onprem",
    "tv_aws_region",
]

# Nodes to be drawn first inside the AWS Cloud but outside any subnets or VPCs
AWS_EDGE_NODES = [
    "aws_route53",
    "aws_cloudfront_distribution",
    "aws_internet_gateway",
    "aws_api_gateway",
    "aws_apigateway",
    "aws_cloudwatch_event",
    "aws_sns_topic",
    "aws_cognito",
    "aws_wafv2",
    "aws_waf",
    "aws_appsync",
]

# Nodes outside Cloud boundary
AWS_OUTER_NODES = [
    "tv_aws_users",
    "tv_aws_internet",
    "tv_aws_device",
    "tv_aws_onprem",
    "tv_aws_mobile_client",
]

# Order to draw nodes - leave empty string list till last to denote everything else
AWS_DRAW_ORDER = [
    AWS_OUTER_NODES,
    AWS_EDGE_NODES,
    AWS_GROUP_NODES,
    AWS_CONSOLIDATED_NODES,
    [""],
]

# List of prefixes where additional nodes should be created automatically
AWS_AUTO_ANNOTATIONS = [
    {"aws_route53": {"link": ["tv_aws_users.users"], "arrow": "reverse"}},
    {
        "aws_cloudfront_distribution": {
            "link": ["tv_aws_users.users"],
            "arrow": "reverse",
        }
    },
    {
        "aws_dx": {
            "link": [
                "tv_aws_onprem.corporate_datacenter",
                "tv_aws_cgw.customer_gateway",
            ],
            "arrow": "forward",
        }
    },
    {
        "aws_internet_gateway": {
            "link": ["tv_aws_internet.internet"],
            "delete": ["aws_nat_gateway."],
            "arrow": "forward",
        }
    },
    {"aws_eks_cluster": {"link": ["aws_eks_service.eks"], "arrow": "reverse"}},
    {"aws_nat_gateway": {"link": ["aws_internet_gateway.*"], "arrow": "forward"}},
    {"aws_ecs_service": {"link": ["aws_ecr_repository.ecr"], "arrow": "forward"}},
    {"aws_eks_cluster": {"link": ["aws_ecr_repository.ecr"], "arrow": "forward"}},
    {"aws_api_gateway": {"link": ["tv_aws_mobile_client.mobile"], "arrow": "reverse"}},
    {"aws_ecs_": {"link": ["aws_ecs_cluster.ecs"], "arrow": "forward"}},
    {
        "aws_lambda": {
            "link": ["aws_cloudwatch_log_group.cloudwatch"],
            "arrow": "forward",
        }
    },
]

# Variant icons for the same service - matches keyword in meta data and changes resource type
AWS_NODE_VARIANTS = {
    "aws_ecs_service": {"FARGATE": "aws_fargate", "EC2": "aws_ec2ecs"},
    "aws_eks_cluster": {"compute_config": "aws_eks_cluster_auto"},
    "aws_lb": {"application": "aws_alb", "network": "aws_nlb"},
    "aws_rds": {
        "aurora": "aws_rds_aurora",
        "mysql": "aws_rds_mysql",
        "postgres": "aws_rds_postgres",
    },
}

# Automatically reverse arrow direction for these resources when discovered through source
AWS_REVERSE_ARROW_LIST = [
    "aws_route53",
    "aws_cloudfront",
    "aws_cloudwatch_event",  # EventBridge emits events TO Lambda (reverse direction)
    "aws_sfn_state_machine",  # Step Functions orchestrates services (reverse direction)
    "aws_vpc.",
    "aws_subnet.",
    "aws_appautoscaling_target",
    "aws_iam_role.",
    "aws_rds_aurora",
]

# Force certain resources to be a destination connection only - original TF node relationships only
AWS_FORCED_DEST = ["aws_rds", "aws_instance", "aws_elasticache"]

# Force certain resources to be a origin connection only - original TF node relationships only
AWS_FORCED_ORIGIN = [
    "aws_route53",
    "aws_cloudfront_distribution",
    "aws_cloudwatch_event",  # EventBridge emits events (source only, not destination)
    "aws_sns_topic",  # SNS emits messages to subscribers (source only, not destination)
    "aws_sfn_state_machine",  # Step Functions orchestrates services (source only, not destination)
    "aws_s3_bucket_notification",  # S3 notifications trigger services (source only, not destination)
    "aws_wafv2_web_acl",  # WAF protects resources (source only, not destination)
    "aws_waf_web_acl",  # WAF Classic protects resources (source only, not destination)
]


AWS_IMPLIED_CONNECTIONS = {
    "certificate_arn": "aws_acm_certificate",
    "container_definitions": "aws_ecr_repository",
}

# Generate AWS_SPECIAL_RESOURCES from RESOURCE_HANDLER_CONFIGS for backward compatibility with older functions
# Include any resource pattern that has transformations or additional handlers
AWS_SPECIAL_RESOURCES = {
    pattern: config.get("additional_handler_function", f"config_handler_{pattern}")
    for pattern, config in RESOURCE_HANDLER_CONFIGS.items()
}

AWS_SHARED_SERVICES = [
    "aws_acm_certificate",
    "aws_cloudwatch_log_group",
    "aws_ecr_repository",
    "aws_efs_file_system",
    "aws_ssm_parameter",
    "aws_kms_key",
    "aws_eip",
]

AWS_ALWAYS_DRAW_LINE = [
    "aws_lb",
    "aws_iam_role",
    "aws_volume_attachment",
    "aws_alb",
    "aws_nlb",
    "aws_efs_mount_target",
    "aws_ecs_service",
    "aws_rds_aurora",
    "aws_rds_mysql",
    "aws_rds_postgres",
]
# Resources that should never have lines drawn between them
AWS_NEVER_DRAW_LINE = []

# Resources that should be disconnected
AWS_DISCONNECT_LIST = []

# Resources that should be hidden from the diagram by default
AWS_HIDE_NODES = ["aws_security_group_rule"]

# Resources that should skip automatic expansion in handle_singular_references
# These resources are manually matched to subnets by suffix in their handlers
AWS_SKIP_SINGULAR_EXPANSION = [
    "aws_eks_fargate_profile",
    "aws_eks_node_group",
]

AWS_ACRONYMS_LIST = [
    "acm",
    "acm",
    "alb",
    "api",
    "db",
    "dx",
    "ebs",
    "ec2",
    "ecr",
    "ecs",
    "efs",
    "eip",
    "eks",
    "elb",
    "etl",
    "igw",
    "iam",
    "ip",
    "kms",
    "lb",
    "nat",
    "nlb",
    "rds",
    "s3",
    "sns",
    "sqs",
    "vpc",
]

AWS_NAME_REPLACEMENTS = {
    "az": "Availability Zone",
    "alb": "App Load Balancer",
    "appautoscaling_target": "Auto Scaling",
    "route_table_association": "Route Table",
    "ecs_service_fargate": "Fargate",
    "eip": "Elastic IP",
    "instance": "EC2",
    "lambda_function": "Lambda",
    "iam_role": "Role",
    "dx": "Direct Connect",
    "cloudfront_distribution": "Cloudfront",
    "iam_policy": "policy",
    "this": "",
}


AWS_REFINEMENT_PROMPT = """
You are an expert AWS Solutions Architect. I have a JSON representation of an AWS architecture diagram generated from Terraform code. The diagram may have incorrect resource groupings, missing connections, or layout issues.
INPUT JSON FORMAT: Each key is a Terraform resource ID, and its value is a list of resource IDs it connects to.
SPECIAL CONVENTIONS:
- Resources starting with "tv_" are visual helper nodes (e.g., "tv_aws_internet.internet" represents the public internet)
- Groups like VPCs, Subnets, Autoscaling, Security Groups etc are always parents and a connection to a resource means the resource is inside that group. However, if a resource inside a group is not also a group type, it should have no connections back to the group nodes
- "aws_az.availability_zone_*" groups represent availability zone boundaries
- Security Groups should always be a group containing EC2 instances or other resources within a subnet
- Resources ending with ~1, ~2, ~3 (instance number) indicate they're either multiple instances of the same resource, or one resource duplicated for clarity when a resource is deployed in multiple availability zones and subnets
- aws_group.shared_services is used to group common shared resources which are accessed by multiple resources such as CloudWatch, ECR, KMS and do not have any incoming or outgoing connections 
Please refine this diagram following AWS conventions and industry best practices:
1. Fix resource groupings (VPCs, subnets, availability zones, security groups) where necessary
2. Add missing logical connections between resources
3. Remove incorrect connections
4. Ensure proper hierarchy (Region > VPC > AZ > Subnet > Resources)
5. Group related resources (e.g., ALB with target groups, Autoscaling resources in an AutoScaling Group, EKS nodes within a subnet)
6. Group type resources like aws_group, aws_appautoscaling_targ, aws_subnet, aws_security_group and tv_aws_oprem are always the parent and other non group resources should be children without connections back to the group
7. Add implied connections (e.g., Lambda in VPC needs ENI connection, ECS or EKS will connect to an ECR repository node)
8. Autoscaling targets should appear as group type nodes within their relevant subnet with the same instance number
9. NAT Gateways in a public subnet should be duplicated with incremental instance numbers in all public subnets to show multi-AZ deployment
10. EKS Cluster worker nodes should be inside subnet groups

"""


AWS_DOCUMENTATION_PROMPT = """\
You are an AWS architect that needs to summarise this JSON of Terraform AWS resources and their associations concisely in paragraph form using as few bullet points as possible. Follow these instructions:
1. If you see ~1, ~2, ~3 etc at the end of the resource name it means multiple instances of the same resource are created. Include how many of each resource type are created in the summary. 
2. Use only AWS resource names in the text which can be inferred from terraform resource type names. e.g. instead of aws_ec2_instance.XXX just say an EC2 Instance named XXX
3. Mention which resources are associated with each respective subnet and availability zone if any. 
4. Provide an overall summary of the architecture and what the system does

"""

# Configuration patterns for multi-instance resource detection
# Each pattern defines:
# - resource_types: List of Terraform resource types to check
# - trigger_attributes: Attributes that trigger expansion (e.g., "subnets", "zones")
# - also_expand_attributes: Attributes containing related resources to also expand
# - resource_pattern: Regex pattern to extract resource references from attribute values
AWS_MULTI_INSTANCE_PATTERNS = [
    {
        "resource_types": ["aws_lb", "aws_alb", "aws_nlb"],
        "trigger_attributes": ["subnets"],
        "also_expand_attributes": ["security_groups"],
        "resource_pattern": r"\$\{(aws_\w+\.\w+)",
        "description": "ALB/NLB spanning multiple subnets",
    },
    {
        "resource_types": ["aws_ecs_service"],
        "trigger_attributes": ["subnets"],
        "also_expand_attributes": ["security_groups"],
        "resource_pattern": r"\$\{(aws_\w+\.\w+)",
        "description": "ECS service spanning multiple subnets",
    },
    # Add more AWS patterns as needed
]

# Replace with your OLLAMA server IP and port number
OLLAMA_HOST = "http://localhost:11434"

# Replace with your actual API Gateway endpoint from: terraform output api_endpoint
BEDROCK_API_ENDPOINT = (
    "https://yirz70b5mc.execute-api.us-east-1.amazonaws.com/prod/chat"
)
