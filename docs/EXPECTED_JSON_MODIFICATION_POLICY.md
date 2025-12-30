# Expected JSON Modification Policy

## Critical Rule

**Expected test outputs (tests/json/expected-*.json) should RARELY be modified. When tests fail, the default assumption is that the code has a bug, NOT that the expected output is wrong.**

## When Expected JSON Can Be Modified

Expected JSON files may ONLY be modified in these scenarios:

### ✅ APPROVED Scenarios

1. **New Feature Implementation**
   - Adding a new test case for a new feature
   - Example: Adding `expected-waf-alb.json` for Phase 7 WAF implementation
   - Requires: User story/task reference

2. **Intentional Behavior Change**
   - Explicit user request to change how a pattern is rendered
   - Example: "Make API Gateway show integrations instead of methods"
   - Requires: User confirmation + justification in commit message

3. **Bug Fix That Improves Accuracy**
   - Current expected output is demonstrably wrong/misleading
   - New output is objectively more accurate
   - Example: Fixing ElastiCache replication group consolidation
   - Requires:
     - Clear explanation of what was wrong
     - Evidence that new output is more accurate
     - User approval BEFORE modification

4. **Validation Failure with Approved Fix**
   - Validation tests (test_validation.py) fail on expected output
   - Root cause identified and fixed in handlers
   - Expected output updated to reflect the fix
   - Requires: Validation test must pass after update

### ❌ NEVER ALLOWED Scenarios

1. **Test Failed, Regenerate to Pass**
   - ❌ BAD: "4 tests failed, let me regenerate expected outputs"
   - ✅ GOOD: "4 tests failed, let me investigate WHY they failed"

2. **Side Effect from Other Changes**
   - ❌ BAD: "I changed the LB handler, wordpress test failed, regenerate expected"
   - ✅ GOOD: "I changed the LB handler, wordpress test failed, investigate and fix the handler"

3. **Making Tests Pass Without Investigation**
   - ❌ BAD: Regenerate → Test passes → Mark task complete
   - ✅ GOOD: Investigate → Fix root cause → Test passes → Validate no regressions

4. **"Looks better" Without User Approval**
   - ❌ BAD: "I think this grouping looks cleaner, regenerating expected"
   - ✅ GOOD: "Current grouping seems suboptimal, confirming with user before changes"

## Required Process for Modification

When you believe expected JSON should be modified:

### Step 1: Justify
Write down:
- Which expected file needs modification
- What specific changes would be made
- WHY the current expected output is wrong
- Evidence that new output is more accurate

### Step 2: Get Approval
- **DO NOT MODIFY** expected JSON yet
- Present justification to user
- Wait for explicit approval
- Only proceed if user confirms

### Step 3: Document
After approval, commit with detailed message:
```
Update expected-X.json: Fix Y rendering issue

- Previous output: [description]
- Issue: [what was wrong]
- New output: [description]
- Why it's better: [justification]
- Approved by: [user confirmation reference]
```

### Step 4: Validate
After modification:
- Run full test suite
- Run validation tests
- Check for unintended side effects
- Verify no other expected files affected

## Red Flags

These patterns indicate WRONG approach:

🚩 **Batch Regeneration**
```bash
# ❌ WRONG
for test in wordpress eks elasticache; do
    cp /tmp/${test}-actual.json tests/json/expected-${test}.json
done
```

🚩 **"Just Making Tests Pass"**
```
4 tests failed → Regenerate 4 expected outputs → Tests pass ✓
```
This is circular logic - you made tests pass by changing what they expect!

🚩 **No Investigation**
```
Test failed → Look at diff → Regenerate expected → Done
```
Missing: WHY did it fail? Is the new output correct? Did I introduce a bug?

🚩 **"Looks Fine to Me"**
```
Actual output looks reasonable → Update expected → Test passes
```
Missing: User approval, justification, comparison with original

## Correct Workflow When Tests Fail

1. **Investigate Root Cause**
   - Read the diff carefully
   - Understand what changed and why
   - Trace through the code to find the cause

2. **Determine If It's a Bug**
   - Is the actual output wrong? → Fix the handler
   - Is the expected output wrong? → Proceed to approval
   - Is it a side effect? → Fix the handler to avoid side effects

3. **Fix the Code**
   - Modify handlers to produce correct output
   - Add validation checks if needed
   - Test the fix thoroughly

4. **Only Then Consider Expected Changes**
   - If the fix genuinely improves output accuracy
   - Get user approval first
   - Document thoroughly

## Validation Tests as Guardrails

The `test_validation.py` file contains tests that check output quality:

- `test_no_shared_connections_in_expected_outputs`: Ensures no rendering issues
- Future: More quality checks

**CRITICAL**: These validation tests should NEVER be modified to pass failing expected outputs. If validation fails:

1. The expected output has a quality issue
2. Fix the handler to produce better output
3. Then update expected (with approval)

## Questions to Ask Yourself

Before modifying expected JSON, ask:

1. ❓ Have I investigated WHY the test failed?
2. ❓ Is this a bug in my code or a genuine improvement?
3. ❓ Have I gotten user approval?
4. ❓ Can I clearly justify this change?
5. ❓ Will this improve diagram accuracy for users?
6. ❓ Have I documented the change thoroughly?

If you can't answer YES to all these, **DO NOT** modify expected JSON.

## Summary

- Expected JSON = source of truth for correct behavior
- Modify RARELY, with approval, with justification
- When tests fail, fix the code first
- Validation tests catch quality issues
- Document all modifications thoroughly

**Default assumption: Test failed = Code has a bug**
