# Testing Strategy for Phase 4 Features

## Objective

Define unit and integration testing practices for the new functionality introduced in Phase 4, including performance considerations and how to update expected outputs.

## Unit Tests

### Location
`tests/unit/test_aws_handlers.py`

### Coverage

**Test Classes**:
- `TestAwsHandleSg` - Security group orphan preservation
- `TestAwsHandleLb` - Classic ELB support
- `TestAwsHandleSubnetAzs` - AZ suffix logic and hidden key initialization
- `TestAwsHandleEfs` - EFS mount target grouping
- `TestLinkSqsQueuePolicy` - Lambda → Queue transitive linking
- `TestLinkEc2ToIamRoles` - EC2 → Role transitive linking
- `TestHandleSpecialCases` - DISCONNECT_LIST behavior

### Test Patterns

**Arrange-Act-Assert Pattern**:
```python
def test_sqs_policy_creates_transitive_link(self):
    # Arrange: Build minimal tfdata samples
    tfdata = {
        "graphdict": {
            "aws_sqs_queue.main": [],
            "aws_sqs_queue_policy.main": ["aws_sqs_queue.main"],
            "aws_lambda_function.processor": ["aws_sqs_queue_policy.main"],
        },
        "metadata": {},
    }
    
    # Act: Run specific handler function
    result = handle_special_cases(tfdata)
    
    # Assert: Verify transitive link was created
    self.assertIn(
        "aws_sqs_queue.main", 
        result["graphdict"]["aws_lambda_function.processor"]
    )
```

**Type Safety Testing**:
```python
def test_handle_nodes_returns_optional_tuple(self):
    """Test that handle_nodes() guards against None returns."""
    # Test with unavailable resource type
    node, resources = handle_nodes(
        "unavailable_type.test",
        cluster, cloud_group, canvas,
        tfdata, []
    )
    
    # Should return None for node, but still return resources list
    self.assertIsNone(node)
    self.assertIsInstance(resources, list)
```

**Edge Case Testing**:
```python
# Test empty graphs
def test_empty_graphdict_handled(self):
    tfdata = {"graphdict": {}, "metadata": {}}
    result = handle_special_cases(tfdata)
    self.assertEqual(result["graphdict"], {})

# Test missing metadata
def test_handles_missing_filesystem_metadata(self):
    tfdata = {
        "graphdict": {"aws_efs_file_system.test": []},
        "meta_data": {}  # No metadata for file system
    }
    # Should not crash
    result = aws_handle_efs(tfdata)
    self.assertIsNotNone(result)
```

---

## Integration Tests

### Location
- `tests/integration/test_multicloud.py`
- `tests/integration_test.py`

### Updated Fixtures
- `tests/json/expected-wordpress.json`
- `tests/json/bastion-expected.json`

### Strategy

**Validate Structural Changes**:
```python
def test_graphdata_output(source, expected):
    """Validate graph structure matches expected output."""
    actual = generate_graph(source)
    expected = load_expected(expected)
    
    # Compare graph structure
    assert actual == expected, "JSON output doesn't match expected"
```

**Key Relationship Validation**:
```python
def test_efs_mount_targets_grouped(self):
    """Verify EFS mount targets are nested under file system."""
    tfdata = parse_terraform(source)
    
    # Mount targets should be children of EFS
    assert "aws_efs_mount_target.this" in tfdata["graphdict"]["aws_efs_file_system.efs"]
    
    # Mount targets should not be standalone nodes
    assert "aws_efs_mount_target.this" not in tfdata["graphdict"]
```

---

## Updating Expected Outputs

### When to Update

Update integration test fixtures when:
1. Intentional structural changes (e.g., grouping, transitive linking)
2. Bug fixes that change graph output
3. New handler logic that affects relationships

### Steps to Update

```bash
# 1. Run tests to identify failures
poetry run pytest -m "not slow"

# 2. If integration fails due to expected JSON mismatch:
#    a. Inspect diffs in test output
poetry run pytest tests/integration_test.py::test_graphdata_output -vv

# 3. Regenerate expected output for specific test case
poetry run python terravision.py graphdata \
  --source tests/json/wordpress-tfdata.json \
  --outfile tests/json/expected-wordpress.json

# 4. Verify unit tests validate the new structures
poetry run pytest tests/unit/test_aws_handlers.py -v

# 5. Re-run all tests to confirm consistency
poetry run pytest -m "not slow"
```

