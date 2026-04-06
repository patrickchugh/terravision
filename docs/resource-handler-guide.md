# Resource Handler Guide

## Table of Contents

1. [Overview](#overview)
2. [Critical: Validate Baseline First](#critical-validate-baseline-first)
   - [Validation Process](#validation-process)
   - [Real Example: API Gateway](#real-example-api-gateway)
   - [Counter-Example: Security Groups](#counter-example-security-groups)
3. [Handler Architecture](#handler-architecture)
   - [Three Handler Types](#three-handler-types)
   - [Why Hybrid Architecture?](#why-hybrid-architecture)
4. [Configuration Structure](#configuration-structure)
   - [Basic Structure](#basic-structure)
   - [Execution Order](#execution-order)
   - [Automatic Function Resolution](#automatic-function-resolution)
5. [Handler Types in Detail](#handler-types-in-detail)
   - [Pure Config-Driven Handler](#1-pure-config-driven-handler)
   - [Hybrid Handler](#2-hybrid-handler)
   - [Pure Function Handler](#3-pure-function-handler)
6. [Available Transformers](#available-transformers)
   - [Resource Expansion](#resource-expansion)
   - [Resource Grouping](#resource-grouping)
   - [Connections](#connections)
   - [Graph Manipulation](#graph-manipulation)
   - [Metadata Operations](#metadata-operations)
   - [Cleanup](#cleanup)
   - [Variants](#variants)
   - [Pipeline](#pipeline)
7. [Resource Consolidation](#resource-consolidation)
8. [Decision Guide](#decision-guide)
   - [Decision Tree](#decision-tree)
   - [Quick Reference Table](#quick-reference-table)
   - [Red Flags and Green Lights](#red-flags-and-green-lights)
9. [Migration Examples](#migration-examples)
10. [Architecture Components](#architecture-components)
11. [Execution Flow](#execution-flow)
12. [Adding New Resource Types](#adding-new-resource-types)
13. [Testing Strategy](#testing-strategy)
14. [Performance Considerations](#performance-considerations)
15. [Best Practices](#best-practices)
16. [Current State (AWS)](#current-state-aws)

---

## Overview

TerraVision uses a **unified hybrid configuration-driven approach** for all resource handlers. This architecture allows handlers to be implemented in three ways:

1. **Pure config-driven**: Use only declarative transformation building blocks (70% code reduction)
2. **Hybrid**: Use transformations + custom Python function (best of both worlds)
3. **Pure function**: Use only custom Python function (for complex logic)

All handlers are defined in `modules/config/resource_handler_configs_<provider>.py` with automatic provider detection.

### Problem Statement

The original `resource_handlers_aws.py` contained 30+ handler functions with repetitive patterns:
- Expanding resources to numbered instances (~1, ~2, ~3) across subnets
- Replacing icons based on metadata variants (e.g., Fargate vs EC2 ECS)
- Creating group nodes and moving resources into them
- Linking/unlinking resources based on patterns
- Deleting intermediate nodes

This led to:
- Code duplication across handlers and cloud providers
- Required implementing equal or greater number of handlers doing similiar processes for each new cloud provider when added
- Difficult maintenance when adding new resource types
- Hard to understand transformation logic scattered across functions


### Solution

The hybrid handler architecture provides:
- **24 reusable transformation operations** in `modules/resource_transformers.py`
- **Configuration-driven handler definitions** in provider-specific config files
- **Flexible execution**: Use config, code, or both as needed
- **70% code reduction** for simple handlers (360 lines → 85 lines for 7 AWS handlers)

---

## Critical: Validate Baseline First

**⚠️ IMPORTANT**: Before implementing ANY handler, you MUST prove that the baseline Terraform graph parsing is insufficient.

### Validation Process

**Step 1: Generate Baseline**
```bash
# Create test Terraform code for the resource type
cd tests/fixtures/aws_terraform/test_resource/

# Run TerraVision WITHOUT any custom handler
# IMPORTANT: Use --debug to save tfdata.json for test reuse
poetry run python ../../../terravision.py graphdata --source . --outfile baseline.json --debug

# The --debug flag creates tfdata.json which can be reused:
poetry run python ../../../terravision.py graphdata --source tfdata.json --outfile output.json
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

---

## Handler Architecture

### Three Handler Types

#### 1. Pure Config-Driven (7 AWS handlers)

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

#### 2. Hybrid (3 AWS handlers)

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

**Current AWS handlers**:
- `aws_subnet` - Metadata prep (before) + insert_intermediate_node transformer (51→39 lines, 24% reduction)
- `aws_cloudfront_distribution` - Link transformers + custom origin parsing
- `aws_efs_file_system` - Bidirectional link transformer + custom cleanup logic

#### 3. Pure Function (6 AWS handlers)

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

**Current AWS specific handlers**:
- `aws_appautoscaling_target` - Count propagation + connection redirection
- `aws_security_group` - Reverse relationships
- `aws_lb` - Metadata parsing
- `aws_ecs` - Conditional logic
- `aws_eks` - Cluster grouping + Karpenter
- `helm_release` - Chart-specific logic

### Why Hybrid Architecture?

**Problem**: Some handlers are simple (move, link, delete), others are complex (conditional logic, dynamic naming, metadata manipulation).

**Solution**: Use the right tool for each handler:
- **Config** for simple, repetitive operations (70% code reduction)
- **Functions** for complex logic that can't be expressed declaratively
- **Both** when you need common operations + unique logic

---

## Configuration Structure

### Basic Structure

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
        "handler_execution_order": "after",  # Optional: "before" or "after" (default)
    },
}
```

### Execution Order

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

---

## Handler Types in Detail

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
}
```

**Result**: 30 lines of Python → 10 lines of config (67% reduction)

### 2. Hybrid Handler

Uses transformations for common operations, then custom function for complex logic.

**Example: Subnet Handler**
```python
"aws_subnet": {
    "description": "Create availability zone nodes and link to subnets",
    "handler_execution_order": "before",  # Run custom function FIRST
    "additional_handler_function": "aws_prepare_subnet_az_metadata",
    "transformations": [
        {
            "operation": "unlink_from_parents",
            "params": {
                "resource_pattern": "aws_subnet",
                "parent_filter": "aws_vpc",
            },
        },
        {
            "operation": "insert_intermediate_node",
            "params": {
                "parent_pattern": "aws_vpc",
                "child_pattern": "aws_subnet",
                "intermediate_node_generator": "generate_az_node_name",
                "create_if_missing": True,
            },
        },
    ],
}
```

**Custom function** (in `resource_handlers_aws.py`):
```python
def aws_prepare_subnet_az_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare metadata for transformer to use."""
    for subnet in subnets:
        tfdata["meta_data"][subnet]["availability_zone"] = original["availability_zone"]
        tfdata["meta_data"][subnet]["region"] = original["region"]
    return tfdata
```

**Result**: 51 lines → 39 lines (24% reduction)

### 3. Pure Function Handler

Uses only custom Python function for complex logic that can't be expressed with transformers.

**Example: Security Group Handler**
```python
"aws_security_group": {
    "description": "Process security group relationships and reverse connections",
    "additional_handler_function": "aws_handle_sg",
}
```

**Why pure function**: Security groups require:
- Bidirectional relationship manipulation
- Dynamic name generation based on connections
- Complex conditional logic for ingress/egress rules
- Metadata parsing and propagation

---

## Available Transformers

All transformers are defined in `modules/resource_transformers.py`. Total: **23 generic transformers** + 1 pipeline orchestrator.

### Resource Expansion (2 transformers)

- **expand_to_numbered_instances** - Create numbered instances per subnet (~1, ~2, ~3)
  - Expands resources across multiple subnets with instance numbers
  - Example: `aws_eks_node_group.workers` → `aws_eks_node_group.workers~1`, `aws_eks_node_group.workers~2`
  - Parameters: `resource_pattern`, `subnet_key`, `skip_if_numbered`, `inherit_connections`
  
- **clone_with_suffix** - Duplicate resources with numbered suffixes
  - Creates copies of resources with incremental numbers
  - Parameters: `resource_pattern`, `count`

### Resource Grouping (4 transformers)

- **create_group_node** - Create container/group nodes
  - Adds grouping nodes to organize related resources
  - Parameters: `group_name`, `children`, `metadata`
  
- **group_shared_services** - Group shared services together (IAM, CloudWatch, etc.)
  - Consolidates commonly shared resources into a single group
  - Parameters: `service_patterns`, `group_name`
  
- **move_to_parent** - Move resources between parents
  - Relocates resources in the hierarchy
  - Parameters: `resource_pattern`, `from_parent_pattern`, `to_parent_pattern`
  
- **move_to_vpc_parent** - Move resources to VPC level
  - Specifically moves resources from subnets to VPC parent level
  - Parameters: `resource_pattern`

**⚠️ For Resource Consolidation**: Use `AWS_CONSOLIDATED_NODES` in `cloud_config_aws.py` instead of transformers. See "Resource Consolidation" section below.

### Connections (11 transformers)

- **link_resources** - Create connections between resources
  - Adds new edges in the graph
  - Parameters: `source_pattern`, `target_pattern`, `bidirectional`
  
- **unlink_resources** - Remove connections between resources
  - Deletes specific edges
  - Parameters: `source_pattern`, `target_pattern`
  
- **unlink_from_parents** - Remove child from parent connections
  - Breaks parent-child relationships
  - Parameters: `resource_pattern`, `parent_filter`
  
- **redirect_connections** - Redirect connections to different resources
  - Changes connection targets
  - Parameters: `from_resource_pattern`, `to_resource_pattern`, `parent_pattern`
  
- **redirect_to_security_group** - Redirect to security groups if present
  - Redirects VPC connections to security groups when they exist
  - Parameters: `resource_pattern`
  
- **match_by_suffix** - Link resources with matching ~N suffixes
  - Connects resources with the same instance number
  - Parameters: `source_pattern`, `target_pattern`
  
- **link_via_shared_child** - Create direct links when resources share a child
  - Detects when both source and target connect to same intermediate, creates direct link
  - Parameters: `source_pattern`, `target_pattern`, `remove_intermediate`
  
- **link_by_metadata_pattern** - Create links based on metadata patterns
  - Uses metadata to determine connections
  - Parameters: `source_pattern`, `target_resource`, `metadata_key`, `metadata_value_pattern`
  
- **create_transitive_links** - Create transitive connections through intermediates
  - Pattern: a→b→c becomes a→c
  - Parameters: `source_pattern`, `intermediate_pattern`, `target_pattern`, `remove_intermediate`
  
- **link_peers_via_intermediary** - Link peer resources that share an intermediary
  - Pattern: intermediate→peer1 + intermediate→peer2 becomes peer1→peer2
  - Parameters: `intermediary_pattern`, `source_pattern`, `target_pattern`, `remove_intermediary`
  
- **bidirectional_link** - Create bidirectional connections between resources
  - Ensures connections exist in both directions
  - Parameters: `source_pattern`, `target_pattern`, `cleanup_reverse`
  
- **replace_connection_targets** - Replace old connection targets with new ones
  - Swaps connection endpoints
  - Parameters: `source_pattern`, `old_target_pattern`, `new_target_pattern`

### Graph Manipulation (1 transformer)

- **insert_intermediate_node** - Insert intermediate nodes between parents and children
  - Transforms: parent→child into parent→intermediate→child
  - Example: VPC→subnet becomes VPC→AZ→subnet
  - Handles node creation, metadata copying, and connection rewiring
  - Parameters: `parent_pattern`, `child_pattern`, `intermediate_node_generator`, `create_if_missing`

### Metadata Operations (1 transformer)

- **propagate_metadata** - Copy metadata from source to target resources
  - Supports copying specific keys or all keys
  - Supports `propagate_to_children: true` to copy to all children
  - Direction: "forward", "reverse", or "bidirectional"
  - Parameters: `source_pattern`, `target_pattern`, `metadata_keys`, `direction`, `copy_from_connections`, `propagate_to_children`

### Cleanup (1 transformer)

- **delete_nodes** - Delete nodes from graph
  - Removes resources and optionally their connections
  - Parameters: `resource_pattern`, `remove_from_parents`

### Variants (2 transformers)

- **apply_resource_variants** - Apply resource type variants (e.g., Fargate vs EC2)
  - Changes resource types based on metadata
  - Parameters: `resource_pattern`, `variant_map`, `metadata_key`
  
- **apply_all_variants** - Apply all variants globally
  - Applies all configured variants across the graph based on provider config
  - Parameters: none (uses provider-specific NODE_VARIANTS config)

### Pipeline (1 orchestrator)

- **apply_transformation_pipeline** - Execute sequence of transformations
  - Runs multiple transformations in order
  - Automatically resolves function parameters ending in `_function` or `_generator`
  - Parameters: `transformations` (list of transformation configs)

---

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

---

## Decision Guide

### Decision Tree

Use this decision tree to determine the best approach for a new or existing handler:

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

### Quick Reference Table

| Characteristic | Pure Config | Hybrid | Pure Function |
|----------------|-------------|--------|---------------|
| **Code lines** | 0 Python, 10-20 config | 20-40 Python, 10-20 config | 50-150 Python, 5 config |
| **Complexity** | Simple operations | Medium complexity | High complexity |
| **Reusability** | 100% (all generic) | 50-80% (transformers reusable) | 0% (all custom) |
| **Testability** | Test transformers once | Test function + transformers | Test entire function |
| **Maintainability** | Easiest (declarative) | Medium (clear separation) | Hardest (procedural) |
| **Use When** | Simple, repetitive ops | Common ops + unique logic | Complex conditional logic |

### Red Flags and Green Lights

**Red Flags for Pure Config** - Avoid Pure Config if handler has ANY of these:
- ❌ Conditional logic based on resource properties (if/else)
- ❌ Complex loops with nested conditions
- ❌ Dynamic naming with custom logic (beyond simple patterns)
- ❌ Try/except error handling
- ❌ Metadata manipulation with complex rules
- ❌ Domain-specific parsing (URLs, domains, ARNs)

**Green Lights for Pure Config** - Use Pure Config if handler does ALL operations with existing transformers:
- ✅ Move resources between parents
- ✅ Create/delete nodes
- ✅ Link/unlink resources
- ✅ Expand to numbered instances
- ✅ Redirect connections
- ✅ Copy metadata (simple patterns)
- ✅ Apply variants
- ✅ Group resources

**When to Choose Hybrid**:
- ✅ Most operations can use transformers
- ✅ Custom logic is isolated (metadata prep, name generation)
- ✅ Custom function is simple (<50 lines)
- ✅ Clear separation between generic and custom operations
- ✅ Custom function prepares data for transformers (or vice versa)

**When to Keep as Pure Function**:
- ❌ Transformers would require too many steps (>5 transformations)
- ❌ Logic has complex conditionals that can't be expressed declaratively
- ❌ Custom code is <50 lines and very specific to this resource type
- ❌ Attempting to use transformers causes edge cases or bugs
- ❌ The logic is well-tested and stable (don't fix what isn't broken)

---

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
        # ... 30 lines of logic to move and delete
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

### Example 2: Hybrid Handler

**Concept**: Use config for common operations, custom function for complex logic

```python
"aws_efs_file_system": {
    "description": "Handle EFS mount targets and file system relationships",
    "transformations": [
        {
            "operation": "bidirectional_link",
            "params": {
                "source_pattern": "aws_efs_mount_target",
                "target_pattern": "aws_efs_file_system",
                "cleanup_reverse": True,
            },
        },
    ],
    "additional_handler_function": "aws_handle_efs",  # Custom cleanup logic
}
```

**Custom function** (in `resource_handlers_aws.py`):
```python
def aws_handle_efs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle complex logic that can't be expressed with transformers."""
    # Config already created bidirectional links
    # Now apply complex conditional cleanup logic
    ...
    return tfdata
```

### Example 3: Pure Function Handler

**When to use**: Complex logic that can't be expressed with transformers

```python
"aws_security_group": {
    "description": "Process security group relationships and reverse connections",
    "additional_handler_function": "aws_handle_sg",
}
```

**Why pure function**: Security groups require:
- Bidirectional relationship manipulation
- Dynamic name generation based on connections
- Complex conditional logic for ingress/egress rules
- Metadata parsing and propagation

---

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

---

## Execution Flow

```python
# In graphmaker.py
def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute all configured handlers in sequence."""
    
    # Load provider-specific handler configs (automatic detection)
    handler_configs = _load_handler_configs(tfdata)
    
    for resource_pattern, config in handler_configs.items():
        # Check if this resource type exists in graph
        if helpers.list_of_dictkeys_containing(tfdata["graphdict"], resource_pattern):
            
            # Determine execution order
            order = config.get("handler_execution_order", "after")
            
            if order == "before":
                # Step 1: Call custom handler function first (if present)
                if "additional_handler_function" in config:
                    handler_func = getattr(resource_handlers, config["additional_handler_function"])
                    tfdata = handler_func(tfdata)
                
                # Step 2: Apply config-driven transformations (if present)
                if "transformations" in config:
                    tfdata = apply_transformation_pipeline(
                        tfdata, 
                        config["transformations"]
                    )
            else:  # "after" (default)
                # Step 1: Apply config-driven transformations (if present)
                if "transformations" in config:
                    tfdata = apply_transformation_pipeline(
                        tfdata, 
                        config["transformations"]
                    )
                
                # Step 2: Call custom handler function (if present)
                if "additional_handler_function" in config:
                    handler_func = getattr(resource_handlers, config["additional_handler_function"])
                    tfdata = handler_func(tfdata)
    
    return tfdata
```

**Execution Steps**:
1. Load provider-specific handler configs (automatic detection)
2. For each resource pattern in config:
   - Check if resource exists in graph
   - If `handler_execution_order` is "before":
     - Call custom function first
     - Apply transformations second
   - If `handler_execution_order` is "after" (default):
     - Apply transformations first
     - Call custom function second
3. Continue to next handler

---

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

Run TerraVision with Terraform code containing the new resource type:

```bash
cd tests/fixtures/aws_terraform/test_new_resource/
poetry run python ../../../terravision.py draw --source . --debug
```

---

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

### Validation Checklist

Before declaring a handler complete, verify:
- ✅ Connection direction is correct (arrows point the right way)
- ✅ No orphaned resources (all resources have connections)
- ✅ No duplicate connections
- ✅ Intermediary links are created (transitive connections)
- ✅ Test coverage is adequate
- ✅ Handler type (config/hybrid/function) is documented
- ✅ Description explains what the handler does

---

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

---

## Best Practices

1. **Start with Pure Config**: Always try Pure Config first. If you can't express the logic with existing transformers, consider Hybrid or Pure Function.

2. **Create Transformers for Common Patterns**: If you see a pattern used in multiple handlers, create a generic transformer.

3. **Keep Functions Small**: If custom function is >100 lines, consider breaking it into multiple transformers or helper functions.

4. **Document Handler Type**: Always include `"description"` explaining what the handler does and why it's that type.

5. **Test Behavior Preservation**: When refactoring, ensure tests pass without changing expected output.

6. **Use `handler_execution_order`**: When transformers need prepared data, run custom function first with `"handler_execution_order": "before"`.

7. **Avoid Over-Engineering**: Don't create transformers for one-off operations. Pure Function is fine for unique, complex logic.

8. **Complete Validation Checklist**: Before declaring a handler complete, run the comprehensive validation checklist to catch:
   - Connection direction errors (arrows pointing wrong way)
   - Orphaned resources (missing connections)
   - Duplicate connections
   - Intermediary link issues (transitive links not created)
   - Test coverage gaps

9. **Trust the Baseline**: Always validate that a handler is needed before implementing. The baseline Terraform graph parsing may already be sufficient.

10. **Use Consolidation Correctly**: For merging multiple resources into one node, use `AWS_CONSOLIDATED_NODES` in `cloud_config_aws.py`, not transformers.

---

## Current State (AWS)

### Pure Config-Driven (7 handlers)

- **aws_eks_node_group** - Expand node groups per subnet
- **aws_eks_fargate_profile** - Expand Fargate profiles per subnet
- **aws_autoscaling_group** - Link ASG to subnets
- **random_string** - Disconnect random resources
- **aws_vpc_endpoint** - Move to VPC and delete
- **aws_db_subnet_group** - Move to VPC, redirect to security groups
- **aws_** (pattern match) - Group shared services

**Code Reduction**: 360 lines → 85 lines (70% reduction)

### Hybrid (3 handlers)

- **aws_subnet** - Metadata prep (before) + `insert_intermediate_node` transformer
  - Creates VPC→AZ→subnet structure
  - 51 lines → 39 lines (24% reduction)
  
- **aws_cloudfront_distribution** - Link transformers + custom origin parsing
  - Generic link operations + domain-specific parsing
  
- **aws_efs_file_system** - Bidirectional link transformer + custom cleanup logic
  - Generic bidirectional linking + specific cleanup

### Pure Function (6 handlers - too complex for config)

- **aws_appautoscaling_target** - Count propagation + connection redirection
  - Logic too specific: conditional copying, policy filtering
  - Improved: removed dangerous `try/except: pass`, added explicit checks
  
- **aws_security_group** - Complex reverse relationship logic
  - Bidirectional manipulation, dynamic naming
  
- **aws_lb** - Metadata parsing and connection redirection
  - Target group parsing, connection management
  
- **aws_ecs** - Chart-specific conditional logic
  - Task definition parsing, service relationships
  
- **aws_eks** - Complex cluster grouping and Karpenter detection
  - Cluster organization, Karpenter support detection
  
- **helm_release** - Chart-specific conditional logic
  - Chart-specific behavior, conditional resource creation

---

## Benefits Summary

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

### 5. Code Reduction
- 70% reduction for simple handlers (360 lines → 85 lines for 7 AWS handlers)
- 24% reduction for hybrid handlers (51 lines → 39 lines for aws_subnet)
- Less code to maintain, fewer bugs

### 6. Flexibility
- Use the right tool for each handler
- Config for simple, code for complex
- Gradual migration path from function to config
- No forced refactoring of stable, complex handlers

---

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

---

## Conclusion

The hybrid configuration-driven approach reduces code by ~70% for simple handlers while maintaining flexibility for complex logic:

- **Readability** - Clear transformation sequences or explicit function calls
- **Maintainability** - Edit config for simple cases, write code only when needed
- **Extensibility** - Compose new handlers from existing blocks or custom functions
- **Testability** - Test transformers independently, test functions in isolation
- **Flexibility** - Choose the right tool (config vs code) for each handler

This architecture makes TerraVision easier to extend with new cloud services while keeping complex logic maintainable. All 135 tests pass with the hybrid architecture, proving backward compatibility and correctness.
