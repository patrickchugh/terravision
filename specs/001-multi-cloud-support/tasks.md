# Implementation Tasks: Multi-Cloud Provider Support (GCP & Azure)

**Feature**: Multi-Cloud Provider Support
**Branch**: `001-multi-cloud-support`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Status**: Ready for Implementation

## Overview

This document provides an actionable task list for implementing multi-cloud provider support (Azure and GCP) in TerraVision. Tasks are organized by user story to enable independent implementation and parallel execution.

**Total Tasks**: 52
**MVP Scope**: User Story 1 (Azure Support) - 22 tasks
**Estimated Completion**: Incremental delivery per user story

---

## Implementation Strategy

### Delivery Phases

1. **Phase 1 (Setup)**: Project structure and foundational infrastructure - *Prerequisite for all stories*
2. **Phase 2 (Foundational)**: Provider detection and configuration loading - *Blocking for all stories*
3. **Phase 3 (US1 - P1)**: Azure diagram generation - *MVP deliverable, independently testable*
4. **Phase 4 (US2 - P2)**: GCP diagram generation - *Independent of US1, can be parallel*
5. **Phase 5 (US3 - P3)**: Multi-cloud project support - *Depends on US1 + US2*
6. **Phase 6 (Polish)**: Documentation, testing, and release preparation

### Parallelization Opportunities

- **After Foundational Phase**: US1 (Azure) and US2 (GCP) can be implemented in parallel by different developers
- **Within Each Story**: Tasks marked [P] can be executed in parallel (different files, no dependencies)
- **Testing**: Test fixture creation can happen in parallel with implementation

---

## Phase 1: Setup & Project Structure

**Goal**: Prepare codebase for refactoring and establish multi-cloud foundation

**Duration**: ~2 hours
**Blocking**: All subsequent phases

### Tasks

- [ ] T001 Create git branch `001-multi-cloud-support` from main
- [ ] T002 Backup existing `modules/cloud_config.py` for reference during refactoring
- [ ] T003 Backup existing `modules/resource_handlers.py` for reference during refactoring
- [ ] T004 Create test fixtures directory structure: `tests/fixtures/azure_terraform/` and `tests/fixtures/gcp_terraform/`
- [ ] T005 [P] Create sample Azure Terraform fixture in `tests/fixtures/azure_terraform/main.tf` (VM + VNet + Storage Account)
- [ ] T006 [P] Create sample GCP Terraform fixture in `tests/fixtures/gcp_terraform/main.tf` (Compute Instance + VPC + Cloud Storage)
- [ ] T007 [P] Create sample multi-cloud Terraform fixture in `tests/fixtures/multi_cloud/main.tf` (AWS + Azure resources)

**Completion Criteria**:
- Branch created and checked out
- Test fixture directories exist with sample Terraform code
- Original files backed up for reference

---

## Phase 2: Foundational Infrastructure (Blocking)

**Goal**: Implement core provider detection and configuration loading system

**Duration**: ~6 hours
**Blocking**: All user stories depend on this phase

### Tasks

