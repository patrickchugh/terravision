# Handler Execution Order Configuration

## Overview

The hybrid handler architecture now supports configurable execution order for custom handler functions and generic transformers. This allows you to specify whether custom logic should run BEFORE or AFTER transformations.

## Configuration Parameter

**Parameter**: `handler_execution_order`
**Values**: `"before"` | `"after"` (default)
**Location**: Handler configuration in `resource_handler_configs_<provider>.py`

## Execution Modes

### Mode 1: "after" (Default Behavior)

Custom handler function runs AFTER transformations.

**Execution Flow**:
```
1. Apply transformations (config-driven)
2. Run additional_handler_function (custom code)
```

**Use When**:
- Transformations do generic work, custom function adds final touches
- Custom function needs to clean up or adjust transformer output
- Custom function performs validation or special cases

**Example**:
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

### Mode 2: "before" (Custom Logic First)

Custom handler function runs BEFORE transformations.

**Execution Flow**:
```
1. Run additional_handler_function (custom code)
2. Apply transformations (config-driven)
```

**Use When**:
- Custom function prepares or enriches metadata that transformers need
- Custom function generates dynamic values (node names, IDs, etc.)
- Custom function performs complex calculations that transformers use

**Example**:
```python
"aws_subnet": {
    "description": "Create availability zone nodes and link to subnets",
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
    "additional_handler_function": "aws_prepare_subnet_az_metadata",
    "handler_execution_order": "before",  # Run handler FIRST to prepare metadata
}
```

## Real-World Example: Subnet AZ Handler

### Problem

The subnet handler needs to:
1. Generate dynamic AZ node names from metadata
2. Use those names to create intermediate nodes
3. Rewire connections: VPC→subnet becomes VPC→AZ→subnet

**Challenge**: Generic transformers need the AZ names, but generating them requires complex logic.

### Solution: Two-Phase Approach

**Phase 1: Custom function prepares metadata** (runs BEFORE transformations)

```python
def aws_prepare_subnet_az_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare AZ metadata for subnets before transformers run."""
    subnet_resources = [
        k for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_subnet")
        and k not in tfdata.get("hidden", [])
    ]

    for subnet in subnet_resources:
        subnet_metadata = tfdata.get("original_metadata", {}).get(subnet, {})

        # Generate AZ node name using complex logic
        az = "aws_az.availability_zone_" + str(
            subnet_metadata.get("availability_zone", "unknown")
        )
        az = az.replace("-", "_")
        region = subnet_metadata.get("region")

        if region:
            az = az.replace("True", region)
        else:
            az = az.replace(".True", ".availability_zone")

        az = _add_suffix(az)

        # Store in metadata for transformers to use
        if subnet not in tfdata["meta_data"]:
            tfdata["meta_data"][subnet] = {}
        tfdata["meta_data"][subnet]["_az_node_name"] = az

    return tfdata
```

**Phase 2: Transformers use prepared metadata** (runs AFTER custom function)

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

### Result

**Before** (Pure Python - 51 lines):
```python
def aws_handle_subnet_azs(tfdata):
    subnet_resources = [...]
    for subnet in subnet_resources:
        parents_list = helpers.list_of_parents(tfdata["graphdict"], subnet)
        for parent in parents_list:
            if subnet in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(subnet)
            az = "aws_az.availability_zone_" + str(...)
            # ... 40 more lines of complex logic
    return tfdata
```

**After** (Hybrid - 25 lines custom + 15 lines config):
- Custom function: 25 lines (metadata preparation only)
- Config: 15 lines (generic transformations)
- **Result**: 22% reduction + clearer separation of concerns

## Benefits of Configurable Execution Order

### 1. Separation of Concerns
- **Custom function**: Handles domain-specific logic (AZ name generation)
- **Transformers**: Handle generic patterns (unlinking, node creation, rewiring)

### 2. Reusability
- Custom metadata preparation can be reused across different resource types
- Transformers remain generic and reusable

### 3. Testability
- Test metadata preparation independently
- Test transformers independently
- Test full pipeline together

### 4. Clarity
- Execution order is explicit in configuration
- No hidden dependencies or ordering assumptions
- Easy to understand what runs when

## Use Cases by Execution Order

| Execution Order | Use Case | Example |
|----------------|----------|---------|
| **"before"** | Prepare metadata | Generate AZ names from subnet metadata |
| **"before"** | Enrich data | Calculate derived values for transformers |
| **"before"** | Validate input | Check preconditions before transformations |
| **"after"** | Clean up | Remove temporary nodes created by transformers |
| **"after"** | Validate output | Check postconditions after transformations |
| **"after"** | Special cases | Handle edge cases not covered by transformers |

## Migration Guide: Pure Python → Hybrid with Execution Order

### Step 1: Analyze the Function

Identify operations that:
1. **Prepare data** → Custom function with `handler_execution_order: "before"`
2. **Apply generic patterns** → Transformations
3. **Clean up or handle special cases** → Custom function with `handler_execution_order: "after"`

