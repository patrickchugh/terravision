# Tasks: Code Quality and Reliability Improvements

**Input**: Design documents from `/specs/002-code-quality-fixes/`
**Prerequisites**: plan.md (technical stack), spec.md (user stories), research.md (decisions), data-model.md (entities), contracts/ (interfaces)

**Tests**: Tests are included per user story requirements from spec.md

**Organization**: Tasks are grouped by user story (P1-P4) to enable independent implementation and testing of each priority level.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project structure (CLI tool):
- **Core modules**: `modules/` (library code)
- **Tests**: `tests/` (unit and integration tests)
- **CLI**: `terravision.py` (entry point)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and test infrastructure setup

- [X] T001 Create modules/exceptions.py with TerraVisionError base exception and specific exception types (MissingResourceError, ProviderDetectionError, MetadataInconsistencyError, TerraformParsingError)
- [X] T002 Create tests/fixtures/ directory structure
- [X] T003 [P] Create tests/fixtures/__init__.py empty module file
- [X] T004 [P] Create tests/fixtures/tfdata_samples.py with minimal_tfdata() fixture function
- [X] T005 Create tests/unit/ directory for focused unit tests
- [X] T006 [P] Create tests/unit/__init__.py empty module file
- [X] T007 Create tests/integration/ directory for end-to-end tests
- [X] T008 [P] Create tests/integration/__init__.py empty module file

**Checkpoint**: Test infrastructure ready - exception types defined, fixture structure in place

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Utility modules and fixtures that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Create modules/utils/ directory for utility modules
- [X] T010 Create modules/utils/__init__.py with imports from string_utils, terraform_utils, graph_utils, provider_utils
- [X] T011 [P] Create modules/utils/string_utils.py with find_between() and find_nth() functions extracted from helpers.py
- [X] T012 [P] Create modules/utils/terraform_utils.py with getvar() and tfvar_read() functions extracted from helpers.py
- [X] T013 [P] Create modules/utils/graph_utils.py with list_of_dictkeys_containing(), find_common_elements() optimized with set intersection, ensure_metadata(), validate_metadata_consistency() functions extracted from helpers.py
- [X] T014 [P] Create modules/utils/provider_utils.py with detect_provider() and get_provider_config() functions
- [X] T015 Update modules/helpers.py to import * from modules.utils and add DeprecationWarning
- [X] T016 [P] Add vpc_tfdata() fixture factory to tests/fixtures/tfdata_samples.py (supports vpc_count, subnet_count, endpoint_count, nat_gateway_count parameters)
- [X] T017 [P] Add vnet_tfdata() fixture factory to tests/fixtures/tfdata_samples.py (supports vnet_count, subnet_count, nsg_count, lb_count parameters)
- [X] T018 [P] Add gcp_network_tfdata() fixture factory to tests/fixtures/tfdata_samples.py (supports network_count, subnet_count, firewall_count, lb_count parameters)
- [X] T019 [P] Add multicloud_tfdata() fixture to tests/fixtures/tfdata_samples.py (combines AWS/Azure/GCP resources)

**Checkpoint**: Foundation ready - utility modules extracted, test fixtures available, user story implementation can now begin

---

## Phase 3: User Story 1 - Critical Reliability Fixes (Priority: P1) 🎯 MVP

**Goal**: Fix critical reliability issues (bare exceptions, missing VPC checks, sys.exit in library, source validation, debug hook, unused imports)

**Independent Test**: Run TerraVision on Terraform configs with missing VPCs, partial metadata, autoscaling resources, multiple .tf files, and verify graceful error handling without crashes

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US1] Create tests/unit/test_exceptions.py with tests for all exception types (base class context storage, specific attributes, inheritance hierarchy)
- [X] T021 [P] [US1] Create tests/unit/test_graph_utils.py with tests for ensure_metadata() and validate_metadata_consistency()
- [X] T022 [US1] Create tests/unit/test_aws_handlers.py with TestAWSHandleVPCEndpoints class (test_no_vpc_raises_error, test_groups_endpoints_under_vpc, test_preserves_metadata)
- [X] T023 [P] [US1] Create tests/unit/test_aws_handlers.py with TestAWSHandleAutoscaling class (test_missing_target_logs_info, test_invalid_metadata_logs_warning, test_successful_processing)
- [X] T024 [P] [US1] Add test_validate_source_all_entries() to existing tests that checks source validation for multiple inputs

