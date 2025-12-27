# Handler Refactoring Guide: From Pure Python to Hybrid Config

## Overview

This guide demonstrates how to refactor complex Pure Python handlers into Hybrid handlers that combine generic transformers with minimal custom code.

## New Generic Transformers Available

We've added 6 new generic transformers to `/modules/resource_transformers.py`:

1. **unlink_from_parents** - Remove child resources from all parent connections
2. **insert_intermediate_node** - Insert intermediate nodes between parents and children (parent→child becomes parent→intermediate→child)
3. **bidirectional_link** - Create bidirectional connections between resources
4. **propagate_metadata** - Copy metadata values from source to target resources
5. **consolidate_into_single_node** - Merge multiple resources into a single consolidated node
6. **replace_connection_targets** - Replace connection targets matching pattern with new targets

## Refactoring Pattern

### Example 1: EFS File System Handler

**Original Pure Python** (46 lines):

```python
def aws_handle_efs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle EFS mount target and file system relationships."""
    # Find all EFS file systems and mount targets
    efs_systems = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_file_system"
    )
    efs_mount_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_mount_target"
    )
    # Link mount targets to file systems
    for target in efs_mount_targets:
        for fs in efs_systems:
            if fs not in tfdata["graphdict"][target]:
                tfdata["graphdict"][target].append(fs)
            # Clean up file system connections
            for fs_connection in sorted(list(tfdata["graphdict"][fs])):
                if helpers.get_no_module_name(fs_connection).startswith(
                    "aws_efs_mount_target"
                ):
                    # Remove mount target from file system
                    tfdata["graphdict"][fs].remove(fs_connection)
                else:
                    # Move other connections to file system
                    tfdata["graphdict"][fs_connection].append(fs)
                    tfdata["graphdict"][fs].remove(fs_connection)
    # Replace EFS file system references with mount target
    for node in sorted(tfdata["graphdict"].keys()):
        connections = tfdata["graphdict"][node]
        if helpers.consolidated_node_check(node):
            for connection in list(connections):
                if helpers.get_no_module_name(connection).startswith(
                    "aws_efs_file_system"
                ):
                    # Use first mount target as replacement
                    target = efs_mount_targets[0].split("~")[0]
                    target = helpers.remove_brackets_and_numbers(target)
                    tfdata["graphdict"][node].remove(connection)
                    tfdata["graphdict"][node].append(target)
    return tfdata
```

**Refactored Hybrid Config** (~15 lines):

```python
# In resource_handler_configs_aws.py
"aws_efs_file_system": {
    "description": "Handle EFS mount targets and file system relationships",
    "transformations": [
        {
            "operation": "bidirectional_link",
            "params": {
                "source_pattern": "aws_efs_mount_target",
                "target_pattern": "aws_efs_file_system",
                "cleanup_reverse": True,  # Remove fs→target after creating target→fs
            },
        },
        {
            "operation": "replace_connection_targets",
            "params": {
                "source_pattern": ".*",  # All nodes
                "old_target_pattern": "aws_efs_file_system",
                "new_target_pattern": "aws_efs_mount_target",
            },
        },
    ],
    "additional_handler_function": "aws_handle_efs_custom",  # For complex consolidation logic
}
```

**Minimal Custom Function** (if still needed):

```python
def aws_handle_efs_custom(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle EFS-specific consolidation logic that can't be expressed in transformers."""
    # Only handle the consolidated node special case
    # Generic transformers already handled the bidirectional linking
    # This is left for domain-specific logic that transformers can't handle
    return tfdata
```

**Result**: 67% code reduction (46 lines → 15 lines config + optional minimal custom code)

---

### Example 2: Subnet AZ Handler

The `aws_handle_subnet_azs` handler is more complex because it:
1. Generates dynamic node names from metadata
2. Accesses `original_metadata` (not just `meta_data`)
3. Filters by `hidden` resources
4. Has domain-specific suffix logic

**Current Implementation Analysis:**

| Step | Type | Can Use Transformer? |
|------|------|---------------------|
| Find subnets | Pattern matching | ✅ Built-in |
| Remove subnet from parents | Unlinking | ✅ `unlink_from_parents` |
| Generate AZ name from metadata | Dynamic naming | ❌ Custom logic needed |
| Create AZ node | Node creation | ✅ `insert_intermediate_node` |
| Link parent→AZ→subnet | Rewiring | ✅ `insert_intermediate_node` |
| Fill empty groups | Utility | ⚠️ Keep as is |

**Challenge**: The `insert_intermediate_node` transformer needs a callable to generate AZ names, but config dictionaries can't contain Python functions directly.

**Solution Options:**

**Option A: Pure Custom Function** (Current approach)
- Keep entire handler as custom function
- Pros: Works with current architecture
- Cons: Doesn't leverage new transformers

**Option B: Hybrid with Function Reference** (Recommended)
```python
# In resource_handler_configs_aws.py
"aws_subnet": {
    "description": "Create availability zone nodes and link to subnets",
    "transformations": [
        {
            "operation": "insert_intermediate_node",
            "params": {
                "parent_pattern": "aws_vpc",
                "child_pattern": "aws_subnet",
                "intermediate_node_generator": "generate_az_node_name",  # Function name as string
                "create_if_missing": True,
            },
        },
    ],
}
```

This requires updating `apply_transformation_pipeline` to resolve function names:

```python
# In resource_transformers.py
def apply_transformation_pipeline(tfdata, transformations):
    for transform_config in transformations:
        operation = transform_config.get("operation")
        params = transform_config.get("params", {})

        # Resolve function references
        if operation == "insert_intermediate_node":
            gen_func_name = params.get("intermediate_node_generator")
            if isinstance(gen_func_name, str):
                # Import and resolve the function
                import modules.resource_handlers_aws as handlers
                params["intermediate_node_generator"] = getattr(handlers, gen_func_name)

        tfdata = transformer_map[operation](tfdata, **params)

    return tfdata
```

