# Handler Configuration Guide

## Overview

TerraVision uses a unified hybrid configuration-driven approach for all resource handlers. Handlers can be:
1. **Pure config-driven**: Use only transformation building blocks (declarative)
2. **Hybrid**: Use transformations + custom Python function (best of both worlds)
3. **Pure function**: Use only custom Python function (for complex logic)

All handlers are defined in `modules/config/resource_handler_configs_<provider>.py` with automatic provider detection.

## ⚠️ CRITICAL: Validate Baseline First!

**Before implementing ANY handler**, you MUST prove that the baseline Terraform graph parsing is insufficient.

### Validation Process

**Step 1: Generate Baseline**
```bash
# Create test Terraform code for the resource type
cd tests/fixtures/aws_terraform/test_resource/
# Run TerraVision WITHOUT any custom handler
# IMPORTANT: Use --debug to save tfdata.json for test reuse
poetry run python ../../../terravision.py graphdata --source . --outfile baseline.json --debug
# The --debug flag creates tfdata.json which can be reused:
# poetry run python ../../../terravision.py graphdata --source tfdata.json --outfile output.json
```

**Step 2: Analyze Baseline Output**
- ✅ Are resources visible with correct icons?
- ✅ Are connections present (arrows show Terraform dependencies)?
- ✅ Is hierarchy clear (VPC → subnet → resources)?
- ✅ Can users understand the architecture?

**Step 3: Decision**
- If ALL checks pass → **STOP! No handler needed.** Trust the baseline.
- If ANY check fails → Document specific issues, proceed cautiously

### Real Example: API Gateway

**Baseline Output** (no handler):
```
Lambda → Integration → Method → Resource → REST API
```

**Analysis**:
- ✅ All resources visible
- ✅ Connections show data flow
- ✅ Hierarchy is clear
- ✅ Users understand: Lambda serves API Gateway

**Decision**: ❌ **Handler NOT needed** - baseline is sufficient!

**Mistake Made**: Tried to parse integration URIs to create "better" diagrams
**Result**: Added complexity, created unhelpful placeholder nodes
**Lesson**: Baseline was already good - handler made it worse!

### Counter-Example: Security Groups

**Baseline Output** (no handler):
```
EC2 → Security Group (simple dependency arrow)
```

**Analysis**:
- ✅ Resources visible
- ❌ No ingress/egress rules shown
- ❌ Can't see which SG allows which traffic
- ❌ Users can't understand network security

**Decision**: ✅ **Handler needed** - baseline insufficient!

**Implementation**: Parse SG rules, create directional arrows with port/protocol labels

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

By default, when a resource pattern matches:

1. **Config-driven transformations** are applied first (if `transformations` key exists)
2. **Additional handler function** is called second (if `additional_handler_function` key exists)

You can reverse this order using the `handler_execution_order` parameter:

```python
"handler_execution_order": "before",  # Run custom function BEFORE transformations
"handler_execution_order": "after",   # Run custom function AFTER transformations (default)
```

**Use Case for "before"**: When transformations need prepared metadata from the custom function.

**Example:**
```python
"aws_subnet": {
    "handler_execution_order": "before",  # Run metadata prep FIRST
    "additional_handler_function": "aws_prepare_subnet_az_metadata",  # Copies metadata
    "transformations": [
        {"operation": "insert_intermediate_node", ...},  # Uses prepared metadata
    ],
}
```

This allows you to:
- Reuse common transformations across handlers
- Only write custom code for unique logic
- Control execution flow for complex scenarios
- Gradually migrate complex handlers to config-driven approach

## Available Transformers

All transformers are defined in `modules/resource_transformers.py`. Total: **24 generic transformers**.

### Resource Expansion
- **expand_to_numbered_instances** - Create numbered instances per subnet (~1, ~2, ~3)
- **clone_with_suffix** - Duplicate resources with numbered suffixes

### Resource Grouping
- **create_group_node** - Create container/group nodes
- **group_shared_services** - Group shared services together (IAM, CloudWatch, etc.)
- **move_to_parent** - Move resources between parents
- **move_to_vpc_parent** - Move resources to VPC level

**⚠️ For Resource Consolidation**: Use `AWS_CONSOLIDATED_NODES` in `cloud_config_aws.py` instead of transformers. See "Resource Consolidation" section below.

### Connections
- **link_resources** - Create connections between resources
- **unlink_resources** - Remove connections between resources
- **unlink_from_parents** - Remove child from parent connections
- **redirect_connections** - Redirect connections to different resources
- **redirect_to_security_group** - Redirect to security groups if present
- **match_by_suffix** - Link resources with matching ~N suffixes
- **link_via_shared_child** - Create direct links when resources share a child
- **link_by_metadata_pattern** - Create links based on metadata patterns
- **create_transitive_links** - Create transitive connections through intermediates
- **bidirectional_link** - Create bidirectional connections between resources
- **replace_connection_targets** - Replace old connection targets with new ones

