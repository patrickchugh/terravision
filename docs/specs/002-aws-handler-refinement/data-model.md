# Data Model: AWS Handler Refinement

**Branch**: `002-aws-handler-refinement` | **Date**: 2025-12-26

## Overview

This document defines the data structures and entity relationships for the AWS resource handler enhancements. The handlers work with TerraVision's existing data structures (`tfdata`, `graphdict`, `meta_data`).

---

## Core Data Structures

### tfdata (Input/Output)

The main data dictionary passed through all handlers:

```python
tfdata = {
    "graphdict": dict,           # Resource connections: {resource_name: [connected_resources]}
    "meta_data": dict,           # Resource attributes: {resource_name: {attribute: value}}
    "original_metadata": dict,   # Unmodified metadata from Terraform
    "node_list": list,           # All resource names
    "hidden": list,              # Resources to hide from diagram
    "all_resource": dict,        # Full resource definitions from Terraform
    "provider_detection": dict,  # Detected cloud providers
}
```

### graphdict (Graph Structure)

Directed graph representing resource connections:

```python
graphdict = {
    "aws_vpc.main": ["aws_subnet.public", "aws_subnet.private"],
    "aws_subnet.public": ["aws_instance.web"],
    "aws_instance.web": ["aws_security_group.web_sg"],
    # ... resource → [children]
}
```

### meta_data (Resource Attributes)

Resource metadata for diagram rendering:

```python
meta_data = {
    "aws_instance.web": {
        "id": "aws_instance.web",
        "count": 2,
        "instance_type": "t3.micro",
        "availability_zone": "us-east-1a",
        # ... Terraform attributes
    }
}
```

---

## New Entity Definitions by Pattern

### API Gateway Entities

#### aws_api_gateway.api (Consolidated Node)

Represents consolidated REST/HTTP API:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Consolidated node identifier |
| api_type | string | "REST" or "HTTP" |
| integrations | list | Backend integration targets |
| stages | int | Number of stages consolidated |
| count | int | Node instance count |

#### aws_apigatewayv2_vpc_link

VPC Link for private integrations:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | VPC Link resource name |
| target_arns | list | NLB/ALB ARNs |
| subnet_ids | list | VPC subnets |

#### aws_external_integration.placeholder

Placeholder for undefined integrations:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | "aws_external_integration.external" |
| label | string | "External Integration" |

---

### Event-Driven Entities

#### aws_cloudwatch_event_rule

EventBridge rule:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Rule resource name |
| event_pattern | dict | Event matching pattern |
| schedule_expression | string | Cron/rate expression |
| targets | list | Target resource ARNs |

#### aws_sns_topic

SNS topic:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Topic resource name |
| subscriptions | list | Subscription endpoints |
| protocols | list | ["lambda", "sqs", "email", etc.] |

#### aws_sqs_queue

SQS queue:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Queue resource name |
| visibility_timeout | int | Message visibility timeout |
| redrive_policy | dict | DLQ configuration |

#### aws_lambda_event_source_mapping

Lambda event source:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | ESM resource name |
| event_source_arn | string | Source ARN (SQS/Kinesis/DynamoDB) |
| function_name | string | Lambda function reference |
| batch_size | int | Event batch size |

---

### Caching Entities

#### aws_elasticache_cluster

Cache cluster node:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Cluster resource name |
| engine | string | "redis" or "memcached" |
| node_type | string | Instance type |
| num_cache_nodes | int | Number of nodes |
| availability_zone | string | AZ placement |

#### aws_elasticache_replication_group

Redis replication group:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Replication group name |
| num_node_groups | int | Shard count |
| replicas_per_node_group | int | Replicas per shard |
| subnet_ids | list | Subnet placement |

---

### Authentication Entities

#### aws_cognito.auth (Consolidated Node)

Consolidated Cognito resources:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | "aws_cognito.auth" |
| user_pool | string | User pool ARN |
| identity_pool | string | Identity pool ARN (optional) |
| lambda_triggers | list | Trigger function references |
| app_clients | int | Number of app clients |

---

### Security Entities

#### aws_waf.firewall (Consolidated Node)

WAF Web ACL:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | "aws_waf.firewall" |
| associated_resources | list | Protected resource ARNs |
| rules_count | int | Number of rules |

---

### Machine Learning Entities

#### aws_sagemaker.ml (Consolidated Node)

SageMaker endpoint group:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | "aws_sagemaker.ml" |
| endpoint | string | Endpoint resource |
| model | string | Model resource |
| s3_artifacts | list | S3 bucket references |

#### aws_sagemaker_notebook_instance

Notebook instance (VPC-placed):

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Notebook resource name |
| subnet_id | string | VPC subnet |
| security_group_ids | list | Security groups |
| instance_type | string | Instance type |

---

### Workflow Entities

#### aws_sfn_state_machine

Step Functions state machine:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | State machine resource |
| definition | dict | State machine definition (parsed) |
| integrated_services | list | Detected service integrations |

---

### Data Processing Entities

#### aws_glue_job

Glue ETL job:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Job resource name |
| script_location | string | S3 script path |
| s3_sources | list | Input S3 paths |
| s3_targets | list | Output S3 paths |

#### aws_kinesis_firehose_delivery_stream

Firehose delivery stream:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | Stream resource name |
| destination | string | "s3", "redshift", "elasticsearch" |
| s3_bucket | string | Destination bucket |
| lambda_processor | string | Transformation Lambda (optional) |

---

### GraphQL Entities

#### aws_appsync.api (Consolidated Node)

AppSync GraphQL API:

