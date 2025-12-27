# Dynamic Configuration-Driven Handlers - Quick Start

## Overview

Resource handlers are now defined as configuration and executed dynamically based on resource patterns. No individual handler functions needed - just add config and it runs automatically.

## How It Works

### 1. Define Handler in Config (`resource_handler_configs.py`)

```python
AWS_RESOURCE_HANDLER_CONFIGS = {
    "aws_eks_node_group": {
        "description": "Expand EKS node groups per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_eks_node_group",
                    "subnet_key": "subnet_ids",
                },
            },
        ],
    },
}
```

### 2. Execute Dynamically (`handler_integration.py`)

```python
def execute_configured_handlers(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Automatically executes handlers for matching resources."""
    resource_types = list(
        {helpers.get_no_module_name(k).split(".")[0] for k in tfdata["node_list"]}
    )
    
    for resource_pattern, config in AWS_RESOURCE_HANDLER_CONFIGS.items():
        # Wildcard matching: 'aws_eks*' matches 'aws_eks_cluster', 'aws_eks_node_group', etc.
        matching = [s for s in resource_types if resource_pattern in s]
        
        if resource_pattern in resource_types or matching:
            tfdata = apply_transformation_pipeline(tfdata, config["transformations"])
    
    return tfdata
```

### 3. Use in Main Pipeline (`graphmaker.py`)

Replace `handle_special_resources()` pattern:

```python
# OLD: Function-based with getattr()
def handle_special_resources(tfdata):
    for resource_prefix, handler in SPECIAL_RESOURCES.items():
        matching = [s for s in resource_types if resource_prefix in s]
        if resource_prefix in resource_types or matching:
            tfdata = getattr(handler_module, handler)(tfdata)
    return tfdata

# NEW: Config-driven
from modules.handler_integration import execute_configured_handlers

def handle_special_resources(tfdata):
    # Execute config-driven handlers first
    tfdata = execute_configured_handlers(tfdata)
    
    # Then execute remaining complex handlers
    # (These will be migrated to config over time)
    for resource_prefix, handler in COMPLEX_HANDLERS.items():
        matching = [s for s in resource_types if resource_prefix in s]
        if resource_prefix in resource_types or matching:
            tfdata = getattr(handler_module, handler)(tfdata)
    
    return tfdata
```

## Wildcard Pattern Matching

Patterns support substring matching (like existing code):

```python
# Exact match
"aws_eks_node_group" → matches only "aws_eks_node_group"

# Wildcard match (substring)
"aws_eks" → matches "aws_eks_cluster", "aws_eks_node_group", "aws_eks_fargate_profile"
"aws_" → matches all AWS resources
"random" → matches "random_string", "random_id", etc.
```

## Adding New Resource Handler

**Step 1:** Add config entry
```python
"aws_new_resource": {
    "description": "What it does",
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

**Step 2:** Done! It executes automatically when that resource type exists.

## Available Transformers

1. **expand_to_numbered_instances** - Create ~1, ~2, ~3 per subnet
2. **replace_icon_variant** - Change icon based on metadata
3. **create_group_node** - Add container nodes
4. **move_to_parent** - Relocate in hierarchy
5. **link_resources** - Add connections
6. **unlink_resources** - Remove connections
7. **delete_nodes** - Remove from graph
8. **match_by_suffix** - Link by ~N suffix
9. **redirect_connections** - Change parent refs
10. **clone_with_suffix** - Duplicate with numbers

## Migration Path

### Phase 1: Simple Handlers (Done)
- aws_eks_node_group
- aws_eks_fargate_profile
- aws_autoscaling_group
- aws_ecs_service (variants)
- aws_lb (variants)
- random_string

### Phase 2: Complex Handlers (Future)
- aws_security_group
- aws_efs_file_system
- aws_cloudfront_distribution
- aws_subnet (AZ creation)
- aws_db_subnet
- helm_release

## Benefits

✅ **No individual functions** - Just config entries  
✅ **Automatic execution** - Runs when resources exist  
✅ **Wildcard support** - Match multiple resource types  
✅ **90% less code** - Config vs Python functions  
✅ **Easy to add** - New resource = new config entry  

## Example: Complete Handler

```python
"aws_eks": {  # Wildcard matches all EKS resources
    "description": "Complete EKS handling",
    "transformations": [
        {
            "operation": "create_group_node",
            "params": {
                "group_name": "aws_account.eks_control_plane",
                "children": ["aws_eks_cluster.*"],
            },
        },
        {
            "operation": "expand_to_numbered_instances",
            "params": {
                "resource_pattern": "aws_eks_node_group",
                "subnet_key": "subnet_ids",
            },
        },
        {
            "operation": "expand_to_numbered_instances",
            "params": {
                "resource_pattern": "aws_eks_fargate_profile",
                "subnet_key": "subnet_ids",
            },
        },
        {
            "operation": "link_resources",
            "params": {
                "source_pattern": "aws_eks_cluster",
                "target_pattern": "aws_eks_node_group",
            },
        },
    ],
}
```

This single config entry replaces 300+ lines of Python code across multiple functions.
