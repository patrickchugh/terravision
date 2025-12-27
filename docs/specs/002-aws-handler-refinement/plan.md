# Implementation Plan: AWS Handler Refinement

**Branch**: `002-aws-handler-refinement` | **Date**: 2025-12-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/docs/specs/002-aws-handler-refinement/spec.md`

## Summary

Enhance TerraVision's AWS resource handlers to produce professional architecture diagrams for the top 80% of common AWS patterns. This includes adding/refining handlers for API Gateway, Event-Driven architectures (EventBridge, SNS, SQS, Lambda ESM), ElastiCache, Cognito, WAF, SageMaker, Step Functions, S3 notifications, Secrets Manager, Glue/Athena, and AppSync. The implementation is additive to existing handlers and must maintain backward compatibility with all existing tests.

## Technical Context

**Language/Version**: Python 3.11 (per pyproject.toml)
**Primary Dependencies**: python-hcl2, graphviz, click, pyyaml (existing)
**Storage**: N/A (file-based Terraform parsing, no database)
**Testing**: pytest with fixtures in tests/json/
**Target Platform**: CLI tool (macOS, Linux, Windows via Poetry)
**Project Type**: Single CLI application (enhancement to existing codebase)
**Performance Goals**: N/A (batch diagram generation, not latency-sensitive)
**Constraints**: Must pass all existing tests; changes must be additive where possible
**Scale/Scope**: 11 user stories, 28 functional requirements, ~40 new/modified handler functions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution Reference**: [docs/constitution.md](../../constitution.md) (v1.2.0)

### Core Principles Compliance

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code as Source of Truth | ✅ PASS | Diagrams generated from Terraform code |
| II. Client-Side Security | ✅ PASS | No cloud credentials required |
| III. Docs as Code (DaC) | ✅ PASS | Diagrams version-controllable |
| IV. Dynamic Parsing | ✅ PASS | Handlers parse Terraform dynamically |
| V. Multi-Cloud Design | ✅ PASS | Changes isolated to AWS handler files |
| VI. Extensibility | ✅ PASS | YAML annotations still supported |
| VII. AI-Assisted Refinement | ✅ PASS | Optional AI remains unchanged |

### Code Organization Compliance

| Rule | Status | Notes |
|------|--------|-------|
| CO-001: Provider config in `cloud_config_<provider>.py` | ✅ PASS | All config changes in `cloud_config_aws.py` |
| CO-002: Provider handlers in `resource_handlers_<provider>.py` | ✅ PASS | All handlers in `resource_handlers_aws.py` |
| CO-003: Common modules provider-agnostic | ✅ PASS | No changes to `graphmaker.py`, `drawing.py`, etc. |
| CO-004: Dynamic dispatch for providers | ✅ PASS | Using existing dispatch pattern |
| CO-005: New providers follow pattern | N/A | AWS only, pattern already exists |

### Quality Requirements Compliance

| Rule | Status | Notes |
|------|--------|-------|
| QR-001: No deployed infrastructure required | ✅ PASS | Works from `terraform plan` |
| QR-002: Handle 200+ resources | ✅ PASS | No performance degradation expected |
| QR-003: Parse external modules | ✅ PASS | Existing module handling unchanged |
| QR-004: Debug mode exports | ✅ PASS | Existing debug mode unchanged |
| QR-005: JSON + human-readable output | ✅ PASS | Existing output formats unchanged |

### Testing Standards Compliance

| Rule | Status | Notes |
|------|--------|-------|
| TS-001: No terraform parsing breakage | ✅ PASS | Additive changes only |
| TS-002: Provider icon tests | ✅ PASS | Will add icon tests for new resources |
| TS-005: Poetry for dependencies | ✅ PASS | Using `poetry run` prefix |
| TS-006: Black formatting | ✅ PASS | Will format with Black (88 chars) |
| TS-007: Pre-commit hooks | ✅ PASS | Non-slow tests in pre-commit |

### Feature-Specific Constraints (from Spec)

- [x] All existing tests under `tests/` MUST continue to pass
- [x] Changes to `resource_handlers_aws.py` and `cloud_config_aws.py` must be additive where possible
- [x] If test failures are due to bugs in expected results, report to user before modifying
- [x] Prioritization: P1 patterns first, then P2, then P3

**Gate Status**: ✅ PASS - All constitution principles satisfied. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
docs/specs/002-aws-handler-refinement/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A for this feature - no API contracts)
├── checklists/          # Quality checklists
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Existing TerraVision structure (enhancement target)
modules/
├── resource_handlers_aws.py    # PRIMARY: Add new handler functions here
├── resource_handlers_gcp.py    # Not modified
├── resource_handlers_azure.py  # Not modified
├── config/
│   └── cloud_config_aws.py     # SECONDARY: Add resource configs here
├── graphmaker.py               # May need minor updates for new patterns
├── drawing.py                  # May need updates for new node types
└── helpers.py                  # Utility functions

resource_classes/
└── aws/                        # Icons for AWS resources (may need new icons if you cannot find a suitable existing one under all subfolders)

tests/
├── json/                       # Test fixtures (add new pattern tests)
│   ├── expected-*.json         # Expected outputs (DO NOT MODIFY existing)
│   └── *-tfdata.json          # Input fixtures
├── integration_test.py         # Integration tests
├── graphmaker_unit_test.py     # Unit tests
└── fixtures/                   # Terraform fixtures for testing
    └── aws_terraform/          # AWS-specific test Terraform
```

**Structure Decision**: Enhancement to existing single-project CLI structure. No new top-level directories needed. All changes are within `modules/` and `tests/`.

## Complexity Tracking

> No violations to justify. All changes are additive to existing patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