| Attribute | Type | Description |
|-----------|------|-------------|
| id | string | "aws_appsync.api" |
| authentication_type | string | "COGNITO", "API_KEY", etc. |
| data_sources | list | DynamoDB/Lambda data sources |

---

## Relationship Mappings

### Connection Patterns

| Source | Target | Relationship | Arrow Direction |
|--------|--------|--------------|-----------------|
| API Gateway | Lambda | integration | → |
| API Gateway | Step Functions | integration | → |
| API Gateway | VPC Link | private_integration | → |
| VPC Link | ALB/NLB | target | → |
| EventBridge | Lambda | target | → |
| EventBridge | Step Functions | target | → |
| SNS | SQS | subscription | → |
| SNS | Lambda | subscription | → |
| SQS | Lambda | event_source | → |
| DynamoDB | Lambda | stream | → |
| Kinesis | Lambda | event_source | → |
| S3 | Lambda | notification | → |
| S3 | SQS | notification | → |
| Cognito | Lambda | trigger | → |
| Cognito | API Gateway | authorizer | → |
| WAF | CloudFront | association | → (in front of) |
| WAF | ALB | association | → (in front of) |
| Lambda | SageMaker | invoke | → |
| Step Functions | Lambda | task | → |
| Step Functions | ECS | task | → |
| Glue | S3 | read/write | ↔ |
| Athena | S3 | query | → |
| AppSync | DynamoDB | data_source | → |
| AppSync | Lambda | resolver | → |

### Containment Hierarchy

```
AWS Cloud
├── Edge Services (outside VPC)
│   ├── Route53
│   ├── CloudFront
│   ├── API Gateway
│   ├── AppSync
│   ├── Cognito
│   └── WAF
├── VPC
│   ├── Availability Zone
│   │   ├── Subnet
│   │   │   ├── Security Group
│   │   │   │   └── Resources (EC2, RDS, ElastiCache, etc.)
│   │   │   └── ECS/EKS Services
│   │   └── SageMaker Notebook (when VPC-configured)
│   └── ...
└── Shared Services (outside VPC)
    ├── CloudWatch
    ├── KMS
    ├── Secrets Manager
    ├── ECR
    └── IAM
```

---

## Configuration Constants

### AWS_SPECIAL_RESOURCES Additions

```python
AWS_SPECIAL_RESOURCES_ADDITIONS = {
    "aws_api_gateway_rest_api": "handle_api_gateway",
    "aws_apigatewayv2_api": "handle_api_gateway_v2",
    "aws_cloudwatch_event_rule": "handle_eventbridge",
    "aws_sns_topic": "handle_sns",
    "aws_lambda_event_source_mapping": "handle_lambda_esm",
    "aws_elasticache_cluster": "handle_elasticache",
    "aws_elasticache_replication_group": "handle_elasticache_replication",
    "aws_cognito_user_pool": "handle_cognito",
    "aws_wafv2_web_acl": "handle_waf",
    "aws_sagemaker_endpoint": "handle_sagemaker",
    "aws_sfn_state_machine": "handle_step_functions",
    "aws_s3_bucket_notification": "handle_s3_notifications",
    "aws_secretsmanager_secret": "handle_secrets_manager",
    "aws_glue_job": "handle_glue",
    "aws_appsync_graphql_api": "handle_appsync",
}
```

### AWS_CONSOLIDATED_NODES Additions

```python
AWS_CONSOLIDATED_NODES_ADDITIONS = [
    {"aws_api_gateway": {"resource_name": "aws_api_gateway.api", "edge_service": True}},
    {"aws_apigatewayv2": {"resource_name": "aws_apigatewayv2.api", "edge_service": True}},
    {"aws_cognito_user_pool": {"resource_name": "aws_cognito.auth", "edge_service": True}},
    {"aws_wafv2_web_acl": {"resource_name": "aws_waf.firewall", "edge_service": True}},
    {"aws_sagemaker_endpoint": {"resource_name": "aws_sagemaker.ml", "vpc": False}},
    {"aws_appsync": {"resource_name": "aws_appsync.api", "edge_service": True}},
]
```

### AWS_EDGE_NODES Additions

```python
AWS_EDGE_NODES_ADDITIONS = [
    "aws_api_gateway",
    "aws_apigatewayv2",
    "aws_appsync",
    "aws_cognito",
    "aws_waf",
]
```

### AWS_HIDE_NODES Additions

```python
AWS_HIDE_NODES_ADDITIONS = [
    "aws_api_gateway_stage",
    "aws_api_gateway_deployment",
    "aws_api_gateway_method",
    "aws_api_gateway_resource",
    "aws_cognito_user_pool_client",
    "aws_cognito_user_pool_domain",
    "aws_wafv2_web_acl_rule",
    "aws_sagemaker_endpoint_configuration",
    "aws_appsync_resolver",
]
```

---

## Validation Rules

### Connection Validation

1. **No orphan edge services**: API Gateway, AppSync, Cognito must have at least one connection
2. **VPC Link must have targets**: VPC Links without NLB/ALB targets are invalid
3. **Event sources must exist**: Lambda ESM source ARNs must reference existing resources
4. **WAF must protect something**: WAF without associations should be flagged

### Containment Validation

1. **One parent only**: Resources can only be in one container (use numbering for multi-placement)
2. **Hierarchy order**: VPC > AZ > Subnet > Security Group > Resource
3. **Edge services outside VPC**: API Gateway, CloudFront, Cognito, WAF never inside VPC

### Arrow Direction Validation

1. **Event flow direction**: Events flow from producer to consumer (SNS → SQS → Lambda)
2. **Request flow direction**: Requests flow from client to backend (API Gateway → Lambda → DynamoDB)
3. **Consistent direction**: No circular references allowed (existing handler removes them)
