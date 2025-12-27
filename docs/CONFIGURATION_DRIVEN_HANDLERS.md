# Configuration-Driven Resource Handler Architecture

## Overview

This document describes the hybrid configuration-driven approach for resource handlers in TerraVision. Handlers can be:
1. **Pure config-driven**: Use only declarative transformation pipelines
2. **Hybrid**: Use config transformations + custom Python functions
3. **Pure function**: Use only custom Python functions (for complex logic)

All handlers are defined in `modules/config/resource_handler_configs_<provider>.py` with automatic provider detection.

## Problem Statement

The original `resource_handlers_aws.py` contained 30+ handler functions with repetitive patterns:
- Expanding resources to numbered instances (~1, ~2, ~3) across subnets
- Replacing icons based on metadata variants (e.g., Fargate vs EC2 ECS)
- Creating group nodes and moving resources into them
- Linking/unlinking resources based on patterns
- Deleting intermediate nodes

This led to:
- Code duplication across handlers
- Difficult maintenance when adding new resource types
- Hard to understand transformation logic scattered across functions

## Solution: Hybrid Handler Architecture

### Core Transformers (`resource_transformers.py`)

24 reusable transformation operations organized by category:

**Resource Expansion:**
1. **expand_to_numbered_instances** - Create ~1, ~2, ~3 instances per subnet
2. **clone_with_suffix** - Duplicate resources with numbered suffixes

**Resource Grouping:**
3. **create_group_node** - Add container/group nodes
4. **group_shared_services** - Group shared services together (IAM, CloudWatch, etc.)
5. **move_to_parent** - Relocate resources in hierarchy
6. **move_to_vpc_parent** - Move resources to VPC level
7. **consolidate_into_single_node** - Merge multiple resources into one

**Connections:**
8. **link_resources** - Add connections between resources
9. **unlink_resources** - Remove connections
10. **unlink_from_parents** - Remove child from parent connections
11. **redirect_connections** - Change parent references
12. **redirect_to_security_group** - Redirect to security groups if present
13. **match_by_suffix** - Link resources with same ~N suffix
14. **link_via_shared_child** - Create direct links when resources share a child
15. **link_by_metadata_pattern** - Create links based on metadata patterns
16. **create_transitive_links** - Create transitive connections through intermediates
17. **bidirectional_link** - Create bidirectional connections between resources
18. **replace_connection_targets** - Replace old connection targets with new ones

**Graph Manipulation:**
19. **insert_intermediate_node** - Insert intermediate nodes between parents and children

**Metadata Operations:**
20. **propagate_metadata** - Copy metadata from source to target resources

**Cleanup:**
21. **delete_nodes** - Remove resources from graph

**Variants:**
22. **apply_resource_variants** - Change resource type based on metadata
23. **apply_all_variants** - Apply all variants globally

**Pipeline:**
24. **apply_transformation_pipeline** - Execute sequence of transformations

### Configuration Structure (`resource_handler_configs_<provider>.py`)

Each handler is defined as:

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

**Execution Order**: Config transformations run first, then additional handler function (if present).

**Automatic Function Resolution**: Parameters ending in `_function` or `_generator` are automatically resolved from string names to actual function references. This allows config files to specify callable parameters without importing modules.

Example:
```python
"transformations": [
    {
        "operation": "insert_intermediate_node",
        "params": {
            "intermediate_node_generator": "generate_az_node_name",  # String
        },
    },
]
# Automatically resolved to: handlers_aws.generate_az_node_name
```

## Migration Examples

### Example 1: Pure Config-Driven Handler

**Before (Python function):**
```python
def aws_handle_vpc_endpoint(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    # Move VPC endpoints from subnets to VPC parent
    vpc_endpoints = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_vpc_endpoint"
    )
    for endpoint in vpc_endpoints:
        # ... 30 lines of logic
    return tfdata
```