- [ ] T008 Create `modules/provider_detector.py` with PROVIDER_PREFIXES constant mapping (aws_, azurerm_, google_ → provider names)
- [ ] T009 Implement `detect_providers(tfdata)` function in `modules/provider_detector.py` per contract spec (scan all_resource, count by prefix, determine primary)
- [ ] T010 Implement `get_provider_for_resource(resource_name)` function in `modules/provider_detector.py` (extract resource type, match prefix)
- [ ] T011 Implement `filter_resources_by_provider(tfdata, provider)` function in `modules/provider_detector.py` (filter graphdict and metadata)
- [ ] T012 Implement `validate_provider_detection(result, tfdata)` function in `modules/provider_detector.py` (validation checks from contract)
- [ ] T013 Create `modules/config_loader.py` with `load_config(provider)` function (dynamic import based on provider name)
- [ ] T014 Add `ProviderDetectionError` exception class to `modules/provider_detector.py`
- [ ] T015 Rename `modules/cloud_config.py` to `modules/cloud_config_aws.py` (git mv to preserve history)
- [ ] T016 Update all AWS config variable names in `modules/cloud_config_aws.py` (verify AWS_ prefix on all variables)
- [ ] T017 Update import statement in `terravision.py` from `import modules.cloud_config` to use `config_loader.load_config('aws')` pattern
- [ ] T018 Update import statement in `modules/graphmaker.py` to use `config_loader.load_config(provider)` pattern
- [ ] T019 Update import statement in `modules/tfwrapper.py` to use `config_loader.load_config(provider)` pattern
- [ ] T020 Update import statement in `modules/helpers.py` to use `config_loader.load_config(provider)` pattern
- [ ] T021 Update import statement in `modules/drawing.py` to use `config_loader.load_config(provider)` pattern
- [ ] T022 Rename `modules/resource_handlers.py` to `modules/resource_handlers_aws.py` (git mv to preserve history)
- [ ] T023 Create new `modules/resource_handlers.py` as dispatcher module with provider-aware routing functions
- [ ] T024 Implement `handle_special_cases(tfdata, provider)` dispatcher in `modules/resource_handlers.py` (routes to provider-specific handler)
- [ ] T025 Implement `match_resources(tfdata, provider)` dispatcher in `modules/resource_handlers.py`
- [ ] T026 Update `modules/graphmaker.py` to call resource handler dispatchers with provider parameter
- [ ] T027 Add provider detection call to `terravision.py` main flow after tfwrapper.tf_initplan() - store result in tfdata["provider_detection"]

**Completion Criteria**:
- Provider detection module complete with all 4 API functions
- Configuration loader dynamically loads provider configs
- All internal imports updated to use config_loader
- Resource handler dispatcher routes to provider-specific handlers
- Provider detection integrated into main CLI flow

**Independent Test**:
```bash
# Test provider detection with AWS project
terravision draw --source tests/fixtures/aws_example --debug
# Should detect provider: aws

# Verify no regressions
pytest tests/integration_test.py -k aws
```

---

## Phase 3: User Story 1 - Azure Diagram Generation (P1)

**Goal**: Enable Azure Terraform project diagram generation with Azure-specific icons and styling

**Priority**: P1 (MVP)
**Duration**: ~8 hours
**Dependencies**: Phase 2 (Foundational)
**Independent**: Can be developed in parallel with US2 (GCP)

### User Story

A cloud architect working with Microsoft Azure infrastructure needs to generate architecture diagrams from their Terraform code. They run TerraVision on their Azure Terraform project, and the tool automatically detects Azure resources, uses appropriate Azure icons and styling, and generates a diagram following Azure architectural best practices.

### Independent Test Criteria

```bash
# Test Azure diagram generation
terravision draw --source tests/fixtures/azure_terraform --outfile azure-test

# Verify:
# 1. Output file azure-test.png exists
# 2. Provider detected as "azure"
# 3. Diagram uses Azure resource icons (check visually)
# 4. Resources grouped by Resource Group (Azure convention)
# 5. No errors or warnings about missing handlers
```

### Tasks

#### Configuration

- [ ] T028 [P] [US1] Create `modules/cloud_config_azure.py` based on AWS config structure
- [ ] T029 [US1] Define AZURE_CONSOLIDATED_NODES in `modules/cloud_config_azure.py` (NSG, Application Gateway grouping rules)
- [ ] T030 [US1] Define AZURE_GROUP_NODES in `modules/cloud_config_azure.py` (azurerm_resource_group → azurerm_virtual_network → azurerm_subnet hierarchy)
- [ ] T031 [US1] Define AZURE_EDGE_NODES, AZURE_OUTER_NODES in `modules/cloud_config_azure.py`
- [ ] T032 [US1] Define AZURE_DRAW_ORDER in `modules/cloud_config_azure.py` (rendering sequence for Azure resources)
- [ ] T033 [US1] Define AZURE_NODE_VARIANTS in `modules/cloud_config_azure.py` (VM types, LB types)
- [ ] T034 [US1] Define AZURE_SPECIAL_RESOURCES in `modules/cloud_config_azure.py` (handler function mapping for Resource Groups, NSGs, VNets)
- [ ] T035 [US1] Define AZURE_REFINEMENT_PROMPT in `modules/cloud_config_azure.py` per research.md prompt template (Resource Group hierarchy, VNet conventions)
- [ ] T036 [US1] Define AZURE_DOCUMENTATION_PROMPT in `modules/cloud_config_azure.py`

