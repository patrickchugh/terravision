# Research: AWS Handler Refinement

**Branch**: `002-aws-handler-refinement` | **Date**: 2025-12-26

## Overview

This document captures research findings for implementing AWS resource handlers for the top 80% of common AWS architectural patterns using TerraVision's **config-driven handler architecture**.

**⚠️ Baseline Validation (CO-005.1)**: The 14 handlers in this research address specific cases where baseline Terraform graph parsing produces insufficient diagrams. Most AWS services (80-90%) work correctly with baseline parsing and DO NOT need custom handlers.

**For future research**: Always test baseline output first and document why it's insufficient before proposing a handler.

---

## Existing Pattern Analysis

### Handler Architecture Principles

**Decision**: Follow config-driven handler architecture per constitution CO-006 through CO-012
**Rationale**: Config-driven approach reduces code by 70%, improves maintainability through reusable transformers, and ensures cross-provider consistency
**Alternatives Considered**: Pure Python handlers rejected due to linear code growth (270 functions for 3 providers × 90 services vs 25 transformers + configs)

#### Constitutional Requirements (CO-006 through CO-012):

1. **CO-006**: Resource handlers MUST be implemented as **Pure Config-Driven** whenever possible
2. **CO-007**: Handlers SHOULD use **Hybrid** approach when combining generic operations with unique logic
3. **CO-008**: Handlers MAY use **Pure Function** ONLY when logic is too complex for declarative expression
4. **CO-009**: Custom Python functions MUST document why config-driven was insufficient
5. **CO-010**: New transformers added when pattern reused across 3+ handlers
6. **CO-011**: Configurations MUST include descriptive `description` field
7. **CO-012**: Parameters ending in `_function` or `_generator` auto-resolve to function references

#### Decision Hierarchy (attempt in order):
1. **Pure Config-Driven** - Use only existing transformers (70% code reduction, easiest to maintain)
2. **Hybrid** - Add new generic transformer if pattern is reusable, supplement with custom function for unique logic
3. **Pure Function** - Only for complex conditional logic that cannot be expressed declaratively

#### Core Architectural Principles:

1. **Hierarchy Over Flatness**: Transform Terraform's flat graphs into AWS's hierarchical structure (VPC → AZ → Subnet → Security Group → Resources)

2. **Containers Over Associations**: Resources that protect or group others become containers (group type nodes)

3. **Direct Over Indirect**: Skip intermediate resources to show direct relationships (e.g., IAM Role → EC2, not Role → Profile → EC2)

### Available Transformers (24 operations)

Reference: `modules/resource_transformers.py`

**Resource Expansion** (2):
- `expand_to_numbered_instances` - Create ~1, ~2, ~3 instances per subnet
- `clone_with_suffix` - Duplicate resources with numbered suffixes

**Resource Grouping** (7):
- `create_group_node` - Add container/group nodes
- `group_shared_services` - Group shared services together (IAM, CloudWatch, etc.)
- `move_to_parent` - Relocate resources in hierarchy
- `move_to_vpc_parent` - Move resources to VPC level
- `consolidate_into_single_node` - Merge multiple resources into one

**Connections** (11):
- `link_resources` - Add connections between resources
- `unlink_resources` - Remove connections
- `unlink_from_parents` - Remove child from parent connections
- `redirect_connections` - Change parent references
- `redirect_to_security_group` - Redirect to security groups if present
- `match_by_suffix` - Link resources with same ~N suffix
- `link_via_shared_child` - Create direct links when resources share a child
- `link_by_metadata_pattern` - Create links based on metadata patterns
- `create_transitive_links` - Create transitive connections through intermediates
- `bidirectional_link` - Create bidirectional connections
- `replace_connection_targets` - Replace old connection targets with new ones

**Graph Manipulation** (1):
- `insert_intermediate_node` - Insert intermediate nodes between parents and children

**Metadata Operations** (1):
- `propagate_metadata` - Copy metadata from source to target resources

**Cleanup** (1):
- `delete_nodes` - Remove resources from graph

**Variants** (2):
- `apply_resource_variants` - Change resource type based on metadata
- `apply_all_variants` - Apply all variants globally

### Config-Driven Implementation Patterns