**After (Configuration):**
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
}
```

**Result**: 30 lines of Python → 10 lines of config (67% reduction)

### Example 2: Hybrid Handler (Hypothetical)

**Concept**: Use config for common operations, custom function for complex logic

```python
"aws_complex_resource": {
    "description": "Handle complex resource with both config and custom logic",
    "transformations": [
        {
            "operation": "expand_to_numbered_instances",
            "params": {
                "resource_pattern": "aws_complex_resource",
                "subnet_key": "subnet_ids",
            },
        },
    ],
    "additional_handler_function": "aws_handle_complex_custom_logic",
},
```

**Custom function** (in `resource_handlers_aws.py`):
```python
def aws_handle_complex_custom_logic(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle complex logic that can't be expressed with transformers."""
    # Config already expanded resources to numbered instances
    # Now apply complex conditional logic
    ...
    return tfdata
```

### Example 3: Pure Function Handler

**When to use**: Complex logic that can't be expressed with transformers

```python
"aws_security_group": {
    "description": "Process security group relationships and reverse connections",
    "additional_handler_function": "aws_handle_sg",
},
```

**Why pure function**: Security groups require:
- Bidirectional relationship manipulation
- Dynamic name generation based on connections
- Complex conditional logic for ingress/egress rules
- Metadata parsing and propagation

## Benefits

### 1. Maintainability
- Add new resource types by editing config, not writing Python
- Clear separation of "what" (config) from "how" (transformers)
- Easy to understand transformation sequence
- Hybrid approach allows gradual migration

### 2. Consistency
- All handlers use same building blocks
- Predictable behavior across resource types
- Easier to test and debug
- Single source of truth for handler metadata

### 3. Extensibility
- Add new transformers without touching existing handlers
- Compose complex handlers from simple operations
- Reuse patterns across different resource types
- Mix config and custom code as needed

### 4. Documentation
- Configuration is self-documenting
- Description field explains purpose
- Transformation sequence shows exact steps
- Handler type (config/hybrid/function) is clear

## Integration with Existing Code

### Execution Flow

```python
# In graphmaker.py
def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute all configured handlers in sequence."""
    
    # Load provider-specific handler configs
    handler_configs = _load_handler_configs(tfdata)
    
    for resource_pattern, config in handler_configs.items():
        # Check if this resource type exists in graph
        if helpers.list_of_dictkeys_containing(tfdata["graphdict"], resource_pattern):
            # Step 1: Apply config-driven transformations (if present)
            if "transformations" in config:
                tfdata = apply_transformation_pipeline(
                    tfdata, 
                    config["transformations"]
                )
            
            # Step 2: Call additional handler function (if present)
            if "additional_handler_function" in config:
                handler_func = getattr(resource_handlers, config["additional_handler_function"])
                tfdata = handler_func(tfdata)
    
    return tfdata
```

### Handler Types

**Pure Config-Driven** (7 handlers):
- `aws_eks_node_group` - Expand node groups per subnet
- `aws_eks_fargate_profile` - Expand Fargate profiles per subnet
- `aws_autoscaling_group` - Link ASG to subnets
- `random_string` - Disconnect random resources
- `aws_vpc_endpoint` - Move to VPC and delete
- `aws_db_subnet_group` - Move to VPC, redirect to security groups
- `aws_` (shared services) - Group shared services

**Hybrid** (3 handlers):
- `aws_subnet` - Metadata prep (before) + insert_intermediate_node transformer
- `aws_cloudfront_distribution` - Link transformers + custom origin parsing
- `aws_efs_file_system` - Bidirectional link transformer + custom cleanup logic

**Pure Function** (6 handlers - too complex for config):
- `aws_appautoscaling_target` - Count propagation + connection redirection
- `aws_security_group` - Complex reverse relationship logic
- `aws_lb` - Metadata parsing and connection redirection
- `aws_ecs` - Chart-specific conditional logic
- `aws_eks` - Complex cluster grouping and Karpenter detection
- `helm_release` - Chart-specific conditional logic

## Adding New Resource Types

### Step 1: Identify Pattern
Determine which approach is needed:
- **Pure config**: Simple operations (expand, link, move, delete)
- **Hybrid**: Common operations + unique logic
- **Pure function**: Complex logic that can't be expressed with transformers

### Step 2: Add Configuration
Add entry to `RESOURCE_HANDLER_CONFIGS` in `modules/config/resource_handler_configs_<provider>.py`:

**Pure config example:**
```python
"aws_new_resource": {
    "description": "Handle new resource type",
    "transformations": [
        {
            "operation": "expand_to_numbered_instances",
            "params": {
                "resource_pattern": "aws_new_resource",
                "subnet_key": "subnet_ids",
            },
        },
    ],
}
```

**Hybrid example:**
```python
"aws_new_resource": {
    "description": "Handle new resource type",
    "transformations": [
        {"operation": "expand_to_numbered_instances", "params": {...}},
    ],
    "additional_handler_function": "aws_handle_new_resource_custom",
}
```

**Pure function example:**
```python
"aws_new_resource": {
    "description": "Handle new resource type with complex logic",
    "additional_handler_function": "aws_handle_new_resource",
}
```

### Step 3: Test
Run TerraVision with Terraform code containing the new resource type.

## Future Enhancements

### Conditional Transformations
```python
{
    "operation": "expand_to_numbered_instances",
    "condition": {
        "metadata_key": "multi_az",
        "equals": True,
    },
    "params": {...},
}
```

### Parameterized Transformations
```python
{
    "operation": "create_group_node",
    "params": {
        "group_name": "aws_account.{cluster_name}_control_plane",
        "children": ["aws_eks_cluster.{cluster_name}"],
    },
}
```

### Validation Rules
```python
{
    "operation": "link_resources",
    "validate": {
        "source_exists": True,
        "target_exists": True,
    },
    "params": {...},
}
```

## Testing Strategy

### Unit Tests
Test each transformer independently:
```python
def test_expand_to_numbered_instances():
    tfdata = {
        "graphdict": {
            "aws_eks_node_group.workers": [],
            "aws_subnet.private_1": [],
            "aws_subnet.private_2": [],
        },
        "meta_data": {
            "aws_eks_node_group.workers": {
                "subnet_ids": ["subnet-1", "subnet-2"]
            },
            "aws_subnet.private_1": {"id": "subnet-1"},
            "aws_subnet.private_2": {"id": "subnet-2"},
        },
    }
    
    result = expand_to_numbered_instances(
        tfdata, 
        "aws_eks_node_group",
        "subnet_ids"
    )
    
    assert "aws_eks_node_group.workers~1" in result["graphdict"]
    assert "aws_eks_node_group.workers~2" in result["graphdict"]
```

### Integration Tests
Test complete handler configurations:
```python
def test_eks_node_group_handler():
    tfdata = load_test_data("eks_cluster.json")
    config = AWS_RESOURCE_HANDLER_CONFIGS["aws_eks_node_group"]
    
    result = apply_transformation_pipeline(tfdata, config["transformations"])
    
    # Verify expected output
    assert_node_groups_expanded(result)
    assert_linked_to_subnets(result)
```

### Regression Tests
Compare output with original handler functions:
```python
def test_backward_compatibility():
    tfdata = load_test_data("complex_architecture.json")
    
    # Old approach
    old_result = match_node_groups_to_subnets(tfdata.copy())
    
    # New approach
    new_result = apply_transformation_pipeline(
        tfdata.copy(),
        AWS_RESOURCE_HANDLER_CONFIGS["aws_eks_node_group"]["transformations"]
    )
    
    assert old_result == new_result
```

## Performance Considerations

### Optimization Opportunities
1. **Lazy Evaluation** - Only execute handlers for resources present in graph
2. **Caching** - Cache pattern matching results
3. **Parallel Execution** - Run independent transformations in parallel
4. **Early Exit** - Skip transformations if preconditions not met

### Benchmarking
```python
import time

def benchmark_handler(handler_name, tfdata):
    start = time.time()
    config = AWS_RESOURCE_HANDLER_CONFIGS[handler_name]
    result = apply_transformation_pipeline(tfdata, config["transformations"])
    elapsed = time.time() - start
    print(f"{handler_name}: {elapsed:.3f}s")
    return result
```

## Conclusion

The hybrid configuration-driven approach reduces code by ~70% for simple handlers while maintaining flexibility for complex logic:
- **Readability** - Clear transformation sequences or explicit function calls
- **Maintainability** - Edit config for simple cases, write code only when needed
- **Extensibility** - Compose new handlers from existing blocks or custom functions
- **Testability** - Test transformers independently, test functions in isolation
- **Flexibility** - Choose the right tool (config vs code) for each handler

This architecture makes TerraVision easier to extend with new cloud services while keeping complex logic maintainable.