### Example: Updating WordPress Fixture

```bash
# Generate new expected output
poetry run python terravision.py graphdata \
  --source tests/json/wordpress-tfdata.json \
  --outfile tests/json/wordpress-expected-new.json

# Compare with old expected output
diff tests/json/expected-wordpress.json tests/json/wordpress-expected-new.json

# If changes are correct, replace old fixture
mv tests/json/wordpress-expected-new.json tests/json/expected-wordpress.json

# Verify tests pass
poetry run pytest tests/integration_test.py::test_graphdata_output -k wordpress
```

---

## Performance Testing

### Location
`tests/performance_test.py`

### Considerations

**Handler Complexity**:
- Avoid O(n²) scans; index by resource ID when possible
- Use dictionary lookups instead of list iterations
- Cache repeated operations

**Example: Efficient Lookup**:
```python
# BAD: O(n²) - iterates for each resource
for resource in resources:
    for dep in all_deps:
        if dep matches resource:
            link(resource, dep)

# GOOD: O(n) - pre-index then lookup
# Build index once
resource_index = {r.id: r for r in resources}

# Fast lookups
for dep in all_deps:
    if dep.parent_id in resource_index:
        link(resource_index[dep.parent_id], dep)
```

**NodeFactory Resolution**:
```python
# Cache resolved classes to avoid repeated lookups
class NodeFactory:
    def __init__(self):
        self._cache = {}
    
    def resolve_class(self, resource_type, module_namespace=None):
        cache_key = (resource_type, id(module_namespace))
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        cls = self._resolve_uncached(resource_type, module_namespace)
        self._cache[cache_key] = cls
        return cls
```

**Drawing/subprocess.run Timing**:
```python
import time

def test_gvpr_performance():
    """Verify gvpr subprocess execution completes in reasonable time."""
    start = time.time()
    
    subprocess.run(
        ["gvpr", "-c", "-q", "-f", script, input, "-o", output],
        check=True,
        capture_output=True,
        text=True,
    )
    
    elapsed = time.time() - start
    assert elapsed < 5.0, f"gvpr took {elapsed}s (threshold: 5s)"
```

### Performance Test Strategy

```python
def test_large_graph_performance(self):
    """Test handler performance with large graphs."""
    # Create large test data (1000+ resources)
    tfdata = generate_large_tfdata(resource_count=1000)
    
    start = time.time()
    result = aws_handle_efs(tfdata)
    elapsed = time.time() - start
    
    # Should complete in reasonable time
    assert elapsed < 2.0, f"Handler took {elapsed}s for 1000 resources"
```

---

## Pre-commit and CI

### Pre-commit Hooks

```bash
# Run pre-commit hooks manually
poetry run pre-commit run --all-files

# What runs:
# - pytest on non-slow tests
# - black code formatting
# - isort import sorting
# - trailing whitespace removal
# - YAML validation
```

### CI Pipeline

**File**: `.github/workflows/lint-and-test.yml`

**Workflow**:
1. Format check (Black/Isort)
2. Lint check (if configured)
3. Run fast tests (`pytest -m "not slow"`)
4. Report coverage

**Local CI Simulation**:
```bash
# Run same checks as CI
poetry run black --check .
poetry run isort --check .
poetry run pytest -m "not slow" --tb=short
```

---

## Example Commands

### Installation
```bash
poetry install
```

### Run Unit Tests
```bash
# All unit tests
poetry run pytest tests/unit/ -v

# Specific test class
poetry run pytest tests/unit/test_aws_handlers.py::TestAwsHandleEfs -v

# Single test
poetry run pytest tests/unit/test_aws_handlers.py::TestAwsHandleEfs::test_groups_mount_targets_under_filesystem -v
```

### Run Integration Tests
```bash
# All integration tests
poetry run pytest tests/integration/ -v

# Specific integration test
poetry run pytest tests/integration_test.py::test_graphdata_output -k wordpress -v
```

### Run All Tests
```bash
# All tests (including slow)
poetry run pytest

# Fast tests only (recommended for development)
poetry run pytest -m "not slow"

# With coverage
poetry run pytest --cov=modules --cov-report=html
```

### Performance Testing
```bash
poetry run pytest tests/performance_test.py -v
```

---

## References