### Implementation for User Story 1

- [X] T025 [US1] Fix aws_handle_vpcendpoints() in modules/resource_handlers/aws.py to check for VPC existence and raise MissingResourceError if no VPCs found (lines ~712-720)
- [X] T026 [US1] Fix aws_handle_autoscaling() in modules/resource_handlers/aws.py to replace bare except: with specific exceptions (StopIteration, KeyError, TypeError) and log appropriate messages (lines ~52-95)
- [X] T027 [US1] Fix aws_handle_natgateways() in modules/resource_handlers/aws.py to check for VPC existence before accessing VPC-dependent resources
- [X] T028 [US1] Update _validate_source() in terravision.py to validate ALL source entries (not just source[0]) and reject individual .tf files (lines ~44-54)
- [X] T029 [US1] Fix debug exception hook logic in terravision.py to show detailed tracebacks when debug=True (not when debug=False) (lines ~275-276)
- [X] T030 [US1] Remove unused 'requests' import from terravision.py (line 8)
- [X] T031 [US1] Remove stale 'graphlist' reference from default_map in terravision.py (lines ~352-357)
- [ ] T032 [US1] Update all AWS handlers to use ensure_metadata() when creating new graph nodes to prevent metadata inconsistencies
- [X] T033 [US1] Update terravision.py CLI error handling to catch and display TerraVisionError exceptions with appropriate styling (INFO=yellow, WARNING=yellow bold, ERROR=red bold)

**Checkpoint**: User Story 1 complete - critical reliability fixes implemented, all tests passing, no crashes on edge cases

---

## Phase 4: User Story 2 - Azure and GCP Provider Support (Priority: P2)

**Goal**: Implement complete Azure and GCP resource handlers for VNets/VPCs, security groups/firewalls, and load balancers

**Independent Test**: Process Azure and GCP Terraform configs with VNets/VPCs, NSGs/firewalls, load balancers and verify correct diagram generation with proper resource groupings

### Tests for User Story 2

- [X] T034 [P] [US2] Create tests/unit/test_azure_handlers.py with TestAzureHandleVNetSubnets class (test_no_vnet_with_subnets_raises_error, test_groups_subnets_under_vnet, test_matches_by_virtual_network_name, test_preserves_subnet_metadata)
- [X] T035 [P] [US2] Create tests/unit/test_azure_handlers.py with TestAzureHandleNSG class (test_reverses_nsg_connections, test_wraps_nics_under_nsg)
- [X] T036 [P] [US2] Create tests/unit/test_azure_handlers.py with TestAzureHandleLB class (test_detects_basic_sku, test_detects_standard_sku, test_updates_metadata_with_lb_type)
- [X] T037 [P] [US2] Create tests/unit/test_gcp_handlers.py with TestGCPHandleNetworkSubnets class (test_no_network_raises_error, test_groups_subnets_under_network, test_matches_by_network_attribute, test_preserves_subnet_metadata)
- [X] T038 [P] [US2] Create tests/unit/test_gcp_handlers.py with TestGCPHandleFirewall class (test_adds_direction_to_metadata, test_handles_ingress_rules, test_handles_egress_rules, test_processes_target_tags)
- [X] T039 [P] [US2] Create tests/unit/test_gcp_handlers.py with TestGCPHandleLB class (test_detects_http_lb, test_detects_tcp_lb, test_detects_internal_lb, test_updates_metadata_with_lb_type)
- [X] T040 [P] [US2] Create tests/integration/test_multicloud.py with test_azure_gcp_mixed_config() and test_azure_gcp_security_mixed() and test_azure_gcp_load_balancers()

### Implementation for User Story 2

