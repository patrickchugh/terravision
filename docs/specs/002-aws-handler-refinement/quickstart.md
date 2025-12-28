# Quickstart: AWS Handler Refinement Implementation

**Branch**: `002-aws-handler-refinement` | **Date**: 2025-12-26

## Overview

This guide provides implementation instructions for adding AWS resource handlers to TerraVision. Follow these patterns to maintain consistency with existing code.

---

## Prerequisites

```bash
# Ensure you're on the feature branch
git checkout 002-aws-handler-refinement

# Install dependencies
poetry install

# Verify existing tests pass
poetry run pytest tests -v
```

---

## Implementation Pattern (Config-Driven Architecture)

Per constitution CO-006 through CO-013, follow this decision hierarchy:
1. **Pure Config-Driven** - Use only existing transformers (preferred)
2. **Hybrid** - Config transformations + custom function for unique logic
3. **Pure Function** - Only when logic is too complex for declarative expression

### Step 1: Add Handler Config to `resource_handler_configs_aws.py`

Location: `modules/config/resource_handler_configs_aws.py`

#### Pattern A: Pure Config-Driven (Preferred)
```python
# Example: ElastiCache (reuses existing transformers)
RESOURCE_HANDLER_CONFIGS = {
    "aws_elasticache_replication_group": {
        "description": "Expand ElastiCache replication groups to numbered instances per subnet",
        "transformations": [
            {
                "operation": "expand_to_numbered_instances",
                "params": {
                    "resource_pattern": "aws_elasticache_replication_group",
                    "subnet_key": "subnet_group_name",
                    "skip_if_numbered": True,
                },
            },
            {
                "operation": "match_by_suffix",
                "params": {
                    "source_pattern": "aws_ecs_service|aws_eks_node_group",
                    "target_pattern": "aws_elasticache",
                },
            },
        ],
    },
}
```

#### Pattern B: Hybrid (Config + Custom Function)
```python
# Example: API Gateway (config consolidation + custom integration parsing)
RESOURCE_HANDLER_CONFIGS = {
    "aws_api_gateway_rest_api": {
        "description": "Consolidate API Gateway resources and parse integrations (Hybrid: consolidation is generic, URI parsing requires custom logic)",
        "transformations": [
            {
                "operation": "consolidate_into_single_node",
                "params": {
                    "resource_pattern": "aws_api_gateway",
                    "target_node_name": "aws_api_gateway.api",
                },
            },
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "aws_api_gateway_stage|aws_api_gateway_deployment",
                    "remove_from_parents": True,
                },
            },
        ],
        "additional_handler_function": "aws_handle_api_gateway_integrations",
    },
}
```

#### Pattern C: Pure Function (Complex Logic Only)
```python
# Example: Step Functions (complex JSON parsing with conditional logic)
RESOURCE_HANDLER_CONFIGS = {
    "aws_sfn_state_machine": {
        "description": "Parse state machine definition JSON to detect service integrations (Pure Function: JSON parsing with conditional logic for multiple task types cannot be expressed declaratively per CO-009)",
        "additional_handler_function": "aws_handle_step_functions",
    },
}
```

### Step 2: Add Custom Function (if Hybrid or Pure Function)

Location: `modules/resource_handlers_aws.py`

Only needed for Hybrid or Pure Function handlers. **Skip this step for Pure Config-Driven handlers.**

```python
def aws_handle_api_gateway_integrations(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse API Gateway integration URIs to detect Lambda/Step Functions connections.

    Why custom function needed (CO-009): Integration URI parsing involves string
    manipulation and ARN extraction logic that transformers cannot express declaratively.
    """
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})
    all_resource = tfdata.get("all_resource", {})

    # Find all API Gateway REST APIs
    api_gateways = [r for r in graphdict.keys() if r.startswith("aws_api_gateway_rest_api.")]

    for api in api_gateways:
        # Parse integrations to find Lambda/Step Functions
        integrations = find_integrations_for_api(api, all_resource)

        for integration in integrations:
            target = parse_integration_uri(integration)
            if target and target in graphdict:
                if target not in graphdict[api]:
                    graphdict[api].append(target)

        # Add placeholder if no integrations
        if not graphdict.get(api, []):
            external_node = "aws_external_integration.external"
            graphdict[api] = [external_node]
            meta_data[external_node] = {"label": "External Integration"}

    return tfdata
```

### Step 3: Add Minimal Config (if Edge Service)

Location: `modules/config/cloud_config_aws.py`

