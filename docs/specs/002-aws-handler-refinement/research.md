# Research: AWS Handler Refinement

**Branch**: `002-aws-handler-refinement` | **Date**: 2025-12-26

## Overview

This document captures research findings for implementing AWS resource handlers for the top 80% of common AWS architectural patterns.

---

## Existing Pattern Analysis

### Handler Architecture Principles

**Decision**: Follow existing TerraVision handler patterns
**Rationale**: Consistency with existing codebase ensures maintainability and reduces bugs
**Alternatives Considered**: Custom patterns rejected as they would diverge from established conventions

#### Core Principles Identified:

1. **Hierarchy Over Flatness**: Transform Terraform's flat graphs into AWS's hierarchical structure (VPC → AZ → Subnet → Security Group → Resources)

2. **Containers Over Associations**: Resources that protect or group others become containers (group type nodes)

3. **Direct Over Indirect**: Skip intermediate resources to show direct relationships (e.g., IAM Role → EC2, not Role → Profile → EC2)

### Implementation Patterns

#### Pattern 1: Two-Step Connection Mapping
```python
# Step 1: Build intermediate mapping
mapping = {}
for resource in graphdict:
    for dependency in graphdict[resource]:
        if is_target_type(dependency):
            mapping[dependency] = resource

# Step 2: Apply mapping to create direct connections
for resource in graphdict:
    for dependency in list(graphdict[resource]):  # Copy to avoid mutation
        if dependency in mapping:
            actual_target = mapping[dependency]
            graphdict[resource].append(actual_target)
            graphdict[resource].remove(dependency)
```

#### Pattern 2: Numbered Resource Expansion
```python
# When resource spans multiple parents, create numbered instances
for i, subnet in enumerate(matching_subnets, 1):
    numbered = f"{resource}~{i}"
    graphdict[numbered] = copy(graphdict[resource])
    meta_data[numbered] = deepcopy(meta_data[resource])
    graphdict[subnet].append(numbered)

# CRITICAL: Delete original unnumbered resource
del graphdict[resource]
del meta_data[resource]
```

#### Pattern 3: Synthetic Container Groups
```python
# Create grouping node for related resources
group_node = f"aws_group.{service_name}"
graphdict[group_node] = []
graphdict[group_node].append(resource)
# Remove from previous parent
previous_parent.remove(resource)
```

---

## P1 Pattern Research: API Gateway

### Decision: Add `handle_api_gateway()` function
**Rationale**: API Gateway is the most common entry point for serverless architectures

### Terraform Resources to Handle:
- `aws_api_gateway_rest_api` - REST API
- `aws_api_gateway_stage` - Deployment stages (consolidate)
- `aws_api_gateway_deployment` - Deployments (consolidate)
- `aws_api_gateway_method` - HTTP methods (consolidate)
- `aws_api_gateway_integration` - Backend integrations (detect connections)
- `aws_apigatewayv2_api` - HTTP API (v2)
- `aws_apigatewayv2_integration` - HTTP API integrations
- `aws_apigatewayv2_vpc_link` - VPC Link connections

### Implementation Strategy:
1. Consolidate all API Gateway sub-resources into single REST API node
2. Detect `integration` attributes to find Lambda/Step Functions connections
3. Position as edge service (outside VPC)
4. Handle VPC Link connections to private resources
5. Add "External Integration" placeholder when no integrations defined

### Configuration Additions:
```python
# Add to AWS_CONSOLIDATED_NODES
{"aws_api_gateway": {"resource_name": "aws_api_gateway.api", "edge_service": True}}

# Add to AWS_SPECIAL_RESOURCES
"aws_api_gateway_rest_api": "handle_api_gateway"
"aws_apigatewayv2_api": "handle_api_gateway_v2"
```

---

## P1 Pattern Research: Event-Driven Architecture

### Decision: Add handlers for EventBridge, SNS, SQS, Lambda ESM
**Rationale**: Event-driven is fundamental to modern AWS applications

### Terraform Resources to Handle:
- `aws_cloudwatch_event_rule` - EventBridge rules
- `aws_cloudwatch_event_target` - EventBridge targets
- `aws_sns_topic` - SNS topics
- `aws_sns_topic_subscription` - SNS subscriptions (detect targets)
- `aws_sqs_queue` - SQS queues
- `aws_lambda_event_source_mapping` - Lambda ESM (SQS, Kinesis, DynamoDB Streams)

### Implementation Strategy:

#### EventBridge:
1. Parse `aws_cloudwatch_event_target` to find target ARNs
2. Create EventBridge → Target connections
3. Handle Lambda, Step Functions, SNS, SQS targets

