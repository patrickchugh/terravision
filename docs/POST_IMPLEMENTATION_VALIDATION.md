# Post-Implementation Validation Checklist

**Purpose**: Catch implementation issues early before declaring "all tests passed"

**When to Use**: After implementing ANY handler, transformer, or configuration change

---

## 1. Test Suite Validation

```bash
# During development: Run fast tests only (excludes slow integration tests)
poetry run pytest tests -v -m "not slow"

# At task completion: Run ALL tests including slow ones
poetry run pytest tests -v

# Verify test count hasn't decreased
# Expected: 139+ tests passing
```

- [ ] Fast tests pass during development (`-m "not slow"`)
- [ ] ALL tests pass at task completion (including slow tests)
- [ ] Test count is equal or higher than baseline (139+)
- [ ] No new pytest warnings introduced

---

## 2. Connection Direction Validation

**Purpose**: Verify arrows point in logically correct direction

For EACH test fixture created or modified:

```bash
# Generate output JSON
poetry run python terravision.py graphdata \
  --source tests/json/<fixture>-tfdata.json \
  --outfile /tmp/<fixture>-debug.json

# Inspect connections
cat /tmp/<fixture>-debug.json | jq .
```

**Check Each Resource Type**:

- [ ] **Event Sources → Consumers**: Events flow in correct direction
  - ✅ SNS → SQS, SNS → Lambda
  - ✅ EventBridge → Lambda
  - ✅ SQS → Lambda (via event source mapping)
  - ✅ DynamoDB → Lambda (via streams)
  - ✅ Kinesis → Lambda (via event source mapping)
- [ ] **API Gateway → Backends**: Requests flow correctly
  - ✅ API Gateway → Lambda
  - ✅ API Gateway → Step Functions
  - ✅ API Gateway → HTTP backends
- [ ] **Load Balancers → Compute**: Traffic flows correctly
  - ✅ ELB → ALB instances → Compute resources
  - ✅ ALB → ECS/Fargate
  - ✅ NO backward arrows: Compute → ELB ❌
- [ ] **Data Sources → Consumers**: Data access is clear
  - ✅ Lambda → DynamoDB
  - ✅ Lambda → S3
  - ✅ Application → RDS

**Common Issues**:
- Bidirectional arrows (both A → B and B → A) - usually indicates error
- Reversed arrows (consumer → source instead of source → consumer)
- Circular references being incorrectly resolved

---

## 3. Orphaned Resources Validation

**Purpose**: Find resources with no connections when they should have them

For EACH test fixture:

```bash
# Find resources with empty connection lists
cat /tmp/<fixture>-debug.json | jq 'to_entries | map(select(.value == [])) | from_entries'
```

**Investigate EACH orphaned resource**:

- [ ] **Is this expected?** (e.g., `aws_group.shared_services` may have no outbound connections)
- [ ] **Should it have connections?** Check the Terraform source:
  - Does it reference other resources?
  - Do other resources reference it?
  - Are there implicit relationships (event source mappings, etc.)?
- [ ] **Is an intermediary blocking the connection?**
  - Check for intermediary resources that should create transitive links
  - Verify intermediaries are being properly removed
  - Verify direct connections are being created

**Common Orphaned Resource Patterns**:
- Event sources without Lambda connections (missing event source mapping handler)
- Lambda functions without event source connections (intermediary not removed)
- Resources in VPCs not showing subnet placement
- Security groups not showing protected resources

---

## 4. Duplicate Connection Prevention

**Purpose**: Verify no duplicate connections exist in output

For EACH test fixture:

```bash
# Check for duplicates in connections
cat /tmp/<fixture>-debug.json | jq 'to_entries | map({key: .key, duplicates: (.value | group_by(.) | map(select(length > 1)) | flatten)}) | map(select(.duplicates | length > 0))'
```

**Expected Result**: Empty array `[]` (no duplicates)

**If duplicates found**:
- [ ] Identify which code path is creating the duplicate
- [ ] Check if duplicate prevention logic is missing
- [ ] Verify fix prevents duplicates at SOURCE, not via deduplication sweep