#### Pattern 1: Pure Config-Driven Handler
```python
# In modules/config/resource_handler_configs_aws.py
"aws_resource_type": {
    "description": "What this handler does and why it uses this approach",
    "transformations": [
        {
            "operation": "expand_to_numbered_instances",
            "params": {
                "resource_pattern": "aws_resource_type",
                "subnet_key": "subnet_ids",
            },
        },
        {
            "operation": "link_resources",
            "params": {
                "source_pattern": "aws_resource_type",
                "target_pattern": "aws_target",
            },
        },
    ],
}
```

#### Pattern 2: Hybrid Handler (Config + Custom Function)
```python
# Config-driven transformations + custom logic for complex cases
"aws_complex_resource": {
    "description": "Handler combining generic operations with unique logic",
    "transformations": [
        {
            "operation": "expand_to_numbered_instances",
            "params": {"resource_pattern": "aws_complex_resource", "subnet_key": "subnet_ids"},
        },
    ],
    "additional_handler_function": "aws_handle_complex_custom",  # Custom function in resource_handlers_aws.py
}

# In modules/resource_handlers_aws.py
def aws_handle_complex_custom(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle complex logic that cannot be expressed with transformers.

    Why custom function needed: [specific justification per CO-009]
    """
    # Complex conditional logic, metadata parsing, etc.
    return tfdata
```

#### Pattern 3: Pure Function Handler (Too Complex for Config)
```python
# Only when logic is too complex for declarative expression
"aws_very_complex": {
    "description": "Complex bidirectional logic requiring conditional branches",
    "additional_handler_function": "aws_handle_very_complex",
}

# In modules/resource_handlers_aws.py
def aws_handle_very_complex(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Why Pure Function: Multiple conditional branches, dynamic name generation,
    bidirectional relationship manipulation that transformers cannot express.
    """
    # Complex logic here
    return tfdata
```

---

## P1 Pattern Research: API Gateway

### Decision: **❌ NO HANDLER NEEDED** (Baseline validation showed handlers unnecessary)

**⚠️ Original Plan (REJECTED)**: Hybrid handler with config transformations + custom integration parsing

**Validation Process**:
1. Created test Terraform: API Gateway REST API + Lambda integration
2. Generated baseline diagram WITHOUT custom handler
3. Analyzed output

**Baseline Output**:
```
Lambda → Integration → Method → Resource → REST API
```

**Analysis**:
- ✅ All resources visible with correct icons
- ✅ Connections show Lambda serving API Gateway
- ✅ Hierarchy is clear (method → resource → API)
- ✅ Users can understand the architecture

**Attempted Implementation (Failed)**:
- Tried to parse integration URIs to create direct API → Lambda connections
- Problem: In `terraform plan`, URIs show as `true` (computed values), not actual ARNs
- Result: Created unhelpful `tv_external.api_integration_...` placeholder nodes
- Made diagram WORSE, not better

**Final Decision**: ❌ **No handler implemented** - baseline is sufficient!

**⚠️ Lesson Learned**: This is a textbook example of CO-005.1 in action:
- "Most services MUST NOT have custom handlers - trust the baseline Terraform graph parsing"
- Always validate baseline first before assuming handlers are needed
- "Looks better" is not a valid reason - must fix actual confusion/inaccuracy

### Terraform Resources (Handled by Baseline)
- `aws_api_gateway_rest_api` - REST API (baseline shows clearly)
- `aws_api_gateway_integration` - Integrations (connections visible via Terraform dependencies)
- `aws_api_gateway_method` - Methods (part of resource hierarchy)
- `aws_api_gateway_resource` - Resources (part of resource hierarchy)
- `aws_apigatewayv2_api` - HTTP/WebSocket APIs (baseline shows clearly)

**No custom handler code needed** - Terraform dependency graph is sufficient!

---

## P1 Pattern Research: Event-Driven Architecture

### Decision: **Hybrid Handlers** (config transformations + custom ARN parsing)
**Rationale**: Event-driven is fundamental to modern AWS applications. Connection creation can use `link_resources` transformer, but ARN parsing and endpoint resolution require custom logic.