Only if the resource is an edge service:

```python
AWS_EDGE_NODES = [
    # ... existing entries ...
    "aws_api_gateway",
    "aws_appsync",
    "aws_cognito",
]
```

### Step 4: Verify Handler Dispatch

**No code changes needed!** The existing dispatch in `graphmaker.py` automatically loads and executes handlers from `RESOURCE_HANDLER_CONFIGS`:

```python
# In graphmaker.py (existing code - no modification needed)
def handle_special_resources(tfdata):
    config = load_config(provider)
    handler_configs = config.RESOURCE_HANDLER_CONFIGS  # Auto-loaded

    # Transformers execute automatically based on config
    # Custom functions called automatically if specified

    return tfdata
```

---

## Common Implementation Patterns

### Pattern A: Two-Step Connection Mapping

Use when connecting resources through intermediate resources:

```python
def link_resources_through_intermediate(tfdata):
    graphdict = tfdata["graphdict"]

    # Step 1: Build mapping from intermediate to actual target
    mapping = {}
    for resource, connections in graphdict.items():
        for conn in connections:
            if is_intermediate_resource(conn):
                target = find_actual_target(conn, tfdata)
                mapping[conn] = target

    # Step 2: Replace intermediate connections with direct connections
    for resource in list(graphdict.keys()):
        connections = list(graphdict[resource])  # Copy to avoid mutation
        for conn in connections:
            if conn in mapping:
                graphdict[resource].remove(conn)
                if mapping[conn] not in graphdict[resource]:
                    graphdict[resource].append(mapping[conn])

    return tfdata
```

### Pattern B: Numbered Resource Expansion

Use when a resource spans multiple parents:

```python
def expand_across_subnets(tfdata, resource):
    graphdict = tfdata["graphdict"]
    meta_data = tfdata["meta_data"]

    # Find subnets this resource should be in
    subnets = find_matching_subnets(resource, tfdata)

    if len(subnets) > 1:
        # Create numbered instances
        for i, subnet in enumerate(subnets, 1):
            numbered = f"{resource}~{i}"
            graphdict[numbered] = copy.copy(graphdict[resource])
            meta_data[numbered] = copy.deepcopy(meta_data[resource])

            # Add to specific subnet
            graphdict[subnet].append(numbered)

        # CRITICAL: Delete original unnumbered resource
        del graphdict[resource]
        del meta_data[resource]

    return tfdata
```

### Pattern C: Event Source Connections

Use for event-driven patterns (SQS -> Lambda, SNS -> SQS):

```python
def handle_event_source(tfdata):
    graphdict = tfdata["graphdict"]
    all_resource = tfdata["all_resource"]

    # Find all Lambda event source mappings
    for resource_name, resource_data in all_resource.items():
        if resource_name.startswith("aws_lambda_event_source_mapping."):
            source_arn = resource_data.get("event_source_arn", "")
            function_name = resource_data.get("function_name", "")

            # Find source resource (SQS, Kinesis, DynamoDB)
            source = find_resource_by_arn(source_arn, tfdata)
            target = find_lambda_by_name(function_name, tfdata)

            if source and target:
                # Add connection: Source -> Lambda (event flow direction)
                if target not in graphdict.get(source, []):
                    graphdict.setdefault(source, []).append(target)

    return tfdata
```

---

## Testing New Handlers

### Step 1: Create Test Terraform Fixture

Location: `tests/fixtures/aws_terraform/<pattern_name>/`

```hcl
# tests/fixtures/aws_terraform/api_gateway_lambda/main.tf
resource "aws_api_gateway_rest_api" "example" {
  name = "example-api"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = aws_api_gateway_rest_api.example.id
  type        = "AWS_PROXY"
  uri         = aws_lambda_function.handler.invoke_arn
}

resource "aws_lambda_function" "handler" {
  function_name = "api-handler"
  runtime       = "python3.9"
  handler       = "index.handler"
}
```

### Step 2: Generate Expected Output

```bash
# Generate tfdata from fixture
poetry run python terravision.py graphdata \
  --source tests/fixtures/aws_terraform/api_gateway_lambda \
  --outfile tests/json/api-gateway-lambda-tfdata.json

# Run TerraVision and capture expected output
poetry run python terravision.py draw \
  --source tests/fixtures/aws_terraform/api_gateway_lambda \
  --debug

# Review and copy expected output
cp tfdata.json tests/json/expected-api-gateway-lambda.json
```