#### Resource Handlers

- [ ] T037 [P] [US1] Create `modules/resource_handlers_azure.py` skeleton with imports
- [ ] T038 [US1] Implement `handle_special_cases(tfdata)` in `modules/resource_handlers_azure.py` (Azure-specific disconnect logic)
- [ ] T039 [US1] Implement `azure_handle_resource_groups(tfdata)` in `modules/resource_handlers_azure.py` (group resources by azurerm_resource_group)
- [ ] T040 [US1] Implement `azure_handle_nsg(tfdata)` in `modules/resource_handlers_azure.py` (Network Security Group relationships)
- [ ] T041 [US1] Implement `azure_handle_app_gateway(tfdata)` in `modules/resource_handlers_azure.py` (Application Gateway backend pool connections)
- [ ] T042 [US1] Implement `azure_match_resources(tfdata)` in `modules/resource_handlers_azure.py` (post-processing for Azure resources)
- [ ] T043 [US1] Register Azure handlers in `modules/resource_handlers.py` dispatcher

#### Drawing & Output

- [ ] T044 [US1] Update `modules/drawing.py` to import Azure resource classes from `resource_classes.azure.*` when provider is 'azure'
- [ ] T045 [US1] Update `modules/drawing.py` to use Azure cloud group class when provider is 'azure'
- [ ] T046 [US1] Update `terravision.py` to load Azure configuration when Azure provider detected
- [ ] T047 [US1] Update `terravision.py` to generate output filename with "-azure" suffix if multi-provider project

#### Testing

- [ ] T048 [P] [US1] Create `tests/test_azure_resources.py` with test_detect_azure_provider() test
- [ ] T049 [P] [US1] Add test_azure_resource_grouping() to `tests/test_azure_resources.py` (verify Resource Group hierarchy)

**Completion Criteria**:
- Azure config file complete with all required variables
- Azure resource handlers implement core functionality (Resource Groups, NSGs, App Gateway)
- Drawing module imports and uses Azure resource classes
- Independent test passes (Azure diagram generated successfully)
- No regression in AWS diagram generation

---

## Phase 4: User Story 2 - GCP Diagram Generation (P2)

**Goal**: Enable GCP Terraform project diagram generation with GCP-specific icons and styling

**Priority**: P2
**Duration**: ~8 hours
**Dependencies**: Phase 2 (Foundational)
**Independent**: Can be developed in parallel with US1 (Azure)

### User Story

A DevOps engineer working with Google Cloud Platform infrastructure needs to generate architecture diagrams from their Terraform code. They run TerraVision on their GCP Terraform project, and the tool automatically detects GCP resources, uses appropriate GCP icons and styling, and generates a diagram following GCP architectural best practices.

### Independent Test Criteria

```bash
# Test GCP diagram generation
terravision draw --source tests/fixtures/gcp_terraform --outfile gcp-test

# Verify:
# 1. Output file gcp-test.png exists
# 2. Provider detected as "gcp"
# 3. Diagram uses GCP resource icons (check visually)
# 4. Resources grouped by Project (GCP convention)
# 5. No errors or warnings about missing handlers
```

### Tasks

#### Configuration