### Terraform Resources to Handle:
- `aws_cloudwatch_event_rule` - EventBridge rules
- `aws_cloudwatch_event_target` - EventBridge targets
- `aws_sns_topic` - SNS topics
- `aws_sns_topic_subscription` - SNS subscriptions (detect targets)
- `aws_sqs_queue` - SQS queues
- `aws_lambda_event_source_mapping` - Lambda ESM (SQS, Kinesis, DynamoDB Streams)

### Recommended Handler Type: **Hybrid** (ARN parsing requires custom logic)
```python
# In modules/config/resource_handler_configs_aws.py
"aws_cloudwatch_event_rule": {
    "description": "Parse EventBridge targets and create event flow connections",
    "additional_handler_function": "aws_handle_eventbridge_targets",  # Custom ARN parsing
}

"aws_sns_topic": {
    "description": "Parse SNS subscriptions and create fan-out connections",
    "transformations": [
        {
            "operation": "link_resources",
            "params": {
                "source_pattern": "aws_sns_topic",
                "target_pattern": "aws_sqs_queue|aws_lambda_function",
            },
        },
    ],
    "additional_handler_function": "aws_handle_sns_subscriptions",  # Parse protocol/endpoint
}

"aws_lambda_event_source_mapping": {
    "description": "Create event source to Lambda connections",
    "additional_handler_function": "aws_handle_lambda_esm",  # Parse event_source_arn
}
```

**Why Hybrid**: ARN parsing and endpoint resolution from Terraform metadata requires conditional logic and string manipulation that transformers cannot express declaratively.

---

## P1 Pattern Research: ElastiCache

### Decision: **Pure Config-Driven** (reuses existing `expand_to_numbered_instances` transformer)
**Rationale**: Nearly every production application uses caching. Pattern is identical to EKS node groups (expansion across subnets).

### Terraform Resources to Handle:
- `aws_elasticache_cluster` - Cache clusters
- `aws_elasticache_replication_group` - Redis replication groups
- `aws_elasticache_subnet_group` - Subnet groups

### Recommended Handler Type: **Pure Config-Driven**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_elasticache_replication_group": {
    "description": "Expand ElastiCache replication groups to numbered instances per subnet",
    "transformations": [
        {
            "operation": "expand_to_numbered_instances",
            "params": {
                "resource_pattern": "aws_elasticache_replication_group",
                "subnet_key": "subnet_group_name",  # References aws_elasticache_subnet_group
                "skip_if_numbered": True,
            },
        },
        {
            "operation": "match_by_suffix",  # Link cache~1 to app~1
            "params": {
                "source_pattern": "aws_ecs_service|aws_eks_node_group",
                "target_pattern": "aws_elasticache",
            },
        },
    ],
}
```

**Why Pure Config**: Identical pattern to `aws_eks_node_group` - expansion across subnets + suffix matching for connections. No custom logic needed.

---

## P1 Pattern Research: Cognito

### Decision: **Hybrid Handler** (config consolidation + custom Lambda trigger detection)
**Rationale**: Standard authentication service for serverless/web apps. Consolidation uses transformers, but parsing `lambda_config` metadata requires custom logic.

### Terraform Resources to Handle:
- `aws_cognito_user_pool` - User pools
- `aws_cognito_user_pool_client` - App clients (consolidate)
- `aws_cognito_identity_pool` - Identity pools
- `aws_cognito_user_pool_domain` - Custom domains (consolidate)

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_cognito_user_pool": {
    "description": "Consolidate Cognito resources and detect Lambda triggers",
    "transformations": [
        {
            "operation": "consolidate_into_single_node",
            "params": {
                "resource_pattern": "aws_cognito",
                "target_node_name": "aws_cognito.auth",
            },
        },
    ],
    "additional_handler_function": "aws_handle_cognito_triggers",  # Parse lambda_config
}
```

**Why Hybrid**: Consolidation is generic, but detecting Lambda triggers from `lambda_config` metadata (pre_sign_up, post_confirmation, etc.) requires custom parsing logic.

---

## P2 Pattern Research: WAF

