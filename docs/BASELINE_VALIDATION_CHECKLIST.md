# Baseline Validation Checklist

**Purpose**: This checklist MUST be completed before implementing any custom resource handler.

**Constitutional Requirement**: CO-005.1 - "Most services MUST NOT have custom handlers"

---

## ⚠️ MANDATORY PRE-IMPLEMENTATION VALIDATION

Complete ALL steps below. If validation passes, **STOP** - no handler is needed!

### Step 1: Create Test Terraform Code

```bash
# Create realistic Terraform configuration for the resource type
mkdir -p tests/fixtures/aws_terraform/test_<resource_name>
cd tests/fixtures/aws_terraform/test_<resource_name>

# Write main.tf with representative resource configuration
# Include typical connections (e.g., API Gateway → Lambda, ECS → RDS)
```

**Requirements**:
- [ ] Test code represents real-world usage patterns
- [ ] Includes connections to other resources (not isolated)
- [ ] Uses typical configurations (not contrived edge cases)

---

### Step 2: Generate Baseline Diagram

```bash
# Generate diagram WITHOUT any custom handler
# IMPORTANT: Always use --debug flag to save tfdata.json for test reuse
cd /Users/patrick/git/terravision
poetry run python terravision.py graphdata \
  --source tests/fixtures/aws_terraform/test_<resource_name> \
  --outfile baseline-<resource_name>.json \
  --debug
```

**Why --debug flag?**
- Saves `tfdata.json` containing Terraform plan output
- Allows rapid iteration without re-running `terraform plan`
- Enables reusing tfdata.json for integration tests
- Example: `poetry run python terravision.py graphdata --source tfdata.json --outfile output.json`

**Requirements**:
- [ ] Baseline generated successfully with `--debug` flag
- [ ] `tfdata.json` file created in current directory
- [ ] No custom handler exists for this resource type
- [ ] Output saved for analysis

---

### Step 3: Analyze Baseline Output

Open `baseline-<resource_name>.json` and evaluate:

#### 3.1 Resource Visibility
- [ ] **All resources appear in the graph**
- [ ] **Icons are correct** (or generic icons are acceptable)
- [ ] **Labels are meaningful** (resource type + name visible)

#### 3.2 Connections/Relationships
- [ ] **Dependencies are shown** (arrows between connected resources)
- [ ] **Direction is correct** (producer → consumer, parent → child)
- [ ] **Critical relationships are present** (e.g., Lambda → DynamoDB, API → Lambda)

#### 3.3 Hierarchy/Grouping
- [ ] **VPC hierarchy works** (VPC → subnet → resources where applicable)
- [ ] **Logical grouping** (shared services grouped, related resources connected)
- [ ] **No orphaned resources** (everything has proper parent/connections)

#### 3.4 User Understanding
- [ ] **Architecture is clear** - can users understand the system?
- [ ] **Data flow is visible** - can users trace request/data paths?
- [ ] **No critical confusion** - nothing misleading or ambiguous

#### 3.5 Rendering and Visual Layout
- [ ] **No resource duplication** - same resource doesn't appear in multiple locations (e.g., Lambda in multiple subnets when it should be at VPC level)
- [ ] **Numbered resource placement** - numbered instances (~1, ~2, ~3) distributed 1:1 with parent resources (e.g., subnet_a gets ~1, subnet_b gets ~2)
- [ ] **No cross-subnet connections** - numbered resources don't create connections to unnumbered resources in different subnets
- [ ] **Single logical parent** - resources don't appear as children of multiple parents unless architecturally correct (e.g., shared services)
- [ ] **Clean connection routing** - no unnecessary crossing lines or messy connection patterns that obscure relationships

**Common Rendering Issues to Check**:
- Multi-subnet resources (Lambda, ElastiCache) appearing in all subnets instead of one logical location
- Numbered resources (redis~1, redis~2, redis~3) all connecting to the same unnumbered resource (lambda) creating visual clutter
- Resources placed at wrong hierarchy level (subnet-level vs VPC-level)

---

### Step 4: Decision Matrix

| Check Category | Pass? | Notes |
|---------------|-------|-------|
| Resource Visibility | ☐ Yes ☐ No | |
| Connections/Relationships | ☐ Yes ☐ No | |
| Hierarchy/Grouping | ☐ Yes ☐ No | |
| User Understanding | ☐ Yes ☐ No | |
| Rendering/Visual Layout | ☐ Yes ☐ No | |

**Decision Rules**:
- ✅ **ALL checks pass** → **STOP! No handler needed.** Trust the baseline.
- ❌ **ANY check fails** → Document specific issues, proceed to Step 5

---

### Step 5: Document Justification (Required if proceeding)

If baseline validation failed, answer ALL questions below:

#### 5.1 What specific problem exists?
```
Describe the exact diagram issue (not subjective preference):
- What is confusing/missing/incorrect?
- What user question can't be answered from the diagram?
- What critical relationship is not visible?

Example (Good): "Security group ingress/egress rules not shown - users can't understand network security model"
Example (Bad): "Would look better with direct connections instead of via integration resources"
```

#### 5.2 Why can't baseline handle this?
```
Explain why Terraform dependency graph is insufficient:
- Is the information not in Terraform at all?
- Is it in complex nested metadata that needs parsing?
- Is there implicit knowledge not in the code?

Example (Good): "SG rules are in nested 'ingress' blocks, not Terraform dependencies - requires custom parsing"
Example (Bad): "Integration URIs could theoretically be parsed" (but they show as 'true' in plan!)
```