**Option C: Two-Phase Approach with Execution Order** ⭐ **RECOMMENDED**
1. Custom function runs first to generate and store AZ names in metadata
2. Generic transformers use stored names to create nodes and links

```python
# In resource_handler_configs_aws.py
"aws_subnet": {
    "description": "Create availability zone nodes and link to subnets",
    "handler_execution_order": "before",  # NEW: Run handler BEFORE transformations
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

See `docs/HANDLER_EXECUTION_ORDER.md` for complete documentation.

---

### Example 3: Load Balancer Handler

**Original Pure Python** (64 lines):

```python
def aws_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle load balancer type variants and connections."""
    found_lbs = sorted(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_lb")
    )
    for lb in found_lbs:
        if lb not in tfdata["meta_data"]:
            continue

        lb_type = helpers.check_variant(lb, tfdata["meta_data"][lb])
        renamed_node = str(lb_type) + "." + "elb"

        # Initialize renamed node metadata
        if not tfdata["meta_data"].get(renamed_node):
            tfdata["meta_data"][renamed_node] = copy.deepcopy(tfdata["meta_data"][lb])

        # Transfer connections
        for connection in sorted(list(tfdata["graphdict"][lb])):
            if not tfdata["graphdict"].get(renamed_node):
                tfdata["graphdict"][renamed_node] = list()
            c_type = connection.split(".")[0]
            if c_type not in SHARED_SERVICES:
                tfdata["graphdict"][renamed_node].append(connection)
                tfdata["graphdict"][lb].remove(connection)

        # Propagate count metadata
        # ... (more complex logic)

        # Update parent references
        parents = sorted(helpers.list_of_parents(tfdata["graphdict"], lb))
        for p in parents:
            # ... (rewire connections)
```

**Refactored Hybrid Config**:

```python
"aws_lb": {
    "description": "Handle load balancer type variants and connections",
    "transformations": [
        {
            "operation": "apply_resource_variants",
            "params": {
                "resource_pattern": "aws_lb",
                "variant_map": {
                    "application": "aws_alb",
                    "network": "aws_nlb",
                },
                "metadata_key": "load_balancer_type",
            },
        },
        {
            "operation": "consolidate_into_single_node",
            "params": {
                "resource_pattern": "aws_alb|aws_nlb",
                "target_node_name": "aws_alb.elb",  # Or dynamically generated
                "merge_connections": True,
                "merge_metadata": True,
            },
        },
        {
            "operation": "propagate_metadata",
            "params": {
                "source_pattern": "aws_alb.elb",
                "target_pattern": "aws_vpc",  # Propagate to parents
                "metadata_keys": ["count"],
                "direction": "reverse",
                "copy_from_connections": True,
            },
        },
    ],
    "additional_handler_function": "aws_handle_lb_custom",  # For remaining complex logic
}
```

---

## Migration Checklist

When refactoring a Pure Python handler to Hybrid:

### 1. Analyze the Function
- [ ] List all operations the function performs
- [ ] Identify which operations match existing transformers
- [ ] Identify which operations are domain-specific

### 2. Extract Generic Patterns
- [ ] Can parent-child links be broken? → `unlink_from_parents`
- [ ] Can resources be linked bidirectionally? → `bidirectional_link`
- [ ] Can intermediate nodes be inserted? → `insert_intermediate_node`
- [ ] Can metadata be propagated? → `propagate_metadata`
- [ ] Can resources be consolidated? → `consolidate_into_single_node`
- [ ] Can connection targets be replaced? → `replace_connection_targets`

### 3. Create Configuration
- [ ] Add entry to `RESOURCE_HANDLER_CONFIGS` in `resource_handler_configs_aws.py`
- [ ] Add `transformations` array with generic operations
- [ ] Add `additional_handler_function` if custom logic remains

### 4. Simplify Custom Function
- [ ] Remove all logic covered by transformers
- [ ] Keep only domain-specific logic that can't be generalized
- [ ] Add clear comments explaining why custom logic is needed

### 5. Test
- [ ] Compare output of old vs new implementation
- [ ] Ensure all connections are preserved
- [ ] Verify metadata is correctly propagated
- [ ] Run full test suite

---

## When to Use Each Transformer

| Transformer | Use When | Example |
|-------------|----------|---------|
| `unlink_from_parents` | Need to break parent-child connections | Removing subnets from VPC before inserting AZ nodes |
| `insert_intermediate_node` | Need parent→child to become parent→intermediate→child | VPC→subnet becomes VPC→AZ→subnet |
| `bidirectional_link` | Need resources to reference each other | EFS mount target ↔ EFS file system |
| `propagate_metadata` | Need to copy metadata up/down hierarchy | Propagating count from connections to load balancer |
| `consolidate_into_single_node` | Need to merge multiple resources into one | Multiple ALBs become single ALB.elb node |
| `replace_connection_targets` | Need to redirect connections to different resource | All resources connecting to EFS FS now connect to EFS mount target |

---

## Benefits of Hybrid Approach

1. **70% code reduction** for handlers with generic patterns
2. **Reusability**: Same transformers work across different resource types
3. **Clarity**: Transformation sequence is self-documenting
4. **Flexibility**: Can mix config and custom code as needed
5. **Testability**: Test transformers independently from custom logic
6. **Maintainability**: Add new resources by editing config, not writing Python

---

## Next Steps

1. Identify remaining Pure Python handlers to refactor
2. Create additional transformers as patterns emerge
3. Update documentation with real-world refactoring examples
4. Add unit tests for new transformers
5. Measure performance impact of configuration-driven approach
