# Handler Execution Order Feature - Implementation Summary

## What Was Implemented

Added configurable execution order for hybrid handlers, allowing custom functions to run BEFORE or AFTER generic transformations.

## New Configuration Parameter

**Parameter**: `handler_execution_order`
**Values**:
- `"before"` - Run custom function FIRST, then transformations
- `"after"` - Run transformations FIRST, then custom function (default)

**Location**: Handler configuration in `resource_handler_configs_<provider>.py`

## Code Changes

### 1. Updated `modules/graphmaker.py`

Modified `handle_special_resources()` function to support configurable execution order:

```python
def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Apply special processing for specific resource types.

    Supports hybrid approach with configurable execution order:
    - 'handler_execution_order': "before" or "after" (default: "after")
    """

    for resource_pattern, config in RESOURCE_HANDLER_CONFIGS.items():
        execution_order = config.get("handler_execution_order", "after")

        if execution_order == "before":
            # Step 1: Run handler function FIRST
            if has_handler:
                tfdata = handler_func(tfdata)
            # Step 2: Apply transformations AFTER
            if has_transformations:
                tfdata = apply_transformation_pipeline(tfdata, transformations)
        else:
            # Default: transformations first, then handler
            # Step 1: Apply transformations
            if has_transformations:
                tfdata = apply_transformation_pipeline(tfdata, transformations)
            # Step 2: Run handler function
            if has_handler:
                tfdata = handler_func(tfdata)

    return tfdata
```

### 2. Added Helper Function in `modules/resource_handlers_aws.py`

Created `aws_prepare_subnet_az_metadata()` to demonstrate "before" mode:

```python
def aws_prepare_subnet_az_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare AZ metadata for subnets before transformers run.

    This function runs BEFORE transformations to generate and store AZ node names
    in metadata so that generic transformers can use them.
    """
    subnet_resources = [...]

    for subnet in subnet_resources:
        # Generate AZ node name using complex domain logic
        az = "aws_az.availability_zone_" + str(...)
        # ... complex string manipulation

        # Store in metadata for transformers to use
        tfdata["meta_data"][subnet]["_az_node_name"] = az

    return tfdata
```

### 3. Updated Documentation

Created comprehensive documentation:
- `docs/HANDLER_EXECUTION_ORDER.md` - Complete feature documentation
- Updated `docs/HANDLER_REFACTORING_GUIDE.md` - Added recommended approach

## Usage Examples

### Example 1: Default "after" Mode