- [x] T041 [P] [US2] Implement azure_handle_vnet_subnets() in modules/resource_handlers/azure.py to group subnets under VNets based on virtual_network_name metadata
- [x] T042 [P] [US2] Implement azure_handle_nsg() in modules/resource_handlers/azure.py to reverse NSG connections (NSG wraps NICs) similar to AWS security groups
- [x] T043 [P] [US2] Implement azure_handle_lb() in modules/resource_handlers/azure.py to detect load balancer SKU (Basic/Standard) from metadata and update display attributes
- [x] T044 [P] [US2] Implement azure_handle_app_gateway() in modules/resource_handlers/azure.py to process Application Gateway SKUs (Standard_v2/WAF_v2)
- [x] T045 [P] [US2] Implement gcp_handle_network_subnets() in modules/resource_handlers/gcp.py to group subnets under VPC networks based on network attribute
- [x] T046 [P] [US2] Implement gcp_handle_firewall() in modules/resource_handlers/gcp.py to process firewall rules with direction (INGRESS/EGRESS) and target tags
- [x] T047 [P] [US2] Implement gcp_handle_lb() in modules/resource_handlers/gcp.py to detect LB type (HTTP(S)/TCP/Internal) from protocol and load_balancing_scheme metadata
- [x] T048 [P] [US2] Implement gcp_handle_cloud_dns() in modules/resource_handlers/gcp.py to group DNS records under managed zones
- [x] T049 [US2] Update modules/resource_handlers/__init__.py to export new Azure and GCP handler functions
- [x] T050 [US2] Update provider detection logic in modules/provider_runtime.py to handle Azure (azurerm_*) and GCP (google_*) resource prefixes
- [x] T051 [US2] Update handler orchestration to call Azure and GCP handlers when appropriate provider is detected

**Checkpoint**: ✅ User Story 2 COMPLETE - Azure and GCP support fully implemented, mixed provider configs work correctly
- 37 new tests added (22 GCP, 10 Azure, 5 integration) - all passing
- All handlers implemented and verified
- Multi-cloud coexistence confirmed via integration tests

---

## Phase 5: User Story 3 - Developer Experience and Maintainability (Priority: P3)

**Goal**: Add comprehensive unit tests for AWS handlers, migrate to ProviderRegistry, add metadata helpers, evaluate transformation_functions.py

**Independent Test**: Run test suite showing 80%+ coverage for handlers, verify all code uses ProviderRegistry instead of cloud_config constants, confirm helpers split is complete

### Tests for User Story 3

- [ ] T052 [P] [US3] Create tests/unit/test_string_utils.py with tests for find_between() (test_simple_extraction, test_nested_parentheses, test_replacement_mode, test_nth_occurrence)
- [ ] T053 [P] [US3] Create tests/unit/test_terraform_utils.py with tests for getvar() (test_nested_access, test_default_value, test_invalid_path) and tfvar_read() (test_parses_hcl, test_parses_json, test_file_not_found)
- [ ] T054 [P] [US3] Create tests/unit/test_provider_utils.py with tests for detect_provider() (test_aws_detection, test_azure_detection, test_gcp_detection, test_mixed_providers_raises_error, test_unknown_provider)
- [ ] T055 [P] [US3] Add TestAWSHandleSG class to tests/unit/test_aws_handlers.py (test_reverses_sg_connections, test_creates_unique_sg_nodes, test_preserves_metadata)
- [ ] T056 [P] [US3] Add TestAWSHandleLoadBalancer class to tests/unit/test_aws_handlers.py (test_detects_alb, test_detects_nlb, test_detects_clb, test_updates_metadata)
- [ ] T057 [P] [US3] Add TestAWSHandleEFS class to tests/unit/test_aws_handlers.py (test_groups_mount_targets, test_handles_missing_filesystem)
- [ ] T058 [P] [US3] Add TestAWSHandleNATGateways class to tests/unit/test_aws_handlers.py (test_groups_under_subnets, test_handles_missing_vpc)
- [ ] T059 [P] [US3] Add TestAWSHandleIAMRoles class to tests/unit/test_aws_handlers.py (test_processes_role_attachments, test_handles_policies)

### Implementation for User Story 3

- [ ] T060 [US3] Migrate modules/graphmaker.py line 19 TODO to use ProviderRegistry.get_provider() instead of hard-coded AWS assumptions
- [ ] T061 [US3] Migrate modules/drawing.py icon path lookups to use ProviderRegistry.get_provider().icon_base_path
- [ ] T062 [US3] Migrate modules/service_mapping.py resource type mappings to use ProviderRegistry
- [ ] T063 [US3] Search for all direct imports of cloud_config constants (AWS_CONSOLIDATED_NODES, etc.) and replace with ProviderRegistry usage
- [ ] T064 [US3] Add deprecation warnings to modules/cloud_config.py for direct constant access
- [ ] T065 [US3] Create initialize_metadata() helper function in modules/utils/graph_utils.py for consistent metadata entry creation
- [ ] T066 [US3] Evaluate transformation_functions.py - determine if logic is used in current pipeline or can be removed, document decision in plan.md
- [ ] T067 [US3] Create docs/ERROR_HANDLING.md documenting exception hierarchy, severity levels (INFO/WARNING/ERROR), and Click styling patterns
- [ ] T068 [US3] Create docs/JSON_INPUT_FORMAT.md documenting required JSON structure and validation rules
- [ ] T069 [US3] Update terravision.py to log WARNING when provider detection defaults to AWS
- [ ] T070 [US3] Update terravision.py to log WARNING when enrichment is skipped for JSON inputs without all_resource key

