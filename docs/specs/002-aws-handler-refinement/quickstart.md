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

## Implementation Pattern

### Step 1: Add Configuration to `cloud_config_aws.py`

Location: `modules/config/cloud_config_aws.py`

```python
# 1. Add to AWS_SPECIAL_RESOURCES (maps resource type to handler function)
AWS_SPECIAL_RESOURCES = {
    # ... existing entries ...
    "aws_api_gateway_rest_api": "handle_api_gateway",
    "aws_elasticache_cluster": "handle_elasticache",
    # ... add more as needed
}

# 2. Add to AWS_CONSOLIDATED_NODES (if resource should be consolidated)
AWS_CONSOLIDATED_NODES = [
    # ... existing entries ...
    {
        "aws_api_gateway": {
            "resource_name": "aws_api_gateway.api",
            "import_location": "resource_classes.aws.app_services",
            "vpc": False,
            "edge_service": True,
        }
    },
]

# 3. Add to AWS_EDGE_NODES (if resource is an edge service)
AWS_EDGE_NODES = [
    # ... existing entries ...
    "aws_api_gateway",
    "aws_appsync",
    "aws_cognito",
]

# 4. Add to AWS_HIDE_NODES (if resource should be hidden from diagram)
AWS_HIDE_NODES = [
    # ... existing entries ...
    "aws_api_gateway_stage",
    "aws_api_gateway_deployment",
]
```

### Step 2: Add Handler Function to `resource_handlers_aws.py`

Location: `modules/resource_handlers_aws.py`

```python
def handle_api_gateway(tfdata: dict) -> dict:
    """
    Handle API Gateway resources.

    This handler:
    1. Consolidates API Gateway sub-resources into single node
    2. Detects Lambda/Step Functions integrations
    3. Positions as edge service outside VPC

    Args:
        tfdata: Dictionary containing graphdict, meta_data, all_resource

    Returns:
        Modified tfdata dictionary
    """
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})
    all_resource = tfdata.get("all_resource", {})

    # Find all API Gateway REST APIs
    api_gateways = [
        r for r in graphdict.keys()
        if r.startswith("aws_api_gateway_rest_api.")
    ]

    for api in api_gateways:
        # Find integrations by looking for aws_api_gateway_integration resources
        integrations = find_integrations_for_api(api, all_resource)

        for integration in integrations:
            # Parse integration URI to find Lambda/Step Functions
            target = parse_integration_uri(integration)
            if target and target in graphdict:
                # Add connection: API Gateway -> Target
                if target not in graphdict[api]:
                    graphdict[api].append(target)

    # If no integrations found, add external placeholder
    if not graphdict.get(api, []):
        external_node = "aws_external_integration.external"
        graphdict[api] = [external_node]
        meta_data[external_node] = {"label": "External Integration"}

    return tfdata


def find_integrations_for_api(api: str, all_resource: dict) -> list:
    """Find all integrations associated with an API Gateway."""
    integrations = []
    api_id = api.split(".")[-1]

    for resource_name, resource_data in all_resource.items():
        if resource_name.startswith("aws_api_gateway_integration."):
            # Check if this integration belongs to our API
            if resource_data.get("rest_api_id") == api_id:
                integrations.append(resource_data)

    return integrations


def parse_integration_uri(integration: dict) -> str:
    """Parse integration URI to extract Lambda/Step Functions ARN."""
    uri = integration.get("uri", "")

    # Lambda integration pattern
    if ":lambda:" in uri:
        # Extract function name from ARN
        parts = uri.split(":")
        for part in parts:
            if "function:" in part:
                return f"aws_lambda_function.{part.split('/')[-1]}"

    # Step Functions integration pattern
    if ":states:" in uri:
        parts = uri.split(":")
        for part in parts:
            if "stateMachine:" in part:
                return f"aws_sfn_state_machine.{part.split('/')[-1]}"

    return None
```

### Step 3: Register Handler in Dispatch

The handler is automatically registered via `AWS_SPECIAL_RESOURCES`. The dispatch happens in `graphmaker.py`:

```python
# In graphmaker.py (no modification needed - existing dispatch pattern)
def handle_special_resources(tfdata):
    config = load_config(provider)
    special_resources = config.SPECIAL_RESOURCES

    for resource_type, handler_name in special_resources.items():
        if any(r.startswith(resource_type) for r in tfdata["graphdict"]):
            handler = getattr(resource_handlers, handler_name)
            tfdata = handler(tfdata)

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

- [ ] Configuration added to `cloud_config_aws.py`
  - [ ] `AWS_SPECIAL_RESOURCES` entry
  - [ ] `AWS_CONSOLIDATED_NODES` if consolidating
  - [ ] `AWS_EDGE_NODES` if edge service
  - [ ] `AWS_HIDE_NODES` for sub-resources
- [ ] Handler function in `resource_handlers_aws.py`
  - [ ] Docstring with purpose and behavior
  - [ ] Safe iteration (copy lists before modifying)
  - [ ] Deep copy for metadata
  - [ ] Sorted iteration for determinism
- [ ] Test fixture in `tests/fixtures/aws_terraform/`
- [ ] Expected output in `tests/json/`
- [ ] Test case in `tests/graphmaker_unit_test.py`
- [ ] Black formatting applied
- [ ] All existing tests still pass

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