Transformations run first, custom function handles cleanup:

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
    "additional_handler_function": "aws_handle_efs",
    "handler_execution_order": "after",  # Optional - this is the default
}
```

**Execution Flow**: transformations → handler

### Example 2: "before" Mode

Custom function prepares metadata, transformations use it:

```python
"aws_subnet": {
    "description": "Create availability zone nodes and link to subnets",
    "handler_execution_order": "before",  # Run handler FIRST
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

**Execution Flow**: handler → transformations

## Use Cases

| Execution Order | Use When | Example |
|----------------|----------|---------|
| **"before"** | Custom function prepares data for transformers | Generate AZ names from subnet metadata |
| **"before"** | Custom function enriches metadata | Calculate derived values transformers need |
| **"before"** | Custom function validates input | Check preconditions before processing |
| **"after"** | Custom function cleans up transformer output | Remove temporary nodes |
| **"after"** | Custom function handles special cases | Edge cases not covered by transformers |
| **"after"** | Custom function validates final output | Check postconditions |

## Benefits

### 1. Flexible Hybrid Architecture
- Support both "preparation" and "cleanup" patterns
- Clear separation between data preparation and transformation
- Explicit execution flow

### 2. Enables Complex Refactoring
- Handlers that previously couldn't use transformers now can
- Custom logic prepares data, transformers do the work
- Example: Subnet AZ handler now 22% smaller with clearer intent

### 3. Maintains Backward Compatibility
- Default is "after" mode (existing behavior)
- Existing handlers continue to work unchanged
- Opt-in feature for handlers that need it

### 4. Self-Documenting
- Execution order is explicit in config
- No hidden dependencies
- Easy to understand what runs when

## Real-World Impact

### Subnet AZ Handler Refactoring

**Before** (Pure Python - 51 lines):
```python
def aws_handle_subnet_azs(tfdata):
    # All-in-one function doing everything
    # - Generate AZ names
    # - Unlink from parents
    # - Create AZ nodes
    # - Rewire connections
    # ... 51 lines of intertwined logic
    return tfdata
```

**After** (Hybrid with "before" mode - 40 lines total):
```python
# Custom function (25 lines) - runs FIRST
def aws_prepare_subnet_az_metadata(tfdata):
    # ONLY generate and store AZ names
    for subnet in subnets:
        az_name = generate_complex_az_name(subnet)
        tfdata["meta_data"][subnet]["_az_node_name"] = az_name
    return tfdata

# Config (15 lines) - runs AFTER
"aws_subnet": {
    "handler_execution_order": "before",
    "additional_handler_function": "aws_prepare_subnet_az_metadata",
    "transformations": [
        {"operation": "unlink_from_parents", "params": {...}},
        {"operation": "insert_intermediate_node", "params": {...}},
    ],
}
```

**Result**:
- 22% code reduction (51 → 40 lines)
- Clearer separation of concerns
- Reusable transformers
- More testable

## Testing Strategy

### Unit Test for Execution Order

```python
def test_handler_execution_order():
    execution_log = []

    def mock_handler(data):
        execution_log.append("handler")
        return data

    def mock_transformer(data, **params):
        execution_log.append("transformer")
        return data

    # Test "before" mode
    config = {
        "handler_execution_order": "before",
        "additional_handler_function": "mock_handler",
        "transformations": [{"operation": "mock_transformer"}],
    }

    handle_special_resources(tfdata)
    assert execution_log == ["handler", "transformer"]

    # Test "after" mode (default)
    config["handler_execution_order"] = "after"
    execution_log.clear()

    handle_special_resources(tfdata)
    assert execution_log == ["transformer", "handler"]
```

## Files Modified

```
modules/
├── graphmaker.py                      # Updated handle_special_resources()
└── resource_handlers_aws.py           # Added aws_prepare_subnet_az_metadata()

docs/
├── HANDLER_EXECUTION_ORDER.md         # NEW - Complete feature documentation
└── HANDLER_REFACTORING_GUIDE.md       # Updated with recommended approach

EXECUTION_ORDER_FEATURE.md             # NEW - This summary
```

## Migration Guide

### When to Add `handler_execution_order: "before"`

If your handler needs to:
1. Generate dynamic values that transformers will use
2. Enrich metadata before transformations
3. Prepare data structures for generic operations

Then:
1. Extract the preparation logic into a focused custom function
2. Add `"handler_execution_order": "before"` to config
3. Let transformers do the actual graph manipulation

### Example Migration

**Before**:
```python
def aws_handle_resource(tfdata):
    # Step 1: Complex metadata calculation
    for r in resources:
        calculate_metadata(r)

    # Step 2: Generic unlinking
    for r in resources:
        unlink_from_parents(r)

    # Step 3: Generic node creation
    for r in resources:
        create_nodes(r)

    return tfdata
```

**After**:
```python
# Custom function for Step 1
def aws_prepare_resource_metadata(tfdata):
    for r in resources:
        calculate_metadata(r)
    return tfdata

# Config for Steps 2-3
{
    "handler_execution_order": "before",  # Run Step 1 FIRST
    "additional_handler_function": "aws_prepare_resource_metadata",
    "transformations": [
        {"operation": "unlink_from_parents", "params": {...}},  # Step 2
        {"operation": "create_group_node", "params": {...}},    # Step 3
    ],
}
```

## Best Practices

### 1. Default to "after"
Unless you have a specific need for "before" mode, use the default.

### 2. Document Why
Always add a comment explaining why "before" mode is needed:

```python
"aws_subnet": {
    # Run handler BEFORE transformations to generate AZ node names
    # that insert_intermediate_node transformer needs
    "handler_execution_order": "before",
    ...
}
```

### 3. Keep Preparation Functions Focused
When using "before" mode, the custom function should ONLY prepare data:
- Don't mix preparation with transformation logic
- Let transformers handle graph manipulation
- Store prepared values in metadata

### 4. Consider Split Handlers
If you need both preparation and cleanup:

```python
# First: Prepare
"resource_prepare": {
    "handler_execution_order": "before",
    "additional_handler_function": "prepare",
    "transformations": [...],
}

# Second: Clean up
"resource_cleanup": {
    "handler_execution_order": "after",
    "additional_handler_function": "cleanup",
}
```

## Future Enhancements

Potential future improvements:
1. Support multiple custom functions with different execution orders
2. Add "during" mode to interleave custom logic between transformations
3. Add conditional execution based on metadata
4. Add execution order visualization in debug mode

## Conclusion

The `handler_execution_order` feature completes the hybrid handler architecture by enabling flexible control over when custom logic runs:

- **"before"**: Prepare data for transformers
- **"after"** (default): Clean up or handle special cases

This enables powerful two-phase hybrid handlers that:
1. Use custom code for domain-specific logic (metadata preparation)
2. Use transformers for generic patterns (graph manipulation)
3. Maintain clear, explicit execution flow

The feature is backward compatible, opt-in, and self-documenting - making it easy to adopt incrementally as handlers are refactored.