**Checkpoint**: User Story 3 complete - comprehensive test coverage achieved, ProviderRegistry migration complete, developer documentation in place

---

## Phase 6: User Story 4 - Performance and Scalability (Priority: P4)

**Goal**: Optimize find_common_elements with set operations, cache sorted results, refactor find_between parsing

**Independent Test**: Process large Terraform configs (100+ resources) and verify 30%+ performance improvement, benchmark find_common_elements O(n+m) complexity

### Tests for User Story 4

- [ ] T071 [P] [US4] Add test_find_common_elements_performance() to tests/unit/test_graph_utils.py with 10k element lists, verify <0.1s execution
- [ ] T072 [P] [US4] Add test_find_common_elements_correctness() to tests/unit/test_graph_utils.py verifying set-based results match nested loop results
- [ ] T073 [P] [US4] Add test_find_between_nested_parens() to tests/unit/test_string_utils.py with deeply nested parentheses
- [ ] T074 [P] [US4] Create tests/performance_test.py test_large_config_processing() with 100-resource and 500-resource fixtures, benchmark before/after times

### Implementation for User Story 4

- [ ] T075 [US4] Optimize find_common_elements() in modules/utils/graph_utils.py to use set intersection (set1 & set2) instead of nested loops
- [ ] T076 [US4] Add sorted() call to find_common_elements() return to ensure deterministic output
- [ ] T077 [US4] Refactor aws_handle_sg() in modules/resource_handlers/aws.py to cache sorted(tfdata["graphdict"].keys()) outside loop
- [ ] T078 [US4] Review all resource handlers for repeated sorting operations inside loops and extract to cached variables
- [ ] T079 [US4] Refactor find_between() in modules/utils/string_utils.py to use stack-based parsing for nested delimiters instead of complex index calculations
- [ ] T080 [US4] Add _extract_nested_parens() helper function to modules/utils/string_utils.py for proper paren matching
- [ ] T081 [US4] Run performance benchmarks on 100-resource and 500-resource configs, document before/after times in PHASE4-COMPLETION-SUMMARY.md
- [ ] T082 [US4] Verify 30%+ performance improvement target achieved for large configs

**Checkpoint**: User Story 4 complete - performance optimizations implemented and verified, targets achieved

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple user stories

- [ ] T083 [P] Run poetry run black . to format all Python code
- [ ] T084 [P] Run poetry run isort . to organize imports (skip drawing.py per pyproject.toml)
- [ ] T085 [P] Run poetry run pre-commit run --all-files to verify all checks pass
- [ ] T086 Run poetry run pytest to verify all fast tests pass
- [ ] T087 Run poetry run pytest -m "" to verify all tests (including slow integration tests) pass
- [ ] T088 Run poetry run pytest --cov=modules --cov-report=html to generate coverage report, verify 80%+ overall coverage
- [ ] T089 [P] Update AGENTS.md with new test patterns, module structure, exception handling patterns
- [ ] T090 [P] Update README.md with information about new Azure/GCP support and improved error handling
- [ ] T091 [P] Create or update docs/CONTRIBUTING.md with quickstart.md patterns, testing requirements, code style guidelines
- [ ] T092 Run validation from specs/002-code-quality-fixes/quickstart.md example workflow to ensure developer onboarding guide works
- [ ] T093 Verify all tasks marked with [X] in this tasks.md file
- [ ] T094 Create PHASE4-COMPLETION-SUMMARY.md documenting all changes, test coverage metrics, performance improvements, migration notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion, can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on Foundational phase completion, should run after US1 (uses AWS handlers for testing)
- **User Story 4 (Phase 6)**: Depends on Foundational phase completion, should run after US3 (optimizes utils modules)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent - only depends on Foundational phase
- **User Story 2 (P2)**: Independent - only depends on Foundational phase, can run in parallel with US1
- **User Story 3 (P3)**: Depends on US1 (tests AWS handlers), should run after US1 complete
- **User Story 4 (P4)**: Depends on US3 (optimizes utils modules), should run after US3 complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD approach)
- Exception types before handlers that use them (US1)
- Fixtures before tests that use them (all stories)
- Utils modules before handlers that import them (US1, US2)
- Handler implementation before integration tests (US2)
- Migration tasks before deprecation warnings (US3)