- [ ] T050 [P] [US2] Create `modules/cloud_config_gcp.py` based on AWS config structure
- [ ] T051 [US2] Define GCP_CONSOLIDATED_NODES in `modules/cloud_config_gcp.py` (Firewall, Load Balancer grouping rules)
- [ ] T052 [US2] Define GCP_GROUP_NODES in `modules/cloud_config_gcp.py` (google_project → google_compute_network → google_compute_subnetwork hierarchy)
- [ ] T053 [US2] Define GCP_EDGE_NODES, GCP_OUTER_NODES in `modules/cloud_config_gcp.py`
- [ ] T054 [US2] Define GCP_DRAW_ORDER in `modules/cloud_config_gcp.py` (rendering sequence for GCP resources)
- [ ] T055 [US2] Define GCP_NODE_VARIANTS in `modules/cloud_config_gcp.py` (Instance types, LB types)
- [ ] T056 [US2] Define GCP_SPECIAL_RESOURCES in `modules/cloud_config_gcp.py` (handler function mapping for Projects, VPCs, Firewall Rules)
- [ ] T057 [US2] Define GCP_REFINEMENT_PROMPT in `modules/cloud_config_gcp.py` per research.md prompt template (Project hierarchy, global VPC, regional subnets)
- [ ] T058 [US2] Define GCP_DOCUMENTATION_PROMPT in `modules/cloud_config_gcp.py`

#### Resource Handlers

- [ ] T059 [P] [US2] Create `modules/resource_handlers_gcp.py` skeleton with imports
- [ ] T060 [US2] Implement `handle_special_cases(tfdata)` in `modules/resource_handlers_gcp.py` (GCP-specific disconnect logic)
- [ ] T061 [US2] Implement `gcp_handle_projects(tfdata)` in `modules/resource_handlers_gcp.py` (group resources by google_project)
- [ ] T062 [US2] Implement `gcp_handle_firewall(tfdata)` in `modules/resource_handlers_gcp.py` (Firewall rule VPC-level placement)
- [ ] T063 [US2] Implement `gcp_handle_gke(tfdata)` in `modules/resource_handlers_gcp.py` (GKE cluster node pool relationships)
- [ ] T064 [US2] Implement `gcp_match_resources(tfdata)` in `modules/resource_handlers_gcp.py` (post-processing for GCP resources)
- [ ] T065 [US2] Register GCP handlers in `modules/resource_handlers.py` dispatcher

#### Drawing & Output

- [ ] T066 [US2] Update `modules/drawing.py` to import GCP resource classes from `resource_classes.gcp.*` when provider is 'gcp'
- [ ] T067 [US2] Update `modules/drawing.py` to use GCP cloud group class when provider is 'gcp'
- [ ] T068 [US2] Update `terravision.py` to load GCP configuration when GCP provider detected
- [ ] T069 [US2] Update `terravision.py` to generate output filename with "-gcp" suffix if multi-provider project

#### Testing

- [ ] T070 [P] [US2] Create `tests/test_gcp_resources.py` with test_detect_gcp_provider() test
- [ ] T071 [P] [US2] Add test_gcp_resource_grouping() to `tests/test_gcp_resources.py` (verify Project hierarchy)

**Completion Criteria**:
- GCP config file complete with all required variables
- GCP resource handlers implement core functionality (Projects, VPCs, Firewall, GKE)
- Drawing module imports and uses GCP resource classes
- Independent test passes (GCP diagram generated successfully)
- No regression in AWS or Azure diagram generation

---

## Phase 5: User Story 3 - Multi-Cloud Project Support (P3)

**Goal**: Handle Terraform projects with multiple cloud providers by generating separate diagrams per provider

**Priority**: P3
**Duration**: ~4 hours
**Dependencies**: Phase 3 (US1) AND Phase 4 (US2) - requires both Azure and GCP support complete

### User Story

A solutions architect working on a multi-cloud deployment has Terraform code that provisions resources across AWS, GCP, and Azure. They need to visualize their entire infrastructure. When they run TerraVision, the tool detects all cloud providers used and generates separate diagrams per provider.

### Independent Test Criteria

```bash
# Test multi-cloud diagram generation
terravision draw --source tests/fixtures/multi_cloud --outfile architecture

# Verify:
# 1. Multiple output files created: architecture-aws.png, architecture-azure.png
# 2. Each diagram contains only resources from that provider
# 3. Console output shows "Detected 2 providers: aws, azure"
# 4. Console output shows separate "Generating AWS diagram..." and "Generating Azure diagram..." messages
```