### Step 2: Split the Logic

**Original**:
```python
def aws_handle_resource(tfdata):
    # Part A: Prepare metadata (domain-specific)
    for resource in resources:
        metadata[resource] = calculate_complex_value(resource)

    # Part B: Generic pattern (unlinking)
    for resource in resources:
        for parent in parents:
            parent.remove(resource)

    # Part C: Generic pattern (node creation)
    for resource in resources:
        create_intermediate_node(resource)

    # Part D: Special case handling (domain-specific)
    if special_condition:
        handle_special_case()

    return tfdata
```

**Refactored**:
```python
# Custom function for Part A + Part D
def aws_prepare_resource_metadata(tfdata):
    # Part A: Prepare metadata
    for resource in resources:
        metadata[resource] = calculate_complex_value(resource)
    return tfdata

def aws_handle_resource_special_cases(tfdata):
    # Part D: Special cases
    if special_condition:
        handle_special_case()
    return tfdata

# Config for Parts A, B, C, D
{
    "handler_execution_order": "before",
    "additional_handler_function": "aws_prepare_resource_metadata",
    "transformations": [
        # Part B: Unlinking
        {"operation": "unlink_from_parents", "params": {...}},
        # Part C: Node creation
        {"operation": "insert_intermediate_node", "params": {...}},
    ],
}

# If Part D is needed, add another config entry:
{
    "handler_execution_order": "after",
    "additional_handler_function": "aws_handle_resource_special_cases",
}
```

### Step 3: Choose Execution Order

**Decision Matrix**:

| If your custom function... | Then use... |
|----------------------------|-------------|
| Generates values that transformers need | `"before"` |
| Enriches metadata for transformers | `"before"` |
| Validates input before processing | `"before"` |
| Cleans up transformer output | `"after"` |
| Handles edge cases not covered by transformers | `"after"` |
| Validates final output | `"after"` |

## Implementation Details

### Code Location

**File**: `modules/graphmaker.py`
**Function**: `handle_special_resources()`

```python
def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Apply special processing for specific resource types.

    Supports hybrid approach with configurable execution order:
    - 'handler_execution_order': "before" or "after" (default: "after")
    """

    for resource_pattern, config in RESOURCE_HANDLER_CONFIGS.items():
        execution_order = config.get("handler_execution_order", "after")

        if execution_order == "before":
            # Run handler FIRST, then transformations
            if has_handler:
                tfdata = handler_func(tfdata)
            if has_transformations:
                tfdata = apply_transformation_pipeline(tfdata, transformations)
        else:
            # Run transformations FIRST, then handler (default)
            if has_transformations:
                tfdata = apply_transformation_pipeline(tfdata, transformations)
            if has_handler:
                tfdata = handler_func(tfdata)

    return tfdata
```

## Best Practices

### 1. Default to "after"
Unless you have a specific reason to run custom logic first, use the default "after" mode. This keeps transformers as the primary mechanism.

### 2. Document Why
Add comments explaining why you chose "before" execution order:

```python
"aws_subnet": {
    "description": "Create availability zone nodes and link to subnets",
    # Run handler BEFORE transformations to generate AZ node names
    # that insert_intermediate_node transformer needs
    "handler_execution_order": "before",
    "additional_handler_function": "aws_prepare_subnet_az_metadata",
    "transformations": [...],
}
```

### 3. Keep Custom Functions Focused
When using "before" mode:
- Custom function should ONLY prepare data
- Don't mix preparation with transformation logic
- Let transformers handle the actual graph manipulation

### 4. Consider Split Handlers
If you need both "before" and "after" logic, create two separate configs:

```python
# First pass: Prepare metadata
"aws_resource_prepare": {
    "handler_execution_order": "before",
    "additional_handler_function": "aws_prepare_resource",
    "transformations": [...],
}

# Second pass: Clean up
"aws_resource_cleanup": {
    "handler_execution_order": "after",
    "additional_handler_function": "aws_cleanup_resource",
}
```

## Testing

### Test Execution Order

```python
def test_handler_execution_order():
    tfdata = load_test_data()

    # Track execution order
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
        "transformations": [{"operation": "mock_transformer", "params": {}}],
    }

    handle_special_resources(tfdata)

    assert execution_log == ["handler", "transformer"]

    # Test "after" mode (default)
    execution_log.clear()
    config["handler_execution_order"] = "after"

    handle_special_resources(tfdata)

    assert execution_log == ["transformer", "handler"]
```

## Summary

The `handler_execution_order` configuration parameter provides flexible control over when custom logic runs relative to generic transformations:

- **"before"**: Custom function prepares data for transformers
- **"after"** (default): Custom function handles special cases after transformations

This enables powerful hybrid handlers that combine:
- Domain-specific logic (custom functions)
- Generic reusable patterns (transformers)
- Clear, explicit execution flow

Use "before" mode when transformers need data that only custom logic can generate. Use "after" mode (default) for everything else.