**Handler Code**:
- `modules/resource_handlers/aws.py` - All handlers and transitive links
- `modules/node_factory.py` - resolve_class() method
- `modules/drawing.py` - Optional returns and subprocess.run()

**Test Files**:
- `tests/unit/test_aws_handlers.py` - Patterns for Phase 4 unit tests
- `tests/integration_test.py` - Integration test patterns
- `tests/json/expected-wordpress.json` - Integration test fixture
- `tests/json/bastion-expected.json` - Integration test fixture

**Configuration**:
- `pytest.ini` - Pytest configuration and markers
- `.pre-commit-config.yaml` - Pre-commit hook configuration
- `.github/workflows/lint-and-test.yml` - CI pipeline

---

## Test Coverage Targets

**Current Coverage** (Phase 4):
- **Unit Tests**: 196/196 passing (100%)
- **Integration Tests**: 83/83 passing (100%)
- **Total**: 279/279 passing (100%)

**Coverage by Module**:
- `modules/resource_handlers/aws.py` - 29 tests
- `modules/resource_handlers/azure.py` - 10 tests
- `modules/resource_handlers/gcp.py` - 22 tests
- `modules/graph_utils.py` - 40 tests
- `modules/provider_utils.py` - 32 tests
- `modules/terraform_utils.py` - 22 tests
- `modules/drawing.py` - Covered by integration tests

**New Tests Added in Phase 4**:
- 8 test classes for bug fixes
- 29 total test methods
- Coverage for transitive linking, grouping, type safety

---

## Best Practices

### 1. Test Naming
```python
# Good: Descriptive test names
def test_efs_mount_targets_grouped_under_filesystem(self):
def test_lambda_connects_directly_to_queue_via_policy(self):
def test_handle_nodes_returns_none_for_unavailable_type(self):

# Bad: Vague test names
def test_efs(self):
def test_linking(self):
def test_returns_none(self):
```

### 2. Test Independence
```python
# Good: Each test is self-contained
class TestAwsHandleEfs(unittest.TestCase):
    def setUp(self):
        # Fresh test data for each test
        self.tfdata = self._create_test_data()
    
    def test_groups_mount_targets(self):
        result = aws_handle_efs(self.tfdata)
        # Assert on result, not shared state

# Bad: Tests depend on each other
class TestAwsHandleEfs(unittest.TestCase):
    tfdata = {...}  # Shared across tests
    
    def test_step1(self):
        aws_handle_efs(self.tfdata)
    
    def test_step2(self):
        # Depends on step1 running first
```

### 3. Assert Specificity
```python
# Good: Specific assertions
self.assertEqual(result["graphdict"]["aws_efs.fs"], ["aws_efs_mount_target.mt1"])
self.assertIsNone(node)
self.assertIn("aws_sqs_queue.main", result["graphdict"]["aws_lambda.fn"])

# Bad: Vague assertions
self.assertTrue(result)  # What are we testing?
self.assertIsNotNone(result)  # Too general
```

### 4. Error Message Context
```python
# Good: Helpful error messages
self.assertEqual(
    actual, 
    expected,
    f"EFS mount targets not grouped. Expected {expected}, got {actual}"
)

# Bad: No context
self.assertEqual(actual, expected)
```

---

## Troubleshooting Test Failures

### Integration Test Mismatch
```bash
# Problem: JSON output doesn't match expected
# Solution: Inspect diff and update fixture if correct

# View detailed diff
poetry run pytest tests/integration_test.py::test_graphdata_output -vv | less

# Regenerate if changes are intentional
poetry run python terravision.py graphdata \
  --source tests/json/wordpress-tfdata.json \
  --outfile tests/json/expected-wordpress.json
```

### Unit Test Failures
```bash
# Problem: Specific handler test failing
# Solution: Debug with verbose output

# Run with verbose output
poetry run pytest tests/unit/test_aws_handlers.py::TestAwsHandleEfs -vv

# Add print debugging
import pdb; pdb.set_trace()  # In test code

# Run single test with debugger
poetry run pytest tests/unit/test_aws_handlers.py::TestAwsHandleEfs::test_groups_mount_targets -vv -s
```

### Performance Degradation
```bash
# Problem: Tests running slowly
# Solution: Profile and optimize

# Run with timing
poetry run pytest tests/performance_test.py -vv --durations=10

# Profile specific test
poetry run python -m cProfile -o profile.stats terravision.py draw --source tests/json/wordpress-tfdata.json
```