### Tasks

- [ ] T072 [US3] Update `terravision.py` to detect if multiple providers exist in tfdata["provider_detection"]["providers"]
- [ ] T073 [US3] Implement `generate_output_filename(base_filename, provider, providers_list)` helper function in `terravision.py` (adds provider suffix if multi-provider)
- [ ] T074 [US3] Implement main loop in `terravision.py` to iterate over detected providers and generate separate diagrams
- [ ] T075 [US3] Update console output messaging in `terravision.py` to show "Detected N providers: aws, azure, gcp" when multiple detected
- [ ] T076 [US3] Update console output to show "Generating [Provider] diagram..." for each provider in multi-cloud projects
- [ ] T077 [US3] Add logic to filter tfdata by provider before passing to drawing module in multi-cloud scenario using `filter_resources_by_provider()`
- [ ] T078 [P] [US3] Update multi-cloud test fixture to include all three providers (AWS + Azure + GCP)
- [ ] T079 [P] [US3] Add test_multi_cloud_detection() to `tests/test_provider_detection.py` (verify detects all 3 providers)
- [ ] T080 [US3] Add integration test to `tests/integration_test.py` for multi-cloud project (verify separate outputs generated)

**Completion Criteria**:
- Multi-provider projects detected correctly
- Separate output files generated per provider with appropriate naming
- Each diagram contains only resources from its respective provider
- Console messaging clearly indicates multi-cloud detection and progress
- Independent test passes

---

## Phase 6: Testing & Polish

**Goal**: Comprehensive testing, documentation updates, and release preparation

**Duration**: ~6 hours
**Dependencies**: All user stories complete

### Tasks

#### Provider Detection Tests

- [ ] T081 [P] Create `tests/test_provider_detection.py` with test_detect_aws_only() test
- [ ] T082 [P] Add test_detect_azure_only() to `tests/test_provider_detection.py`
- [ ] T083 [P] Add test_detect_gcp_only() to `tests/test_provider_detection.py`
- [ ] T084 [P] Add test_get_provider_for_aws_resource() to `tests/test_provider_detection.py`
- [ ] T085 [P] Add test_get_provider_for_azure_resource() to `tests/test_provider_detection.py`
- [ ] T086 [P] Add test_get_provider_for_gcp_resource() to `tests/test_provider_detection.py`
- [ ] T087 [P] Add test_get_provider_for_unknown_resource() to `tests/test_provider_detection.py`
- [ ] T088 [P] Add test_filter_resources_by_provider() to `tests/test_provider_detection.py`
- [ ] T089 [P] Add test_validate_provider_detection_success() to `tests/test_provider_detection.py`
- [ ] T090 [P] Add test_validate_provider_detection_failure() to `tests/test_provider_detection.py`

#### Integration Tests

- [ ] T091 [P] Add test_azure_diagram_generation() to `tests/integration_test.py` (end-to-end Azure test)
- [ ] T092 [P] Add test_gcp_diagram_generation() to `tests/integration_test.py` (end-to-end GCP test)
- [ ] T093 Run full pytest suite and verify all tests pass: `pytest tests/`
- [ ] T094 Test backward compatibility: run TerraVision on existing AWS Terraform projects and verify no regressions

#### Documentation

- [ ] T095 Update README.md to change Azure and GCP status from "Coming soon" to "✅ Supported"
- [ ] T096 Add "Supported Cloud Providers" section to README.md with Azure and GCP resource lists (50+ core services each)
- [ ] T097 Add "Multi-Cloud Projects" section to README.md explaining separate diagram generation
- [ ] T098 Add troubleshooting section to README.md for provider detection issues
- [ ] T099 Update version number in `terravision.py` from 0.8 to 0.9 (MINOR version bump per constitution)
- [ ] T100 Create MIGRATION.md guide for any external code importing `modules.cloud_config` (breaking change notice)