#### 5.3 Baseline vs. Expected Output
```
Baseline Output:
<paste actual JSON showing the problem>

Expected Output (with handler):
<paste what it SHOULD look like>

Improvement Justification:
<explain how expected output solves the documented problem>
```

#### 5.4 Have you validated the improvement?
- [ ] Created proof-of-concept handler
- [ ] Tested with real Terraform code (not assumptions!)
- [ ] Verified computed values are available (URIs, ARNs, etc.)
- [ ] Confirmed it improves clarity (not just "different")

---

## Real Examples

### ✅ Example 1: Security Groups (Handler Justified)

**Baseline Output**:
```json
{
  "aws_instance.web": ["aws_security_group.web_sg"],
  "aws_security_group.web_sg": []
}
```

**Problem**:
- ☐ Resource visibility - ✅ PASS (SG visible)
- ☐ Connections - ❌ FAIL (ingress/egress rules not shown)
- ☐ Hierarchy - ✅ PASS (EC2 → SG clear)
- ☐ User understanding - ❌ FAIL (can't see which ports/protocols allowed)

**Justification**:
- Users can't understand network security model
- SG rules in nested `ingress` blocks, not Terraform dependencies
- Requires parsing rule blocks to create directional arrows

**Decision**: ✅ Handler needed

---

### ❌ Example 2: API Gateway (Handler NOT Justified)

**Baseline Output**:
```json
{
  "aws_lambda_function.api_handler": ["aws_api_gateway_integration.lambda"],
  "aws_api_gateway_integration.lambda": ["aws_api_gateway_method.get_users"],
  "aws_api_gateway_method.get_users": ["aws_api_gateway_resource.users"],
  "aws_api_gateway_resource.users": ["aws_api_gateway_rest_api.example"]
}
```

**Analysis**:
- ☑ Resource visibility - ✅ PASS (all visible)
- ☑ Connections - ✅ PASS (Lambda → Integration → Method → Resource → API)
- ☑ Hierarchy - ✅ PASS (method → resource → API clear)
- ☑ User understanding - ✅ PASS (can understand Lambda serves API Gateway)

**Attempted Justification** (rejected):
- "Could parse integration URIs to create direct Lambda → API connection"
- Problem: URIs show as `true` in terraform plan, can't be parsed!
- Result: Created unhelpful placeholder nodes instead

**Decision**: ❌ No handler needed - baseline is sufficient!

---

## Common Anti-Patterns (DO NOT DO)

### ❌ "It would look better/cleaner"
**Why wrong**: Subjective preference, not a functional improvement. Baseline works.

### ❌ "Direct connections instead of intermediates"
**Why wrong**: Intermediate resources (integrations, permissions) provide useful context.

### ❌ "Consolidate everything into one node"
**Why wrong**: May hide important details. Use `AWS_CONSOLIDATED_NODES` if truly needed.

### ❌ "Parse computed values for better labels"
**Why wrong**: Computed values show as `true` in terraform plan - can't be parsed!

### ❌ "Add placeholder nodes for external systems"
**Why wrong**: Terraform doesn't know about external systems - use annotations instead.

---

## Constitutional Compliance

This checklist enforces:
- **CO-005.1**: Most services MUST NOT have custom handlers
- **Core Principle I**: Code as Source of Truth (Terraform dependencies ARE the truth)
- **Core Principle IV**: Dynamic Parsing (baseline already does this!)

**Reminder**: The burden of proof is on the handler implementer to justify why baseline is insufficient.

---

## Sign-Off

Before implementing a handler, complete this sign-off:

```
Resource Type: _________________
Date: _________________
Validator: _________________

I have completed all steps in this checklist and confirm:
- [ ] Baseline validation was performed with real Terraform code
- [ ] ALL validation checks were objectively evaluated
- [ ] Specific problems were documented with evidence
- [ ] Justification was reviewed and approved
- [ ] This handler is truly necessary (baseline is insufficient)

Baseline validation result: PASS / FAIL
Decision: PROCEED / STOP (no handler needed)
```

---

**Remember**: Most resources (80-90%) work perfectly with baseline parsing. Handlers are the exception, not the rule!

---

## Post-Implementation Validation

After implementing a handler (if baseline validation failed), you MUST complete the comprehensive validation checklist in **[`docs/POST_IMPLEMENTATION_VALIDATION.md`](POST_IMPLEMENTATION_VALIDATION.md)**.

That checklist validates:
1. **Test Suite**: All tests pass, test count hasn't decreased
2. **Connection Directions**: Arrows point in correct direction (event sources → consumers, APIs → backends, etc.)
3. **Orphaned Resources**: No resources missing expected connections
4. **Duplicate Connections**: No duplicate entries in connection lists
5. **Intermediary Links**: Transitive connections work properly when intermediaries are removed
6. **Numbered Resources**: Count/for_each expansion works correctly
7. **Expected Output**: Actual output matches expected JSON
8. **Rendering Quality** (CRITICAL - added to prevent visual confusion):
   - Resources appear exactly once at correct hierarchy level (e.g., Lambda at VPC, not duplicated in subnets)
   - Numbered instances (~1, ~2, ~3) distributed 1:1 with parent resources (subnet_a → ~1, subnet_b → ~2)
   - No cross-subnet connection clutter (numbered resources only connect to unnumbered resources in same subnet)
   - Clean visual layout with no unnecessary crossing lines
   - Test output matches expected JSON exactly
9. **Integration Test Coverage**: Test fixtures exist and exercise handlers
10. **Documentation**: Docs updated with implementation changes

**POST_IMPLEMENTATION_VALIDATION.md is the authoritative source for post-implementation validation.** Use it before declaring any handler complete.