### Graph Manipulation
- **insert_intermediate_node** - Insert intermediate nodes between parents and children
  - Example: VPC→subnet becomes VPC→AZ→subnet
  - Handles node creation, metadata copying, and connection rewiring

### Metadata Operations
- **propagate_metadata** - Copy metadata from source to target resources
  - Supports copying specific keys or all keys
  - Supports `propagate_to_children: true` to copy to all children
  - Direction: "forward", "reverse", or "bidirectional"

### Cleanup
- **delete_nodes** - Delete nodes from graph

### Variants
- **apply_resource_variants** - Apply resource type variants (e.g., Fargate vs EC2)
- **apply_all_variants** - Apply all variants globally

### Pipeline
- **apply_transformation_pipeline** - Execute sequence of transformations

## Resource Consolidation

**⚠️ IMPORTANT**: When you need to consolidate multiple resources into a single node (e.g., merge all `aws_api_gateway_rest_api.*` into one `aws_api_gateway_rest_api.api` node), **DO NOT use a transformer**. Instead, add an entry to `AWS_CONSOLIDATED_NODES` in `cloud_config_aws.py`.

### Why Use AWS_CONSOLIDATED_NODES?

1. **Simpler**: Declarative configuration in one central location
2. **More maintainable**: All consolidation rules in one place
3. **Existing mechanism**: Uses the proven consolidation system already in TerraVision
4. **Automatic**: Runs before handlers, so handlers see consolidated nodes

### How to Consolidate Resources

**❌ WRONG - Don't use transformers:**
```python
# DON'T DO THIS!
"aws_api_gateway_rest_api": {
    "transformations": [
        {
            "operation": "consolidate_into_single_node",  # This transformer was removed!
            "params": {
                "resource_pattern": "aws_api_gateway_rest_api",
                "target_node_name": "aws_api_gateway_rest_api.api",
            },
        },
    ],
}
```

**✅ CORRECT - Add to AWS_CONSOLIDATED_NODES:**
```python
# In modules/config/cloud_config_aws.py
AWS_CONSOLIDATED_NODES = [
    # ... existing entries ...
    {
        "aws_api_gateway_rest_api": {
            "resource_name": "aws_api_gateway_rest_api.api",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
            "edge_service": True,
        }
    },
]
```

### AWS_CONSOLIDATED_NODES Format

```python
{
    "resource_prefix": {  # Pattern to match (e.g., "aws_api_gateway_rest_api")
        "resource_name": "consolidated.node.name",  # Final consolidated name
        "import_location": "resource_classes.aws.category",  # Icon path
        "vpc": True/False,  # Whether resource is inside VPC
        "edge_service": True/False,  # (Optional) Whether it's an edge service
    }
}
```

### When to Use Consolidation

Use `AWS_CONSOLIDATED_NODES` when:
- Multiple resources of the same type should appear as one node
- You want to merge `aws_foo_bar.x`, `aws_foo_bar.y`, `aws_foo_bar.z` → `aws_foo_bar.consolidated`
- Examples: API Gateway (many integration/method resources → 1 API), CloudWatch logs, Route53 records

**Note**: After consolidation, you can still use handler transformations to add connections, delete sub-resources, etc.

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
- `aws_db_subnet_group` - Move to VPC, redirect to security groups
- `aws_` (pattern match) - Group shared services

**Hybrid** (3 handlers):
- `aws_subnet` - Metadata prep (before) + `insert_intermediate_node` transformer
  - Creates VPC→AZ→subnet structure
  - 51 lines → 39 lines (24% reduction)
- `aws_cloudfront_distribution` - Link transformers + custom origin parsing
- `aws_efs_file_system` - Bidirectional link transformer + custom cleanup logic

**Pure function** (6 handlers - too complex for config):
- `aws_appautoscaling_target` - Count propagation + connection redirection
  - Logic too specific: conditional copying, policy filtering
  - Improved: removed dangerous `try/except: pass`, added explicit checks
- `aws_security_group` - Complex reverse relationship logic
- `aws_lb` - Metadata parsing and connection redirection
- `aws_ecs` - Chart-specific conditional logic
- `aws_eks` - Complex cluster grouping and Karpenter detection
- `helm_release` - Chart-specific conditional logic

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

## Decision Guide: Which Handler Type to Use?

Use this decision tree to determine the best approach for a new or existing handler:

### Start Here

