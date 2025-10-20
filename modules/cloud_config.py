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
        "aws_cloudwatch": {
            "resource_name": "aws_cloudwatch_log_group.cloudwatch",
            "import_location": "resource_classes.aws.management",
            "vpc": False,
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
]

# List of Group type nodes and order to draw them in
AWS_GROUP_NODES = [
    "aws_vpc",
    "aws_az",
    "aws_group",
    "aws_appautoscaling_target",
    "aws_subnet",
    "aws_security_group",
    "tv_aws_onprem",
]

# Nodes to be drawn first inside the AWS Cloud but outside any subnets or VPCs
AWS_EDGE_NODES = [
    "aws_route53",
    "aws_cloudfront_distribution",
    "aws_internet_gateway",
    "aws_api_gateway",
    "aws_apigateway",
]

# Nodes outside Cloud boundary
AWS_OUTER_NODES = ["tv_aws_users", "tv_aws_internet"]

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
    "aws_vpc.",
    "aws_subnet.",
    "aws_appautoscaling_target",
    "aws_iam_role.",
    "aws_rds_aurora",
]

# Force certain resources to be a destination connection only - original TF node relationships only
AWS_FORCED_DEST = ["aws_rds", "aws_instance"]

# Force certain resources to be a origin connection only - original TF node relationships only
AWS_FORCED_ORIGIN = ["aws_route53", "aws_cloudfront_distribution"]


AWS_IMPLIED_CONNECTIONS = {
    "certificate_arn": "aws_acm_certificate",
    "container_definitions": "aws_ecr_repository",
}

# List of special resources and handler function name
AWS_SPECIAL_RESOURCES = {
    "aws_cloudfront_distribution": "aws_handle_cloudfront_pregraph",
    "aws_subnet": "aws_handle_subnet_azs",
    "aws_appautoscaling_target": "aws_handle_autoscaling",
    "aws_efs_file_system": "aws_handle_efs",
    "aws_db_subnet": "aws_handle_dbsubnet",
    "aws_security_group": "aws_handle_sg",  # place after db_subnet handler
    "aws_lb": "aws_handle_lb",
    "aws_vpc_endpoint": "aws_handle_vpcendpoints",
    "aws_": "aws_handle_sharedgroup",
    "random_string": "random_string_handler",
}

AWS_SHARED_SERVICES = [
    "aws_acm_certificate",
    "aws_cloudwatch_log_group",
    "aws_ecr_repository",
    "aws_ecs_cluster",
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

AWS_ACRONYMS_LIST = [
    "acm",
    "alb",
    "db",
    "ec2",
    "kms",
    "elb",
    "eip",
    "eks",
    "ecr",
    "nlb",
    "efs",
    "ebs",
    "iam",
    "ip",
    "igw",
    "api",
    "acm",
    "ecs",
    "rds",
    "lb",
    "alb",
    "nlb",
    "nat",
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