### Step 3: Add Test Case

Location: `tests/graphmaker_unit_test.py`

```python
def test_api_gateway_lambda_integration():
    """Test API Gateway connects to Lambda function."""
    tfdata = load_json("tests/json/api-gateway-lambda-tfdata.json")

    # Run through graphmaker pipeline
    result = compile_tfdata(tfdata)

    # Verify API Gateway connects to Lambda
    api_gateway = next(
        r for r in result["graphdict"]
        if r.startswith("aws_api_gateway")
    )

    assert any(
        "lambda" in conn.lower()
        for conn in result["graphdict"][api_gateway]
    ), "API Gateway should connect to Lambda"
```

### Step 4: Run Tests

```bash
# Run specific test
poetry run pytest tests/graphmaker_unit_test.py::test_api_gateway_lambda_integration -v

# Run all tests (ensure no regressions)
poetry run pytest tests -v

# Run non-slow tests (for pre-commit)
poetry run pytest -m "not slow" -v
```

---

## Code Quality Checklist

Before committing:

```bash
# Format code with Black
poetry run black modules/

# Verify formatting
poetry run black --check -v modules/

# Run tests
poetry run pytest tests -v

# Check for regressions in existing tests
poetry run pytest tests/json/ -v
```

---

## Handler Implementation Checklist

For each new handler, verify:

- [ ] **Handler config added to `resource_handler_configs_aws.py`**
  - [ ] `description` field explains purpose and handler type (CO-011)
  - [ ] Handler type decision made (Pure Config / Hybrid / Pure Function)
  - [ ] If Pure Config: Only `transformations` array populated
  - [ ] If Hybrid: Both `transformations` and `additional_handler_function`
  - [ ] If Pure Function: Only `additional_handler_function` + justification (CO-009)
- [ ] **Custom function in `resource_handlers_aws.py` (if Hybrid or Pure Function)**
  - [ ] Docstring includes "Why custom function needed" (CO-009)
  - [ ] Safe iteration (copy lists before modifying)
  - [ ] Deep copy for metadata
  - [ ] Follows existing handler patterns from HANDLER_ARCHITECTURE.md
- [ ] **Minimal config in `cloud_config_aws.py` (only if needed)**
  - [ ] `AWS_EDGE_NODES` entry (if edge service)
  - [ ] **No** `AWS_SPECIAL_RESOURCES`, `AWS_CONSOLIDATED_NODES`, or `AWS_HIDE_NODES` entries (now in handler configs)
- [ ] **Test fixtures**
  - [ ] Terraform fixture in `tests/fixtures/aws_terraform/`
  - [ ] Expected output in `tests/json/`
  - [ ] Test case in `tests/graphmaker_unit_test.py`
- [ ] **Quality checks**
  - [ ] Black formatting applied: `poetry run black modules/`
  - [ ] All existing tests still pass: `poetry run pytest tests -v`

---

## Priority Implementation Order

### P1 - Implement First (Most Common Patterns)

1. **API Gateway** (`handle_api_gateway`, `handle_api_gateway_v2`)
2. **Event-Driven** (`handle_eventbridge`, `handle_sns`, `handle_lambda_esm`)
3. **ElastiCache** (`handle_elasticache`, `handle_elasticache_replication`)
4. **Cognito** (`handle_cognito`)

### P2 - Implement Second

5. **WAF** (`handle_waf`)
6. **SageMaker** (`handle_sagemaker`)
7. **Step Functions** (`handle_step_functions`)
8. **S3 Notifications** (`handle_s3_notifications`)
9. **Secrets Manager** (`handle_secrets_manager`)

### P3 - Implement Last (Nice to Have)

10. **Glue/Athena** (`handle_glue`, `handle_athena`)
11. **AppSync** (`handle_appsync`)

---

## Troubleshooting

### Handler Not Being Called

1. Check `AWS_SPECIAL_RESOURCES` contains correct resource type prefix
2. Verify resource type in tfdata matches exactly
3. Add debug logging: `print(f"Processing {resource_type}")`

### Connections Not Appearing

1. Check arrow direction (source -> target)
2. Verify target resource exists in graphdict
3. Check for typos in resource names

### Duplicate Connections

1. Check if resource already in connection list before adding
2. Use `if target not in graphdict[source]` guard

### Test Failures After Changes

1. Run existing tests first to establish baseline
2. Check if expected JSON needs updating (report to user first!)
3. Compare graphdict output between old and new code