### Decision: **Hybrid Handler** (config consolidation + custom association parsing)
**Rationale**: Essential for security compliance. Consolidation uses transformers, but parsing `resource_arn` from associations requires custom logic.

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_wafv2_web_acl": {
    "description": "Consolidate WAF rules and parse resource associations",
    "transformations": [
        {
            "operation": "consolidate_into_single_node",
            "params": {
                "resource_pattern": "aws_wafv2_web_acl",
                "target_node_name": "aws_waf.firewall",
            },
        },
    ],
    "additional_handler_function": "aws_handle_waf_associations",  # Parse resource_arn
}
```

**Why Hybrid**: Consolidation is generic, but parsing association ARNs to determine CloudFront/ALB/API Gateway requires custom logic.

---

## P2 Pattern Research: SageMaker

### Decision: **Hybrid Handler** (config consolidation + custom S3 artifact detection)
**Rationale**: Growing ML workloads in enterprise. Consolidation uses transformers, but parsing `model_data_url` for S3 connections requires custom logic.

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_sagemaker_endpoint": {
    "description": "Consolidate SageMaker components and detect S3 artifacts",
    "transformations": [
        {
            "operation": "consolidate_into_single_node",
            "params": {
                "resource_pattern": "aws_sagemaker_endpoint",
                "target_node_name": "aws_sagemaker.ml",
            },
        },
    ],
    "additional_handler_function": "aws_handle_sagemaker_artifacts",  # Parse model_data_url
}
```

**Why Hybrid**: Consolidation is generic, but extracting S3 bucket references from model URLs requires custom parsing.

---

## P2 Pattern Research: Step Functions

### Decision: **Pure Function Handler** (complex JSON definition parsing)
**Rationale**: Key orchestration service. Parsing state machine definition JSON with conditional logic for different task types (Lambda, ECS, SageMaker, DynamoDB) is too complex for transformers.

### Recommended Handler Type: **Pure Function**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_sfn_state_machine": {
    "description": "Parse state machine definition JSON to detect service integrations",
    "additional_handler_function": "aws_handle_step_functions",
}

# In modules/resource_handlers_aws.py
def aws_handle_step_functions(tfdata):
    """
    Why Pure Function: Parsing JSON state machine definitions with conditional
    logic for multiple task types (Lambda, ECS, SageMaker, DynamoDB, SNS, SQS)
    requires complex branching and ARN extraction that transformers cannot express.
    """
    # Parse definition JSON, extract ARNs, create connections
    return tfdata
```

**Why Pure Function**: JSON parsing with conditional logic for multiple service integration types cannot be expressed declaratively.

---

## P2 Pattern Research: S3 Notifications

### Decision: **Hybrid Handler** (config linking + custom notification config parsing)
**Rationale**: S3 is foundational for data flow patterns. Generic linking available, but parsing notification configurations requires custom logic.

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_s3_bucket_notification": {
    "description": "Parse S3 notification configurations and create event connections",
    "transformations": [
        {
            "operation": "link_resources",
            "params": {
                "source_pattern": "aws_s3_bucket",
                "target_pattern": "aws_lambda_function|aws_sqs_queue|aws_sns_topic",
            },
        },
    ],
    "additional_handler_function": "aws_handle_s3_notification_config",  # Parse notification targets
}
```

**Why Hybrid**: Generic linking available, but parsing notification configurations for specific targets requires custom logic.

---

## P2 Pattern Research: Secrets Manager

### Decision: **Hybrid Handler** (config grouping + custom reference detection)
**Rationale**: Essential for secure configuration. Adding to shared services uses transformer, but detecting secret references in environment variables requires custom logic.

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_secretsmanager_secret": {
    "description": "Group secrets as shared services and detect application references",
    "transformations": [
        {
            "operation": "group_shared_services",
            "params": {
                "service_patterns": ["aws_secretsmanager_secret", "aws_ssm_parameter"],
                "group_name": "aws_group.shared_services",
            },
        },
    ],
    "additional_handler_function": "aws_handle_secret_references",  # Detect env var references
}
```

**Why Hybrid**: Grouping is generic, but scanning Lambda/ECS environment variables for secret ARNs requires custom parsing.

---

## P3 Pattern Research: Glue/Athena/Firehose

### Decision: **Hybrid Handlers** (config linking + custom script/config parsing)
**Rationale**: Common data lake patterns. Generic linking available, but parsing Glue scripts and Firehose destinations requires custom logic.

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_glue_job": {
    "description": "Parse Glue job scripts to detect S3 sources and targets",
    "transformations": [
        {
            "operation": "link_resources",
            "params": {
                "source_pattern": "aws_glue_job",
                "target_pattern": "aws_s3_bucket",
            },
        },
    ],
    "additional_handler_function": "aws_handle_glue_scripts",  # Parse script_location for S3
}

"aws_kinesis_firehose_delivery_stream": {
    "description": "Parse Firehose destination configuration",
    "additional_handler_function": "aws_handle_firehose_destinations",  # Parse destination config
}
```