**Common Duplicate Sources**:
- `graphmaker.reverse_relations()` - missing duplicate check when reversing arrows
- `annotations.py` - missing duplicate check when adding manual connections
- `graphmaker.handle_singular_references()` - missing duplicate check for numbered instances
- `helpers.append_dictlist()` - missing duplicate check for auto-annotations
- Handler functions creating connections without checking existing

---

## 5. Intermediary Link Validation

**Purpose**: Verify intermediary resources are properly handled

**Pattern**: `A → intermediary → B` should become `A → B` (intermediary removed)

For EACH intermediary resource type:

```bash
# Check if intermediaries still exist in final output
cat /tmp/<fixture>-debug.json | jq 'keys | map(select(contains("<intermediary_pattern>")))'
```

**Examples**:
- `aws_lambda_event_source_mapping` - should be removed, direct event source → Lambda created
- `aws_api_gateway_integration` - may exist (provides context) OR be removed (config choice)
- `aws_lb` - should be converted to `aws_alb.elb~1`, `aws_alb.elb~2`, etc.

**If intermediary still exists**:
- [ ] Is this intentional? (Some intermediaries provide useful context)
- [ ] Should it create transitive links? Check transformer configuration
- [ ] Are both source AND target found? (Transformer requires both)
- [ ] Is `remove_intermediary=True` set correctly?

**If intermediary is removed**:
- [ ] Are transitive links created? (Check source → target exists)
- [ ] Are dangling references cleaned up? (No other nodes point to removed intermediary)
- [ ] Are metadata entries cleaned up? (Removed from `meta_data` dict)

---

## 6. Numbered Resource Expansion Validation

**Purpose**: Verify count/for_each expansion works correctly

For resources with count > 1:

```bash
# Check for numbered instances (~ suffix)
cat /tmp/<fixture>-debug.json | jq 'keys | map(select(contains("~")))'
```

**Verify**:
- [ ] Numbered instances exist (e.g., `aws_alb.elb~1`, `aws_alb.elb~2`, `aws_alb.elb~3`)
- [ ] Original resource is removed (e.g., `aws_lb.elb` should not exist if expanded)
- [ ] Connections follow numbering (e.g., `web~1 → db~1`, `web~2 → db~2`)
- [ ] Parent resources link to all numbered instances

---

## 7. Expected Output Comparison

**Purpose**: Verify expected output matches actual output

For EACH test fixture with expected output:

```bash
# Compare expected vs actual
diff tests/json/expected-<fixture>.json /tmp/<fixture>-debug.json
```

**If differences found**:
- [ ] Are differences intentional (new feature)?
- [ ] Update expected output: `cp /tmp/<fixture>-debug.json tests/json/expected-<fixture>.json`
- [ ] Document why expected output changed
- [ ] Re-run tests to verify they pass with updated expected output

---

## 8. Rendering Quality Validation (MANDATORY)

**Purpose**: Prevent visual confusion and messy diagrams from rendering issues

**CRITICAL**: This validation is MANDATORY after Phase 5 rendering issues were discovered. These checks prevent:
- Resources duplicated across multiple subnets (Lambda appearing in cache_a AND cache_b)
- Cross-subnet connection clutter (redis~3 in cache_c connecting to Lambda only in cache_a/cache_b)
- Incorrect numbered resource distribution (all numbered instances in all subnets instead of 1:1 mapping)

For EACH test fixture:

```bash
# Generate graph JSON output
poetry run python terravision.py graphdata \
  --source tests/json/<fixture>-tfdata.json \
  --outfile /tmp/<fixture>-debug.json

# Inspect parent-child relationships
cat /tmp/<fixture>-debug.json | jq '.graphdict'
```

### 8.1 Resource Duplication Check
- [ ] **No resource duplication across subnets**: Same resource doesn't appear as child of multiple subnets
  ```bash
  # Example issue: Lambda in BOTH cache_a and cache_b
  # "aws_subnet.cache_a": ["aws_lambda_function.reader"],
  # "aws_subnet.cache_b": ["aws_lambda_function.reader"]  ❌ WRONG

  # Correct: Lambda at VPC level
  # "aws_vpc.main": ["aws_lambda_function.reader"]  ✅ CORRECT
  ```
