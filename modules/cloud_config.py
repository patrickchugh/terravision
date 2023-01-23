
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
        "aws_lb_": {
            "resource_name": "aws_lb_target_group.elb",
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
        "aws_rds": {
            "resource_name": "aws_rds_cluster.rds",
            "import_location": "resource_classes.aws.database",
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
        "aws_eip": {
            "resource_name": "aws_eip.eip",
            "import_location": "resource_classes.aws.network",
            "vpc": True,
        }
    },
   
]

# List of Group type nodes and order to draw them in
AWS_GROUP_NODES = [
    "aws_vpc",
    "aws_appautoscaling_target",
    "aws_subnet",
    "aws_security_group",
    "tv_aws_onprem"
]

# Nodes to be drawn first inside the AWS Cloud but outside any subnets or VPCs
AWS_EDGE_NODES = [
    "aws_route53",
    "aws_cloudfront_distribution",
    "aws_internet_gateway"
    "aws_api_gateway",
    "aws_apigateway"
]

# Nodes outside Cloud
AWS_OUTER_NODES = [
    "tv_aws_users",
    "tv_aws_internet"    
]

# Order to draw nodes - leave empthy string list till last to denote everything else
AWS_DRAW_ORDER = [AWS_OUTER_NODES, AWS_EDGE_NODES, AWS_GROUP_NODES, AWS_CONSOLIDATED_NODES, [""]]

# List of prefixes where additional nodes should be created automatically
AWS_AUTO_ANNOTATIONS = [
    {"aws_route53": {"link": ["tv_aws_users.users"], "arrow": "reverse"}},
    {"aws_dx": {"link": ["tv_aws_onprem.corporate_datacenter", "tv_aws_cgw.customer_gateway"], "arrow": "forward"}},
    {"aws_internet_gateway": {"link": ["tv_aws_internet.internet"], "arrow": "forward"}},
    {"aws_nat_gateway": {"link": ["aws_internet_gateway.*"], "arrow": "forward"}},
]

# Variant icons for the same service - matches keyword in meta data to suffix after underscore
AWS_NODE_VARIANTS = {"aws_ecs": {"FARGATE": "aws_fargate_ecs", "EC2": "aws_ec2_ecs"}}

# Automatically reverse arrow direction for these resources
AWS_REVERSE_ARROW_LIST = [
    'aws_route53',
    'aws_cloudfront',
    'aws_vpc.',
    'aws_subnet.',
    'aws_iam_role.',
    'aws_lb',
]

AWS_IMPLIED_CONNECTIONS = {'certificate_arn': 'aws_acm_certificate'}