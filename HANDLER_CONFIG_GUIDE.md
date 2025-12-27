# Handler Configuration Guide

## Overview

TerraVision uses a unified hybrid configuration-driven approach for all resource handlers. Handlers can be:
1. **Pure config-driven**: Use only transformation building blocks (declarative)
2. **Hybrid**: Use transformations + custom Python function (best of both worlds)
3. **Pure function**: Use only custom Python function (for complex logic)

All handlers are defined in `modules/config/resource_handler_configs_<provider>.py` with automatic provider detection.

## Why Hybrid Architecture?

**Problem**: Some handlers are simple (move, link, delete), others are complex (conditional logic, dynamic naming, metadata manipulation).

**Solution**: Use the right tool for each handler:
- **Config** for simple, repetitive operations (70% code reduction)
- **Functions** for complex logic that can't be expressed declaratively
- **Both** when you need common operations + unique logic

## Configuration Structure

```python
RESOURCE_HANDLER_CONFIGS = {
    "resource_pattern": {
        "description": "What this handler does",
        "transformations": [  # Optional: config-driven transformations
            {
                "operation": "transformer_name",
                "params": {
                    "param1": "value1",
                    "param2": "value2",
                }
            },
        ],
        "additional_handler_function": "function_name",  # Optional: custom Python function
    },
}
```

## Handler Types

### 1. Pure Config-Driven Handler

Uses only transformation building blocks. No custom Python code needed.

**Example: VPC Endpoint Handler**
```python
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
```

### 2. Hybrid Handler

Uses transformations for common operations, then custom function for complex logic.

**Example: EKS Node Group (Hypothetical)**
```python
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
    "additional_handler_function": "aws_handle_eks_node_group_custom",  # Custom logic after expansion
},
```

### 3. Pure Function Handler

Uses only custom Python function for complex logic that can't be expressed with transformers.

**Example: Security Group Handler**
```python
"aws_security_group": {
    "description": "Process security group relationships and reverse connections",
    "additional_handler_function": "aws_handle_sg",
},
```

## Execution Order

When a resource pattern matches:

1. **Config-driven transformations** are applied first (if `transformations` key exists)
2. **Additional handler function** is called second (if `additional_handler_function` key exists)

This allows you to:
- Reuse common transformations across handlers
- Only write custom code for unique logic
- Gradually migrate complex handlers to config-driven approach

## Available Transformers

All transformers are defined in `modules/resource_transformers.py`:

### Resource Expansion
- **expand_to_numbered_instances** - Create numbered instances per subnet (~1, ~2, ~3)
- **clone_with_suffix** - Duplicate resources with numbered suffixes

### Resource Grouping
- **create_group_node** - Create container/group nodes
- **group_shared_services** - Group shared services together (IAM, CloudWatch, etc.)
- **move_to_parent** - Move resources between parents
- **move_to_vpc_parent** - Move resources to VPC level

### Connections
- **link_resources** - Create connections between resources
- **unlink_resources** - Remove connections
- **redirect_connections** - Redirect connections to different resources
- **redirect_to_security_group** - Redirect to security groups if present
- **match_by_suffix** - Link resources with matching ~N suffixes

### Cleanup
- **delete_nodes** - Delete nodes from graph

### Variants
- **apply_resource_variants** - Apply resource type variants (e.g., Fargate vs EC2)
- **apply_all_variants** - Apply all variants globally

### Pipeline
- **apply_transformation_pipeline** - Execute sequence of transformations

## Benefits

1. **Reusability**: Common operations defined once, used everywhere
2. **Maintainability**: Less code to maintain, easier to understand
3. **Flexibility**: Mix config and code as needed - use the right tool for each handler
4. **Gradual Migration**: Can migrate handlers incrementally from function to config
5. **Single Source of Truth**: All handler metadata in one place
6. **Code Reduction**: 70% reduction for simple handlers (360 lines → 85 lines for 7 handlers)
7. **Clarity**: Handler type (config/hybrid/function) is immediately clear from structure

## Migration Path

To migrate a handler from pure function to hybrid or pure config:

1. **Analyze the function**: Identify operations that match existing transformers
2. **Add transformations**: Create `transformations` array with those operations
3. **Keep or remove function**: 
   - If complex logic remains, keep as `additional_handler_function` (hybrid)
   - If all logic is covered, remove function entirely (pure config)
4. **Test thoroughly**: Ensure behavior matches original
5. **Update documentation**: Document the handler type and purpose

## Current State (AWS)

**Pure config-driven** (7 handlers):
- `aws_eks_node_group` - Expand node groups per subnet
- `aws_eks_fargate_profile` - Expand Fargate profiles per subnet  
- `aws_autoscaling_group` - Link ASG to subnets
- `random_string` - Disconnect random resources
- `aws_vpc_endpoint` - Move to VPC and delete
- `aws_db_subnet_group` - Move to VPC and delete
- `aws_` (pattern match) - Group shared services

**Pure function** (9 handlers - too complex for config):
- `aws_cloudfront_distribution` - Complex origin domain parsing + transitive LB links
- `aws_subnet` - Dynamic AZ node creation with suffix logic
- `aws_appautoscaling_target` - Count propagation with try/except
- `aws_efs_file_system` - Bidirectional relationship manipulation
- `aws_security_group` - Complex reverse relationship logic
- `aws_lb` - Metadata parsing and connection redirection
- `aws_ecs` - Chart-specific conditional logic
- `aws_eks` - Complex cluster grouping and Karpenter detection
- `helm_release` - Chart-specific conditional logic

**Hybrid** (0 handlers currently):
- None yet, but architecture supports it for future needs

## Example: Before and After

### Before (Pure Python)
```python
# In resource_handlers_aws.py
def aws_handle_vpc_endpoint(tfdata):
    # 30 lines of code to move and delete endpoints
    ...
    return tfdata

# In cloud_config_aws.py
AWS_SPECIAL_RESOURCES = {
    "aws_vpc_endpoint": "aws_handle_vpc_endpoint",
}
```

### After (Config-Driven)
```python
# In resource_handler_configs_aws.py
"aws_vpc_endpoint": {
    "description": "Move VPC endpoints into VPC parent and delete endpoint nodes",
    "transformations": [
        {"operation": "move_to_parent", "params": {...}},
        {"operation": "delete_nodes", "params": {...}},
    ],
},
```

**Result**: 30 lines of Python → 10 lines of config (67% reduction)