- [ ] **Resources appear at correct hierarchy level**:
  - VPC-level resources (Lambda, NAT Gateway, ElastiCache subnet groups) under VPC, not subnets
  - Subnet-specific resources (numbered instances like redis~1) under specific subnet

### 8.2 Numbered Resource Distribution Check
- [ ] **1:1 subnet-to-instance mapping**: Numbered instances distributed correctly across subnets
  ```bash
  # Correct pattern: Each subnet gets ONE numbered instance
  # "aws_subnet.cache_a": ["aws_elasticache_replication_group.redis~1"]  ✅
  # "aws_subnet.cache_b": ["aws_elasticache_replication_group.redis~2"]  ✅
  # "aws_subnet.cache_c": ["aws_elasticache_replication_group.redis~3"]  ✅

  # WRONG pattern: Same instance in multiple subnets
  # "aws_subnet.cache_a": ["redis~1", "redis~2"]  ❌
  ```
- [ ] **No numbered instances in wrong subnets**: redis~1 only in first subnet, redis~2 only in second, etc.

### 8.3 Cross-Subnet Connection Check
- [ ] **No cross-subnet connection clutter**: Numbered resources only connect to unnumbered resources in same subnet
  ```bash
  # Check: If redis~3 is in cache_c, and Lambda is only in cache_a/cache_b, redis~3 should NOT connect to Lambda

  # Find numbered resources and their connections
  cat /tmp/<fixture>-debug.json | jq '.graphdict | to_entries | map(select(.key | contains("~"))) | map({resource: .key, connections: .value})'

  # Verify numbered resources don't connect to unnumbered resources in different subnets
  ```
- [ ] **Subnet locality respected**: Connections respect subnet boundaries unless architecturally correct (e.g., VPC-level resources)

### 8.4 Visual Layout Check (Manual Review)
```bash
# Generate actual diagram (optional but helpful)
poetry run python terravision.py draw \
  --source tests/json/<fixture>-tfdata.json \
  --outfile /tmp/<fixture>.png
```

**Manual Review**:
- [ ] All expected resources appear
- [ ] Connections flow logically (top to bottom, left to right)
- [ ] Grouping makes sense (VPCs, availability zones, etc.)
- [ ] No visual clutter (unnecessary crossing lines, duplicate resources)
- [ ] No confusing overlaps or ambiguous relationships
- [ ] Labels are clear and readable

**Common Rendering Issues**:
- Multi-subnet resources appearing in all subnets → Move to VPC level
- All numbered instances in one subnet → Fix 1:1 mapping logic
- Crossing lines from numbered to unnumbered resources → Add cross-subnet cleanup
- Resources with multiple parents when they should have one → Fix parent assignment logic

---

## 9. Integration Test Coverage

**Purpose**: Verify test fixtures cover the implementation

For EACH handler/transformer:

- [ ] Test fixture exists in `tests/fixtures/aws_terraform/`
- [ ] Expected output exists in `tests/json/expected-*.json`
- [ ] Integration test exists in `tests/integration_test.py`
- [ ] Test actually exercises the handler (verify handler is called)

**Add test if missing**:
```python
@pytest.mark.parametrize("fixture_file,expected_file", [
    ("new-pattern-tfdata.json", "expected-new-pattern.json"),
])
def test_graphdata_output(fixture_file, expected_file):
    # Test implementation...
```

---

## 10. Documentation Updates

**Purpose**: Keep documentation in sync with implementation

- [ ] CLAUDE.md updated with new patterns (if applicable)
- [ ] docs/HANDLER_CONFIG_GUIDE.md updated with new handlers
- [ ] docs/specs/002-aws-handler-refinement/tasks.md status updated
- [ ] Handler config includes clear description and comments
- [ ] Complex logic has inline comments explaining why

---

## Summary

This checklist is **MANDATORY** before declaring any phase or handler complete. It catches:
- Functional issues (wrong connections, orphaned resources, duplicates)
- Implementation issues (intermediaries not handled, numbering broken)
- Rendering issues (visual confusion, resource duplication, crossing lines)
- Documentation gaps

**The validation checklist is the last line of defense against shipping broken handlers.**