#### SNS:
1. Parse `aws_sns_topic_subscription` for protocol and endpoint
2. Create SNS → SQS, SNS → Lambda connections based on protocol
3. Arrow direction: SNS → consumer (fan-out pattern)

#### SQS → Lambda:
1. Parse `aws_lambda_event_source_mapping` for event_source_arn
2. Create SQS → Lambda connection (Lambda polls SQS)
3. Arrow direction: SQS → Lambda (event flow direction)

#### DynamoDB Streams:
1. Detect `stream_enabled = true` on `aws_dynamodb_table`
2. Find Lambda ESM referencing the stream
3. Create DynamoDB → Lambda connection

### Configuration Additions:
```python
# Add to AWS_REVERSE_ARROW_LIST (events flow from source to consumer)
"aws_lambda_event_source_mapping"
"aws_sns_topic_subscription"
"aws_cloudwatch_event_target"
```

---

## P1 Pattern Research: ElastiCache

### Decision: Add `handle_elasticache()` function
**Rationale**: Nearly every production application uses caching

### Terraform Resources to Handle:
- `aws_elasticache_cluster` - Cache clusters
- `aws_elasticache_replication_group` - Redis replication groups
- `aws_elasticache_subnet_group` - Subnet groups

### Implementation Strategy:
1. Position ElastiCache inside VPC subnets
2. Expand replication groups across AZs with numbered nodes
3. Detect connections from ECS/EKS/EC2 to cache
4. Match cache nodes to subnets by AZ

### Existing Pattern Reference:
- Similar to EKS node group expansion across subnets
- Use `aws_handle_subnet_azs` pattern for AZ placement

---

## P1 Pattern Research: Cognito

### Decision: Add `handle_cognito()` function
**Rationale**: Standard authentication service for serverless/web apps

### Terraform Resources to Handle:
- `aws_cognito_user_pool` - User pools
- `aws_cognito_user_pool_client` - App clients (consolidate)
- `aws_cognito_identity_pool` - Identity pools
- `aws_cognito_user_pool_domain` - Custom domains (consolidate)

### Implementation Strategy:
1. Consolidate User Pool + clients + domain into single Cognito node
2. Detect API Gateway authorizers referencing Cognito
3. Create Users → Cognito → API Gateway flow
4. Detect Lambda triggers in user pool config
5. Position as edge/authentication service

### Lambda Trigger Detection:
Parse `lambda_config` attribute in user pool for triggers:
- `pre_sign_up`
- `post_confirmation`
- `pre_authentication`
- `post_authentication`
- `custom_message`
- etc.

---

## P2 Pattern Research: WAF

### Decision: Add `handle_waf()` function
**Rationale**: Essential for security compliance

### Terraform Resources to Handle:
- `aws_wafv2_web_acl` - WAFv2 Web ACL
- `aws_wafv2_web_acl_association` - ACL associations
- `aws_waf_web_acl` - Classic WAF (legacy)

### Implementation Strategy:
1. Parse `aws_wafv2_web_acl_association` for resource_arn
2. Create WAF → CloudFront/ALB/API Gateway connections
3. Position WAF in front of protected resources (between users and protected service)
4. Consolidate WAF rules into single WAF node

---

## P2 Pattern Research: SageMaker

### Decision: Add `handle_sagemaker()` function
**Rationale**: Growing ML workloads in enterprise

### Terraform Resources to Handle:
- `aws_sagemaker_endpoint` - Inference endpoints
- `aws_sagemaker_endpoint_configuration` - Endpoint configs (consolidate)
- `aws_sagemaker_model` - Models (link to endpoint)
- `aws_sagemaker_notebook_instance` - Notebooks (VPC placement)

### Implementation Strategy:
1. Consolidate endpoint + config + model into logical ML group
2. Detect S3 references in model_data_url for artifact connections
3. Position notebook instances in VPC subnets when configured
4. Detect Lambda → SageMaker runtime invocations

---

## P2 Pattern Research: Step Functions

### Decision: Add `handle_step_functions()` function
**Rationale**: Key orchestration service

### Terraform Resources to Handle:
- `aws_sfn_state_machine` - State machines

### Implementation Strategy:
1. Parse `definition` JSON to extract service integrations
2. Detect Lambda, ECS, SageMaker, DynamoDB, SNS, SQS task states
3. Create Step Functions → integrated service connections
4. Handle API Gateway → Step Functions flow (sync/async)