#### Visual Validation

- [ ] T101 Generate Azure diagram from real Azure Terraform project (not test fixture) and verify visual quality
- [ ] T102 Generate GCP diagram from real GCP Terraform project (not test fixture) and verify visual quality
- [ ] T103 Take screenshots of Azure and GCP diagrams for PR visual comparison (requirement CR-002)

**Completion Criteria**:
- All provider detection tests pass (10 tests)
- Integration tests pass for Azure, GCP, and multi-cloud scenarios
- No regressions in existing AWS functionality
- README updated with Azure and GCP support
- Version bumped to 0.9
- Migration guide created for breaking changes
- Visual validation complete with screenshots

---

## Task Dependencies

### Critical Path

```
Setup (T001-T007)
  ↓
Foundational (T008-T027) ← BLOCKING for all user stories
  ↓
  ├─→ US1: Azure (T028-T049) ← Can run in parallel with US2
  │
  └─→ US2: GCP (T050-T071) ← Can run in parallel with US1
      ↓
      └─→ US3: Multi-Cloud (T072-T080) ← Requires US1 AND US2 complete
          ↓
          └─→ Polish (T081-T103)
```

### Story Dependencies

- **US1 (Azure)**: Depends on Phase 2 (Foundational), Independent of US2
- **US2 (GCP)**: Depends on Phase 2 (Foundational), Independent of US1
- **US3 (Multi-Cloud)**: Depends on US1 AND US2 complete

### Parallel Execution Opportunities

**Within Foundational Phase**:
- T005, T006, T007 (test fixtures) can run in parallel

**After Foundational Phase Complete**:
- **Team A**: US1 (Azure) tasks T028-T049
- **Team B**: US2 (GCP) tasks T050-T071
- Both teams can work simultaneously (different files, no conflicts)

**Within US1 (Azure)**:
- T028 (config creation) can run parallel with T037 (handler creation)
- T048, T049 (tests) can run parallel with implementation tasks

**Within US2 (GCP)**:
- T050 (config creation) can run parallel with T059 (handler creation)
- T070, T071 (tests) can run parallel with implementation tasks

**Within Polish Phase**:
- T081-T090 (provider detection tests) all run in parallel
- T091-T092 (integration tests) run in parallel
- T095-T100 (documentation) run in parallel with testing

---

## Validation Checklist

Before marking feature complete, verify:

### Functional Requirements

- [ ] FR-001: System automatically detects cloud provider(s) from Terraform ✓
- [ ] FR-002: Azure resources supported with icon mappings ✓
- [ ] FR-003: GCP resources supported with icon mappings ✓
- [ ] FR-004: Provider-specific configs loaded from separate files ✓
- [ ] FR-005: Separate resource handlers for each provider ✓
- [ ] FR-006: Backward compatibility with AWS projects maintained ✓
- [ ] FR-007: Provider-specific styling applied to diagrams ✓
- [ ] FR-008: Multi-cloud projects generate separate diagrams per provider ✓
- [ ] FR-009: Azure diagrams support all formats (PNG, SVG, PDF, BMP) ✓
- [ ] FR-010: GCP diagrams support all formats (PNG, SVG, PDF, BMP) ✓
- [ ] FR-011: Official cloud provider icons used ✓
- [ ] FR-012: YAML annotations work for Azure and GCP ✓
- [ ] FR-013: JSON graph export works for Azure and GCP ✓
- [ ] FR-014: AI refinement works with provider-specific prompts ✓

### Success Criteria

- [ ] SC-001: Azure diagrams generated with same commands as AWS ✓
- [ ] SC-002: GCP diagrams generated with same commands as AWS ✓
- [ ] SC-003: Azure diagram performance within 20% of AWS ✓
- [ ] SC-004: GCP diagram performance within 20% of AWS ✓
- [ ] SC-005: Azure diagrams use recognizable Azure icons ✓
- [ ] SC-006: GCP diagrams use recognizable GCP icons ✓
- [ ] SC-007: No regressions in AWS functionality ✓
- [ ] SC-008: 100% detection accuracy on explicit provider blocks ✓
- [ ] SC-009: 50+ core Azure resource types supported ✓
- [ ] SC-010: 50+ core GCP resource types supported ✓
- [ ] SC-011: Icon mappings extensible without core changes ✓
- [ ] SC-012: Documentation explains Azure/GCP support ✓