**Why Hybrid**: Generic linking available, but parsing job scripts and destination configurations requires custom logic.

---

## P3 Pattern Research: AppSync

### Decision: **Hybrid Handler** (config consolidation + custom data source parsing)
**Rationale**: Growing GraphQL adoption. Consolidation uses transformers, but parsing data source configurations requires custom logic.

### Recommended Handler Type: **Hybrid**
```python
# In modules/config/resource_handler_configs_aws.py
"aws_appsync_graphql_api": {
    "description": "Consolidate AppSync resources and parse data sources",
    "transformations": [
        {
            "operation": "consolidate_into_single_node",
            "params": {
                "resource_pattern": "aws_appsync",
                "target_node_name": "aws_appsync.api",
            },
        },
    ],
    "additional_handler_function": "aws_handle_appsync_datasources",  # Parse data sources
}
```

**Why Hybrid**: Consolidation is generic, but parsing data source configurations for DynamoDB/Lambda requires custom logic.

---

## Configuration Updates Summary

All handlers defined in `modules/config/resource_handler_configs_aws.py` per constitution CO-006 through CO-013.

### Handler Type Distribution:

| Handler | Type | Transformers Used | Custom Function | Rationale |
|---------|------|-------------------|-----------------|-----------|
| ElastiCache | Pure Config | expand_to_numbered_instances, match_by_suffix | None | Identical to EKS node groups |
| API Gateway | Hybrid | consolidate_into_single_node, delete_nodes | aws_handle_api_gateway_integrations | URI parsing complex |
| EventBridge | Hybrid | link_resources | aws_handle_eventbridge_targets | ARN parsing complex |
| SNS | Hybrid | link_resources | aws_handle_sns_subscriptions | Protocol/endpoint resolution |
| Lambda ESM | Hybrid | - | aws_handle_lambda_esm | event_source_arn parsing |
| Cognito | Hybrid | consolidate_into_single_node | aws_handle_cognito_triggers | lambda_config parsing |
| WAF | Hybrid | consolidate_into_single_node | aws_handle_waf_associations | Association ARN parsing |
| SageMaker | Hybrid | consolidate_into_single_node | aws_handle_sagemaker_artifacts | model_data_url parsing |
| Step Functions | Pure Function | - | aws_handle_step_functions | Complex JSON definition parsing |
| S3 Notifications | Hybrid | link_resources | aws_handle_s3_notification_config | Notification config parsing |
| Secrets Manager | Hybrid | group_shared_services | aws_handle_secret_references | Env var reference detection |
| Glue | Hybrid | link_resources | aws_handle_glue_scripts | Script parsing |
| Firehose | Pure Function | - | aws_handle_firehose_destinations | Destination config complex |
| AppSync | Hybrid | consolidate_into_single_node | aws_handle_appsync_datasources | Data source parsing |

### Summary:
- **1 Pure Config-Driven handler** (ElastiCache)
- **11 Hybrid handlers** (most common pattern)
- **2 Pure Function handlers** (Step Functions, Firehose)

### New Transformers Needed:

**None** - All patterns can be expressed using existing 24 transformers + custom functions for complex parsing logic.

This validates the transformer library is approaching saturation per CO-013 (target: ~30 operations).

### Cross-Provider Reusability:

These handlers demonstrate strong cross-provider reusability potential:
- ElastiCache expansion pattern → Azure Cache, GCP Memorystore
- API Gateway consolidation → Azure API Management, GCP API Gateway
- Event-driven patterns → Azure Event Grid, GCP Eventarc
- Secrets management → Azure Key Vault, GCP Secret Manager

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