### Definition Parsing:
State machine definitions contain resource ARNs in task states:
```json
{
  "States": {
    "LambdaTask": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:my-function"
    }
  }
}
```

---

## P2 Pattern Research: S3 Notifications

### Decision: Add `handle_s3_notifications()` function
**Rationale**: S3 is foundational for data flow patterns

### Terraform Resources to Handle:
- `aws_s3_bucket_notification` - Bucket notifications
- `aws_s3_bucket_replication_configuration` - Replication

### Implementation Strategy:
1. Parse notification config for Lambda/SQS/SNS targets
2. Create S3 → Lambda/SQS/SNS connections
3. Detect replication configuration for bucket-to-bucket flows

---

## P2 Pattern Research: Secrets Manager

### Decision: Add `handle_secrets_manager()` function
**Rationale**: Essential for secure configuration

### Terraform Resources to Handle:
- `aws_secretsmanager_secret` - Secrets
- `aws_secretsmanager_secret_rotation` - Rotation config
- `aws_ssm_parameter` - Parameter Store

### Implementation Strategy:
1. Detect secret references in Lambda/ECS environment variables
2. Create Application → Secrets Manager connections
3. Detect rotation Lambda functions
4. Add Secrets Manager to SHARED_SERVICES group

---

## P3 Pattern Research: Glue/Athena

### Decision: Add `handle_glue()` and `handle_athena()` functions
**Rationale**: Common data lake patterns

### Terraform Resources to Handle:
- `aws_glue_job` - ETL jobs
- `aws_glue_crawler` - Data crawlers
- `aws_glue_catalog_database` - Catalog databases
- `aws_athena_workgroup` - Query workgroups
- `aws_kinesis_firehose_delivery_stream` - Firehose

### Implementation Strategy:
1. Parse Glue job scripts for S3 sources/destinations
2. Detect Athena → S3 query patterns
3. Parse Firehose destination configuration

---

## P3 Pattern Research: AppSync

### Decision: Add `handle_appsync()` function
**Rationale**: Growing GraphQL adoption

### Terraform Resources to Handle:
- `aws_appsync_graphql_api` - GraphQL API
- `aws_appsync_datasource` - Data sources
- `aws_appsync_resolver` - Resolvers (consolidate)

### Implementation Strategy:
1. Parse data sources for DynamoDB/Lambda connections
2. Consolidate resolvers into API node
3. Position as edge service (similar to API Gateway)
4. Detect Cognito authentication configuration

---

## Configuration Updates Summary

### AWS_SPECIAL_RESOURCES Additions:
```python
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
```

### AWS_CONSOLIDATED_NODES Additions:
- API Gateway stages/deployments/methods
- Cognito clients/domains
- WAF rules/rule groups
- SageMaker endpoint configs
- AppSync resolvers

### AWS_EDGE_NODES Additions:
- API Gateway
- AppSync
- Cognito (authentication layer)
- WAF (security layer)

### AWS_GROUP_NODES Considerations:
- ElastiCache clusters may become group nodes for multi-node clusters
- SageMaker notebook instances in VPC

---

## Test Terraform Sources

Based on clarification, test configurations should come from:

1. **AWS Reference Architectures**: https://github.com/aws-samples/
2. **HashiCorp Examples**: https://github.com/hashicorp/terraform-provider-aws/tree/main/examples
3. **AWS Quick Starts**: https://github.com/aws-quickstart/

### Recommended Test Fixtures by Pattern:

| Pattern | Source Reference |
|---------|-----------------|
| API Gateway + Lambda | aws-samples/serverless-patterns |
| EventBridge | aws-samples/amazon-eventbridge-integration-patterns |
| ECS + ElastiCache | terraform-provider-aws/examples |
| Cognito + API Gateway | aws-samples/amazon-cognito-api-gateway |
| SageMaker Endpoint | aws-samples/amazon-sagemaker-examples |
| Step Functions | aws-samples/aws-stepfunctions-examples |

---

## Risk Mitigation

### Backward Compatibility:
- Run existing test suite before and after each handler addition
- Use feature flags for new handlers if needed
- Keep original handler code paths intact

### Incremental Implementation:
- Implement P1 patterns first (API Gateway, Event-Driven, ElastiCache, Cognito)
- Validate with tests before proceeding to P2
- P3 patterns are optional enhancements

---

## Next Steps

1. **Phase 1 Design**: Create data-model.md with entity definitions
2. **Phase 1 Design**: Create quickstart.md with implementation guide
3. **Task Generation**: Run `/speckit.tasks` to create implementation tasks