### Parallel Opportunities

#### Phase 1: Setup
- T003, T004, T006, T008 (directory __init__ files) can run in parallel

#### Phase 2: Foundational
- T011, T012, T013, T014 (utils module creation) can run in parallel
- T016, T017, T018, T019 (fixture factories) can run in parallel after T004 complete

#### Phase 3: User Story 1 Tests
- T020, T021, T023, T024 can run in parallel (different test files)

#### Phase 4: User Story 2 Tests
- T034-T039 (Azure/GCP handler tests) can run in parallel

#### Phase 4: User Story 2 Implementation
- T041-T048 (Azure/GCP handlers) can run in parallel (different files)

#### Phase 5: User Story 3 Tests
- T052-T059 (all test files) can run in parallel

#### Phase 6: User Story 4 Tests
- T071-T074 (performance tests) can run in parallel

#### Phase 7: Polish
- T083, T084, T085, T089, T090, T091 can run in parallel (different files)

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all US1 tests together:
Task: "Create tests/unit/test_exceptions.py with tests for all exception types"
Task: "Create tests/unit/test_graph_utils.py with tests for ensure_metadata()"
Task: "Create tests/unit/test_aws_handlers.py with TestAWSHandleAutoscaling class"
Task: "Add test_validate_source_all_entries() to existing tests"
```

## Parallel Example: User Story 2 Implementation

```bash
# Launch all Azure handlers together:
Task: "Implement azure_handle_vnet_subnets() in modules/resource_handlers/azure.py"
Task: "Implement azure_handle_nsg() in modules/resource_handlers/azure.py"
Task: "Implement azure_handle_lb() in modules/resource_handlers/azure.py"
Task: "Implement azure_handle_app_gateway() in modules/resource_handlers/azure.py"

# Launch all GCP handlers together:
Task: "Implement gcp_handle_network_subnets() in modules/resource_handlers/gcp.py"
Task: "Implement gcp_handle_firewall() in modules/resource_handlers/gcp.py"
Task: "Implement gcp_handle_lb() in modules/resource_handlers/gcp.py"
Task: "Implement gcp_handle_cloud_dns() in modules/resource_handlers/gcp.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T008)
2. Complete Phase 2: Foundational (T009-T019) - CRITICAL foundation
3. Complete Phase 3: User Story 1 (T020-T033)
4. **STOP and VALIDATE**: Run pytest, verify no crashes on edge cases
5. Deploy/demo critical reliability fixes

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (T001-T019)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP - critical fixes)
3. Add User Story 2 → Test independently → Deploy/Demo (Azure/GCP support)
4. Add User Story 3 → Test independently → Deploy/Demo (maintainability improvements)
5. Add User Story 4 → Test independently → Deploy/Demo (performance optimizations)
6. Polish → Final release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T019)
2. Once Foundational is done:
   - Developer A: User Story 1 (T020-T033) - critical reliability
   - Developer B: User Story 2 (T034-T051) - Azure/GCP support
3. After US1 complete:
   - Developer C: User Story 3 (T052-T070) - maintainability
4. After US3 complete:
   - Developer D: User Story 4 (T071-T082) - performance
5. All developers: Polish phase together (T083-T094)

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story (US1-US4) for traceability
- Each user story is independently completable and testable
- Tests MUST fail before implementing (TDD approach)
- Commit after each task or logical group of related tasks
- Stop at each checkpoint to validate story independently
- Total tasks: 94
- MVP scope: T001-T033 (Setup + Foundational + US1 = 33 tasks)
- Performance target: 30%+ improvement for 100+ resource configs
- Coverage target: 80%+ overall, 90%+ for resource handlers
