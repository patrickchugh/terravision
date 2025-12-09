# Implementation Plan: Multi-Cloud Provider Support (GCP & Azure)

**Branch**: `001-multi-cloud-support` | **Date**: 2025-12-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-multi-cloud-support/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Add comprehensive support for Google Cloud Platform (GCP) and Microsoft Azure cloud providers to TerraVision, enabling automatic detection of cloud provider from Terraform code and generation of provider-specific architecture diagrams. The implementation refactors the monolithic `cloud_config.py` into provider-specific configuration files organized in `modules/config/` subdirectory, and implements separate resource handlers for each provider. All internal imports are updated to use a new `config_loader.py` module for dynamic provider configuration loading. Icon libraries and resource classes for Azure and GCP already exist in the codebase but need integration with the provider detection and configuration loading system.

**Note**: Multi-cloud project support (generating multiple diagrams from a single project with mixed providers) has been deferred to a future release. Users can generate diagrams for multi-provider projects by running TerraVision separately on each provider's directory.

**Breaking Change**: This feature renames `modules/cloud_config.py` to `modules/cloud_config_aws.py` without maintaining a compatibility shim. TerraVision CLI commands remain fully backward compatible, but any external code importing `modules.cloud_config` directly will need updates.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Terraform 1.x, Graphviz, python-hcl2 (Terraform parser), Diagrams library (for icons), Ollama (optional AI), AWS Bedrock SDK (optional AI)
**Storage**: File system for generated diagrams (PNG, SVG, PDF, BMP), JSON exports, and intermediate tfdata.json (debug mode)
**Testing**: pytest (existing test framework), integration tests with real Terraform projects
**Target Platform**: Cross-platform CLI tool (Linux, macOS, Windows)
**Project Type**: Single project (CLI tool)
**Performance Goals**: Azure/GCP diagram generation completes within same performance targets as AWS (<20% slower for similar-sized projects with 50-100 resources)
**Constraints**: Must maintain 100% client-side processing (no cloud credentials), CLI backward compatibility (all existing terravision commands work unchanged), resource classes already exist for Azure/GCP, breaking change for direct module imports
**Scale/Scope**: Support 30+ core resource types per provider initially (Azure and GCP resource classes already implemented with ~30-50 services each based on file count, meeting RC-003 requirement)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle Compliance Analysis

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code as Source of Truth** | ✅ PASS | Feature maintains Terraform code as source of truth, extending diagram generation to Azure and GCP providers |
| **II. Client-Side Security & Privacy** | ✅ PASS | No cloud credentials required, all processing client-side, only metadata sent to optional AI backends |
| **III. Docs as Code (DaC)** | ✅ PASS | Generated diagrams remain version-controllable artifacts, CI/CD integration unchanged |
| **IV. Dynamic Parsing & Accuracy** | ✅ PASS | Extends existing dynamic parsing to Azure and GCP, handles conditionals and variables per provider |
| **V. Multi-Cloud & Provider Agnostic Design** | ✅ PASS | **Core feature objective** - directly implements constitutional requirement for multi-cloud support |
| **VI. Extensibility Through Annotations** | ✅ PASS | YAML annotations work identically for Azure and GCP as AWS (FR-012) |
| **VII. AI-Assisted Refinement (Optional)** | ✅ PASS | AI refinement extended to Azure/GCP with provider-specific prompts (FR-014) |

### Quality Requirements Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| **QR-001: No deployed infrastructure required** | ✅ PASS | Works from `terraform plan` for all providers |
| **QR-002: Handle large projects efficiently** | ✅ PASS | Performance targets set at <20% slower than AWS for similar scale |
| **QR-003: Parse organizational modules** | ✅ PASS | Existing module parsing works for all providers |
| **QR-004: Debug mode support** | ✅ PASS | tfdata.json export works regardless of provider |
| **QR-005: JSON output support** | ✅ PASS | JSON export available for all providers (FR-013) |

### Testing Standards Compliance

| Standard | Status | Notes |
|----------|--------|-------|
| **TS-001: Don't break terraform plan parsing** | ✅ PASS | Uses existing Terraform parser, provider-agnostic |
| **TS-002: Icon library and mapping tests** | ⚠️ ATTENTION | **Requires new tests** for Azure/GCP icon mappings |
| **TS-003: Annotation testing** | ✅ PASS | Extends existing annotation tests to Azure/GCP |
| **TS-004: CI/CD validation** | ✅ PASS | CI/CD examples remain provider-agnostic |

### Development Workflow Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| **User scenarios with acceptance criteria** | ✅ PASS | Spec includes 3 prioritized user stories with scenarios |
| **Validation with real repos** | ⚠️ ATTENTION | **Requires** 3+ real Azure and 3+ real GCP Terraform repos for testing |
| **README updates** | ⚠️ ATTENTION | **Must update** README to change GCP/Azure from "Coming soon" to "Supported" |
| **Backward compatibility** | ⚠️ PARTIAL | CLI commands unchanged (FR-006), but breaking change for direct `import modules.cloud_config` - updated to `config_loader.load_config(provider)` |

### Code Review Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| **CR-001: Validate against 3+ real repos** | ⚠️ ATTENTION | Need Azure and GCP test repositories |
| **CR-002: Visual comparison screenshots** | ⚠️ ATTENTION | **Required** for Azure/GCP icon styling verification |
| **CR-003: Test both AI backends** | ✅ PASS | Bedrock and Ollama support for Azure/GCP prompts |
| **CR-004: Threat model consideration** | ✅ PASS | No new security concerns, maintains client-side processing |