```
Does the handler involve complex conditional logic?
├─ YES → Is the logic domain-specific (can't be generalized)?
│  ├─ YES → Use Pure Function
│  │         Examples: Security group reverse relationships,
│  │                   autoscaling count propagation with policy filtering
│  └─ NO → Can you break it into generic operations + custom logic?
│     ├─ YES → Use Hybrid
│     │         Examples: Subnet (metadata prep + insert intermediate node),
│     │                   EFS (bidirectional link + custom cleanup)
│     └─ NO → Use Pure Config-Driven
│               Examples: VPC endpoint (move + delete),
│                         EKS node group (expand to numbered instances)
└─ NO → Can the entire operation be expressed with existing transformers?
   ├─ YES → Use Pure Config-Driven
   │         Examples: DB subnet group (move + redirect),
   │                   Random string (delete nodes)
   └─ NO → Would creating a new generic transformer be useful?
      ├─ YES → Create transformer, then use Pure Config-Driven
      │         Examples: insert_intermediate_node, propagate_metadata
      └─ NO → Use Hybrid or Pure Function
                Examples: Custom domain parsing, chart-specific logic
```

### Quick Reference

| Characteristic | Pure Config | Hybrid | Pure Function |
|----------------|-------------|--------|---------------|
| **Code lines** | 0 Python, 10-20 config | 20-40 Python, 10-20 config | 50-150 Python, 5 config |
| **Complexity** | Simple operations | Medium complexity | High complexity |
| **Reusability** | 100% (all generic) | 50-80% (transformers reusable) | 0% (all custom) |
| **Testability** | Test transformers once | Test function + transformers | Test entire function |
| **Maintainability** | Easiest (declarative) | Medium (clear separation) | Hardest (procedural) |
| **Use When** | Simple, repetitive ops | Common ops + unique logic | Complex conditional logic |

### Red Flags for Pure Config

Avoid Pure Config if handler has ANY of these:
- ❌ Conditional logic based on resource properties (if/else)
- ❌ Complex loops with nested conditions
- ❌ Dynamic naming with custom logic (beyond simple patterns)
- ❌ Try/except error handling
- ❌ Metadata manipulation with complex rules
- ❌ Domain-specific parsing (URLs, domains, ARNs)

### Green Lights for Pure Config

Use Pure Config if handler does ALL operations with existing transformers:
- ✅ Move resources between parents
- ✅ Create/delete nodes
- ✅ Link/unlink resources
- ✅ Expand to numbered instances
- ✅ Redirect connections
- ✅ Copy metadata (simple patterns)
- ✅ Apply variants
- ✅ Group resources

### When to Choose Hybrid

Choose Hybrid when:
- ✅ Most operations can use transformers
- ✅ Custom logic is isolated (metadata prep, name generation)
- ✅ Custom function is simple (<50 lines)
- ✅ Clear separation between generic and custom operations
- ✅ Custom function prepares data for transformers (or vice versa)

**Real Example - Subnet Handler:**
```python
# Custom function (21 lines): Copy metadata for transformer to use
def aws_prepare_subnet_az_metadata(tfdata):
    for subnet in subnets:
        tfdata["meta_data"][subnet]["availability_zone"] = original["availability_zone"]
        tfdata["meta_data"][subnet]["region"] = original["region"]
    return tfdata

# Transformer (10 lines config): Use prepared metadata to create AZ nodes
"transformations": [
    {
        "operation": "insert_intermediate_node",
        "params": {
            "parent_pattern": "aws_vpc",
            "child_pattern": "aws_subnet",
            "intermediate_node_generator": "generate_az_node_name",
        },
    },
]
```

### When to Keep as Pure Function

Keep as Pure Function when:
- ❌ Transformers would require too many steps (>5 transformations)
- ❌ Logic has complex conditionals that can't be expressed declaratively
- ❌ Custom code is <50 lines and very specific to this resource type
- ❌ Attempting to use transformers causes edge cases or bugs
- ❌ The logic is well-tested and stable (don't fix what isn't broken)

**Real Example - Autoscaling Handler:**
```python
# Kept as Pure Function because:
# 1. Conditional copying (only if ASG doesn't have count)
# 2. Selective copying (services yes, policies no)
# 3. Complex shared-child detection
# 4. Logic is specific to autoscaling, not generalizable

def aws_handle_autoscaling(tfdata):
    for asg in asg_resources:
        if tfdata["meta_data"].get(asg, {}).get("count"):  # Conditional
            continue
        for service in scaler_links:
            if "policy" not in service.lower():  # Selective filtering
                # Copy count logic...
    # Connection redirection logic...
    return tfdata
```

## Best Practices

1. **Start with Pure Config**: Always try Pure Config first. If you can't express the logic with existing transformers, consider Hybrid or Pure Function.

2. **Create Transformers for Common Patterns**: If you see a pattern used in multiple handlers, create a generic transformer.

3. **Keep Functions Small**: If custom function is >100 lines, consider breaking it into multiple transformers or helper functions.

4. **Document Handler Type**: Always include `"description"` explaining what the handler does and why it's that type.

5. **Test Behavior Preservation**: When refactoring, ensure tests pass without changing expected output.

6. **Use `handler_execution_order`**: When transformers need prepared data, run custom function first with `"handler_execution_order": "before"`.

7. **Avoid Over-Engineering**: Don't create transformers for one-off operations. Pure Function is fine for unique, complex logic.