### Test Coverage

- [ ] Provider detection unit tests (10 tests) ✓
- [ ] Azure integration tests (2 tests) ✓
- [ ] GCP integration tests (2 tests) ✓
- [ ] Multi-cloud integration test (1 test) ✓
- [ ] AWS regression tests pass ✓
- [ ] Visual validation complete (screenshots) ✓

---

## MVP Scope Recommendation

**Minimum Viable Product**: User Story 1 (Azure Diagram Generation)

**Rationale**:
- Delivers immediate value to Azure users (largest enterprise market)
- Establishes multi-cloud architecture pattern for future providers
- Includes all foundational infrastructure (provider detection, config loading)
- Independently testable and deployable
- Can gather user feedback before implementing GCP

**MVP Task Count**: 49 tasks (T001-T049)
**Estimated MVP Duration**: ~16 hours

**Post-MVP Releases**:
- Release 0.9.0: Azure support (US1)
- Release 0.10.0: GCP support (US2)
- Release 0.11.0: Multi-cloud support (US3)

---

## Notes

### File Path Reference

**New Files Created**:
- `modules/provider_detector.py`
- `modules/config_loader.py`
- `modules/cloud_config_azure.py`
- `modules/cloud_config_gcp.py`
- `modules/resource_handlers_azure.py`
- `modules/resource_handlers_gcp.py`
- `tests/test_provider_detection.py`
- `tests/test_azure_resources.py`
- `tests/test_gcp_resources.py`
- `tests/fixtures/azure_terraform/main.tf`
- `tests/fixtures/gcp_terraform/main.tf`
- `tests/fixtures/multi_cloud/main.tf`
- `MIGRATION.md`

**Files Renamed** (use `git mv` to preserve history):
- `modules/cloud_config.py` → `modules/cloud_config_aws.py`
- `modules/resource_handlers.py` → `modules/resource_handlers_aws.py`

**Files Modified**:
- `terravision.py` (provider detection integration, multi-output logic, imports)
- `modules/resource_handlers.py` (refactored as dispatcher)
- `modules/graphmaker.py` (provider-aware handler calls, imports)
- `modules/tfwrapper.py` (import updates)
- `modules/helpers.py` (import updates, provider utilities)
- `modules/drawing.py` (provider-aware resource imports, config loading)
- `tests/integration_test.py` (Azure, GCP, multi-cloud tests)
- `README.md` (supported providers section)

**Files Unchanged**:
- `modules/interpreter.py` (provider-agnostic)
- `modules/fileparser.py` (provider-agnostic)
- `modules/annotations.py` (provider-agnostic)
- `resource_classes/` (existing Azure and GCP classes already present)

### Breaking Changes

**Impact**: Low (TerraVision is primarily a CLI tool, not a library)

**Change**: `modules/cloud_config.py` renamed to `modules/cloud_config_aws.py`

**Affected**: Any external code directly importing `modules.cloud_config`

**Migration**: Update imports to use `config_loader.load_config('aws')` or import `modules.cloud_config_aws` directly

**CLI Users**: No changes required - all `terravision` commands work identically

---

## Success Metrics

### Code Quality
- All pytest tests passing (100% pass rate)
- No pylint errors introduced
- Code coverage maintained or improved

### Performance
- Azure diagram generation: ≤20% slower than AWS (same size project)
- GCP diagram generation: ≤20% slower than AWS (same size project)
- Provider detection: <100ms overhead

### User Experience
- Single command works for all providers (no provider flag needed)
- Clear console output for multi-cloud projects
- Icon recognition rate: >90% (users identify provider from icons alone)

---

**Ready to Start**: Begin with Phase 1 (Setup) tasks T001-T007