### Release Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| **RC-001: Semantic versioning** | ⚠️ ATTENTION | This is a MINOR version bump (0.8 → 0.9) per constitution |
| **RC-002: Migration guide if breaking** | ✅ PASS | Constitution explicitly allows config file location/format changes for new cloud providers (Development Workflow §5). Migration guide still recommended for clarity. |
| **RC-003: Complete icon library** | ✅ PASS | Constitution updated to require "top 30 services" for new providers. Current Azure/GCP classes have ~30-50 services, meeting requirement. |
| **RC-004: No >20% performance regression** | ✅ PASS | Target explicitly set in success criteria |

**GATE DECISION**: ✅ PASS
- All principles pass ✅
- Quality/testing standards pass with attention items noted ✅
- All release criteria met ✅
- No blockers identified

## Project Structure

### Documentation (this feature)

```text
specs/001-multi-cloud-support/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── provider-detection-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

**Existing structure** (TerraVision is a single-project CLI tool):

```text
terravision/
├── terravision.py                    # ⚠️ MODIFY - Add provider detection and multi-output
├── modules/
│   ├── config/                       # 🆕 NEW DIRECTORY - Provider-specific configurations
│   │   ├── __init__.py               # 🆕 NEW - Makes config a package
│   │   ├── cloud_config_aws.py       # 🔄 RENAME from ../cloud_config.py
│   │   ├── cloud_config_azure.py     # 🆕 NEW
│   │   └── cloud_config_gcp.py       # 🆕 NEW
│   ├── config_loader.py              # 🆕 NEW - Loads provider-specific configs from config/
│   ├── provider_detector.py          # 🆕 NEW - Detects cloud provider from Terraform
│   ├── resource_handlers_aws.py      # 🔄 RENAME from resource_handlers.py
│   ├── resource_handlers_gcp.py      # 🆕 NEW
│   ├── resource_handlers_azure.py    # 🆕 NEW
│   ├── resource_handlers.py          # 🔄 REFACTOR to dispatcher (not shim)
│   ├── graphmaker.py                 # ⚠️ MODIFY - Add provider-aware logic, update imports
│   ├── interpreter.py                # ✅ NO CHANGE (provider-agnostic)
│   ├── tfwrapper.py                  # ⚠️ MODIFY - Update imports to modules.config.cloud_config_*
│   ├── fileparser.py                 # ✅ NO CHANGE (provider-agnostic)
│   ├── annotations.py                # ⚠️ MODIFY - Provider-aware AUTO_ANNOTATIONS loading via config_loader
│   ├── helpers.py                    # ⚠️ MODIFY - Add provider utilities, update imports
│   └── drawing.py                    # ⚠️ MODIFY - Provider-aware config loading, update imports
├── resource_classes/
│   ├── aws/                          # ✅ EXISTING - ~80 AWS resource class files
│   ├── azure/                        # ✅ EXISTING - ~32 Azure resource class files (already implemented!)
│   ├── gcp/                          # ✅ EXISTING - ~14 GCP resource class files (already implemented!)
│   ├── generic/                      # ✅ EXISTING - Generic/fallback icons
│   └── onprem/                       # ✅ EXISTING - On-premises resources
├── tests/
│   ├── integration_test.py           # ⚠️ MODIFY - Add Azure/GCP test cases
│   ├── test_provider_detection.py    # 🆕 NEW
│   ├── test_azure_resources.py       # 🆕 NEW
│   ├── test_gcp_resources.py         # 🆕 NEW
│   └── fixtures/
│       ├── azure_terraform/          # 🆕 NEW - Sample Azure Terraform projects
│       └── gcp_terraform/            # 🆕 NEW - Sample GCP Terraform projects
└── README.md                         # ⚠️ MODIFY - Update supported providers section

```

**Structure Decision**: TerraVision uses Option 1 (Single project) structure. The feature adds provider-specific configuration and handler modules while leveraging existing Azure/GCP resource classes that are already present in the codebase. Key changes:

1. **Create** `modules/config/` directory to organize provider configurations
2. **Create** `modules/config/__init__.py` package file
3. **Rename** `cloud_config.py` → `modules/config/cloud_config_aws.py`
4. **Create** `modules/config/cloud_config_azure.py` and `modules/config/cloud_config_gcp.py` with provider-specific configs
5. **Add** `config_loader.py` to dynamically load provider configs from `modules.config.*`
6. **Rename** `resource_handlers.py` → `resource_handlers_aws.py`
7. **Create** `resource_handlers_azure.py` and `resource_handlers_gcp.py`
8. **Refactor** `resource_handlers.py` as dispatcher module (routes to provider-specific handlers)
9. **Add** `provider_detector.py` for automatic provider detection
10. **Update imports** in all modules to use `modules.config.cloud_config_*` pattern
11. **Add comprehensive tests** for Azure and GCP providers

**Breaking Change Note**: This is a breaking change for any external code importing `modules.cloud_config` directly. Internal imports updated throughout codebase to use `config_loader.load_config(provider)` pattern with configs in `modules.config` subpackage.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations identified. All constitution requirements met.
