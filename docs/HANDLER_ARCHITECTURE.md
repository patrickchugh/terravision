# Resource Handler Architecture

## Overview

TerraVision uses a **hybrid configuration-driven architecture** for processing cloud resources. This document provides a high-level overview of how resource handlers work.

## Three Handler Types

### 1. Pure Config-Driven (7 AWS handlers)

**Use when**: Simple, repetitive operations (expand, move, link, delete)

**Benefits**: 
- 70% code reduction
- Declarative and easy to understand
- No Python code needed

**Example**:
```python
"aws_vpc_endpoint": {
    "transformations": [
        {"operation": "move_to_parent", "params": {...}},
        {"operation": "delete_nodes", "params": {...}},
    ],
}
```

**Current AWS handlers**:
- `aws_eks_node_group` - Expand per subnet
- `aws_eks_fargate_profile` - Expand per subnet
- `aws_autoscaling_group` - Link to subnets
- `random_string` - Disconnect
- `aws_vpc_endpoint` - Move and delete
- `aws_db_subnet_group` - Move and delete
- `aws_` (pattern) - Group shared services

### 2. Pure Function (6 AWS handlers)

**Use when**: Complex logic that can't be expressed declaratively

**Reasons for complexity**:
- Conditional logic with multiple branches
- Dynamic name generation
- Bidirectional relationship manipulation
- Metadata parsing and propagation
- Domain-specific logic (Karpenter detection, chart-specific behavior)
- Selective copying with filtering

**Example**:
```python
"aws_security_group": {
    "additional_handler_function": "aws_handle_sg",
}
```

**Current AWS handlers**:
- `aws_appautoscaling_target` - Count propagation + connection redirection
- `aws_security_group` - Reverse relationships
- `aws_lb` - Metadata parsing
- `aws_ecs` - Conditional logic
- `aws_eks` - Cluster grouping + Karpenter
- `helm_release` - Chart-specific logic

### 3. Hybrid (3 AWS handlers)

**Use when**: Common operations + unique logic

**Benefits**:
- Reuse transformers for common operations
- Write code only for unique logic
- Best of both worlds

**Example**:
```python
"aws_subnet": {
    "handler_execution_order": "before",  # Run custom function FIRST
    "additional_handler_function": "aws_prepare_subnet_az_metadata",
    "transformations": [
        {"operation": "insert_intermediate_node", "params": {...}},
    ],
}
```

**Execution order**: Config transformations → Custom function (default: "after")
- Use `handler_execution_order: "before"` to run custom function first

**Current AWS handlers**:
- `aws_subnet` - Metadata prep (before) + insert_intermediate_node transformer (51→39 lines, 24% reduction)
- `aws_cloudfront_distribution` - Link transformers + custom origin parsing
- `aws_efs_file_system` - Bidirectional link transformer + custom cleanup logic

## Architecture Components

### Configuration Files
- `modules/config/resource_handler_configs_aws.py` - AWS handler configs
- `modules/config/resource_handler_configs_gcp.py` - GCP handler configs
- `modules/config/resource_handler_configs_azure.py` - Azure handler configs

### Transformer Functions
- `modules/resource_transformers.py` - 24 reusable transformation building blocks

### Handler Functions
- `modules/resource_handlers_aws.py` - AWS custom handler functions
- `modules/resource_handlers_gcp.py` - GCP custom handler functions
- `modules/resource_handlers_azure.py` - Azure custom handler functions

### Execution Engine
- `modules/graphmaker.py` - `handle_special_resources()` function executes handlers

## Execution Flow

```
1. Load provider-specific handler configs (automatic detection)
2. For each resource pattern in config:
   a. Check if resource exists in graph
   b. If "transformations" key exists:
      - Execute transformation pipeline
   c. If "additional_handler_function" key exists:
      - Call custom Python function
3. Continue to next handler
```

## 24 Available Transformers

**Expansion**: `expand_to_numbered_instances`, `clone_with_suffix`

**Grouping**: `create_group_node`, `group_shared_services`, `move_to_parent`, `move_to_vpc_parent`, `consolidate_into_single_node`

**Connections**: `link_resources`, `unlink_resources`, `unlink_from_parents`, `redirect_connections`, `redirect_to_security_group`, `match_by_suffix`, `link_via_shared_child`, `link_by_metadata_pattern`, `create_transitive_links`, `bidirectional_link`, `replace_connection_targets`

**Graph Manipulation**: `insert_intermediate_node`

**Metadata**: `propagate_metadata`

**Cleanup**: `delete_nodes`

**Variants**: `apply_resource_variants`, `apply_all_variants`

**Pipeline**: `apply_transformation_pipeline`

### Automatic Function Resolution

Parameters ending in `_function` or `_generator` are **automatically resolved** from string names to actual function references from handler modules (`resource_handlers_aws.py`, `resource_handlers_gcp.py`, `resource_handlers_azure.py`).

**Example**:
```python
"transformations": [
    {
        "operation": "insert_intermediate_node",
        "params": {
            "intermediate_node_generator": "generate_az_node_name",  # String in config
        },
    },
]
# Automatically resolved at runtime to: handlers_aws.generate_az_node_name (function reference)
```

This allows configuration files to specify callable parameters without module imports or manual function mapping.

## Key Decisions

### Why Keep 6 Handlers as Pure Functions?

After analysis, these handlers require Python functions because they involve:

1. **Count propagation with selective filtering** (autoscaling targets - copy to services but not policies)
2. **Complex conditional logic** (security group reverse relationships)
3. **Metadata parsing and redirection** (load balancer target groups)
4. **Chart-specific behavior** (Helm releases, ECS task definitions)
5. **Complex detection logic** (EKS Karpenter support)

These operations are too complex to express declaratively with current transformers.

### Why Use Hybrid for 3 Handlers?

These handlers combine generic operations with custom logic:

1. **aws_subnet** - Generic `insert_intermediate_node` transformer + custom metadata prep
2. **aws_cloudfront_distribution** - Generic link transformers + custom origin domain parsing
3. **aws_efs_file_system** - Generic `bidirectional_link` transformer + custom cleanup

Result: 24% code reduction for aws_subnet (51→39 lines) while maintaining clarity.

### Why Migrate 7 Handlers to Pure Config?

These handlers only needed simple operations:
- Expand resources to numbered instances
- Move resources between parents
- Delete intermediate nodes
- Link/unlink resources
- Group shared services

All expressible with existing transformers → 70% code reduction (360 lines → 85 lines).

## Benefits

1. **Right tool for the job**: Config for simple, code for complex
2. **Code reduction**: 70% reduction for simple handlers
3. **Maintainability**: Less code, clearer intent
4. **Flexibility**: Mix approaches as needed
5. **Gradual migration**: Can migrate incrementally
6. **Single source of truth**: All handler metadata in config files

## Documentation

- **HANDLER_CONFIG_GUIDE.md** - How to use the configuration system
- **CONFIGURATION_DRIVEN_HANDLERS.md** - Detailed architecture and examples
- **developer_guide.md** - Developer patterns and best practices
- **aws_resource_handlers/** - Detailed AWS handler specifications

## Testing

All 135 tests pass with hybrid architecture:
- Unit tests for transformers
- Integration tests for handlers
- Provider detection tests
- Config loader tests
