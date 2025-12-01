---
description: "Implementation tasks for Provider Abstraction Layer"
---

# Tasks: Provider Abstraction Layer

**Input**: Design documents from `/specs/001-provider-abstraction-layer/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create `modules/cloud_config/` directory structure
- [X] T002 Create `tests/fixtures/` for provider test data
- [X] T003 [P] Add typing imports to pyproject.toml if missing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create `modules/service_mapping.py` with ServiceCategory enum (40+ categories from data-model.md)
- [X] T005 Implement ServiceMapping class in `modules/service_mapping.py` with category resolution logic
- [X] T006 Create `modules/provider_runtime.py` with ProviderDescriptor dataclass (12 fields from contracts/provider_descriptor.md)
- [X] T007 Implement ProviderContext class in `modules/provider_runtime.py` (lazy loading, 4 properties, 3 methods from contracts/provider_context.md)
- [X] T008 Implement ProviderRegistry singleton in `modules/provider_runtime.py` (register, get_descriptor, get_context, detect_providers)
- [X] T009 Create `modules/node_factory.py` with NodeFactory class and LRU cache decorator
- [X] T010 Create `modules/cloud_config/common.py` with shared types (NodeAttributes, IconPath, ResourceType)
- [X] T011 Create `modules/cloud_config/__init__.py` with provider registration imports
- [X] T012 Add provider detection logic to `modules/tfwrapper.py` (hybrid approach: plan metadata + prefix fallback from research.md)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - AWS User Maintains Current Workflow (Priority: P1) 🎯 MVP

**Goal**: Achieve 100% backwards compatibility - existing AWS workflows continue unchanged

**Independent Test**: Run `poetry run pytest tests/integration_test.py` and all existing AWS test cases pass with zero regressions

### Implementation for User Story 1

- [ ] T013 [US1] Extract AWS color constants from `modules/cloud_config.py` to `modules/cloud_config/aws.py`
- [ ] T014 [US1] Extract AWS icon configuration from `modules/cloud_config.py` to `modules/cloud_config/aws.py`
- [ ] T015 [US1] Extract AWS label mappings from `modules/cloud_config.py` to `modules/cloud_config/aws.py`
- [ ] T016 [US1] Extract AWS resource-to-class mappings from `modules/cloud_config.py` to `modules/cloud_config/aws.py`
- [ ] T017 [US1] Register AWS provider in `modules/cloud_config/__init__.py` using ProviderRegistry (id="aws", default=True)
- [ ] T018 [US1] Update `modules/graphmaker.py` to use ProviderContext.get_context("aws") instead of direct AWS imports
- [ ] T019 [US1] Update `modules/drawing.py` to use NodeFactory.resolve_class() instead of direct AWS imports
- [ ] T020 [US1] Update `modules/helpers.py` to use provider-aware config lookup (maintain AWS defaults)
- [ ] T021 [US1] Update `modules/interpreter.py` to use provider-aware resource type detection (maintain AWS regex patterns)
- [ ] T022 [US1] Update `modules/annotations.py` to use provider-aware AUTO_ANNOTATIONS (maintain AWS annotations)
- [ ] T023 [US1] Add backwards compatibility shim in `modules/cloud_config.py` (re-export AWS constants with deprecation warnings)
- [ ] T024 [US1] Validate zero regressions by running `poetry run pytest tests/integration_test.py`
- [ ] T025 [US1] Validate performance overhead <200ms using existing test fixtures

**Checkpoint**: At this point, User Story 1 should be fully functional - all existing AWS workflows work unchanged

---

## Phase 4: User Story 2 - Multi-Cloud Engineer Specifies Provider (Priority: P2)

**Goal**: Enable Azure and GCP support via `--provider` CLI flag

**Independent Test**: 
1. Run `terravision --provider azure examples/azure-sample.tf` and verify Azure diagram generation
2. Run `terravision --provider gcp examples/gcp-sample.tf` and verify GCP diagram generation
3. Run `terravision --provider auto examples/multi-cloud.tf` and verify mixed-provider detection

### Implementation for User Story 2

- [ ] T026 [P] [US2] Create `modules/cloud_config/azure.py` with minimal Azure provider config (colors, 5-10 core services from resource_classes/azure/)
- [ ] T027 [P] [US2] Create `modules/cloud_config/gcp.py` with minimal GCP provider config (colors, 5-10 core services from resource_classes/gcp/)
- [ ] T028 [US2] Register Azure provider in `modules/cloud_config/__init__.py` using ProviderRegistry (id="azure", default=False)
- [ ] T029 [US2] Register GCP provider in `modules/cloud_config/__init__.py` using ProviderRegistry (id="gcp", default=False)
- [ ] T030 [US2] Add `--provider` click option to `terravision.py` (choices: auto, aws, azure, gcp; default: auto)
- [ ] T031 [US2] Update `terravision.py` main() to pass provider flag to graphmaker and drawing modules
- [ ] T032 [US2] Update `modules/graphmaker.py` to support multi-provider resource processing (provider context switching)
- [ ] T033 [US2] Update `modules/drawing.py` to support multi-provider node rendering (icon fallback chain)
- [ ] T034 [US2] Implement 3-level icon fallback in NodeFactory (provider-specific → generic category → blank from research.md)
- [ ] T035 [US2] Add generic category icons to `resource_images/generic/` for fallback (compute, network, storage, database)
- [ ] T036 [P] [US2] Create `tests/fixtures/azure-sample.tf` for Azure integration testing
- [ ] T037 [P] [US2] Create `tests/fixtures/gcp-sample.tf` for GCP integration testing
- [ ] T038 [P] [US2] Create `tests/fixtures/multi-cloud-sample.tf` for mixed-provider testing
- [ ] T039 [US2] Validate Azure diagram generation with `tests/fixtures/azure-sample.tf`
- [ ] T040 [US2] Validate GCP diagram generation with `tests/fixtures/gcp-sample.tf`
- [ ] T041 [US2] Validate auto-detection with `tests/fixtures/multi-cloud-sample.tf`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Contributor Adds New Provider (Priority: P3)

**Goal**: Validate extensibility by adding a minimal test provider following quickstart.md

**Independent Test**: 
1. Follow `quickstart.md` to add a fictional "DigitalOcean" provider
2. Verify provider registration succeeds
3. Verify sample DigitalOcean resource renders with correct icon/color
4. Complete process in <2 hours (SC-005 from spec.md)

### Implementation for User Story 3

- [ ] T042 [US3] Validate `quickstart.md` steps 1-4 (directory creation) by creating `modules/cloud_config/digitalocean.py`
- [ ] T043 [US3] Validate `quickstart.md` step 5 (provider config) by implementing minimal DigitalOcean config
- [ ] T044 [US3] Validate `quickstart.md` step 6 (registration) by adding DigitalOcean to `modules/cloud_config/__init__.py`
- [ ] T045 [US3] Validate `quickstart.md` step 7 (resource classes) by creating 2-3 test DigitalOcean resource classes
- [ ] T046 [US3] Validate `quickstart.md` step 8 (icons) by adding test icons to `resource_images/digitalocean/`
- [ ] T047 [US3] Validate `quickstart.md` step 9 (service mapping) by mapping DigitalOcean resources to categories
- [ ] T048 [US3] Validate `quickstart.md` step 10 (testing) by creating `tests/test_digitalocean_provider.py`
- [ ] T049 [US3] Validate `quickstart.md` step 11 (validation) by running provider tests
- [ ] T050 [US3] Validate `quickstart.md` step 12 (documentation) by checking provider appears in CLI help
- [ ] T051 [US3] Time entire quickstart process and verify <2 hours completion (SC-005)
- [ ] T052 [US3] Create PR checklist template based on quickstart validation experience

**Checkpoint**: All user stories should now be independently functional and extensibility is validated

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T053 [P] Update `README.md` with `--provider` flag documentation and multi-cloud examples
- [ ] T054 [P] Update `docs/ARCHITECTURAL.md` with provider abstraction layer architecture diagram
- [ ] T055 [P] Add provider system documentation to `docs/` (architecture, extension guide, migration guide)
- [ ] T056 Code cleanup: Remove deprecated AWS-specific imports and update all docstrings
- [ ] T057 Performance validation: Run benchmark suite and verify <10% overhead (SC-006 from spec.md)
- [ ] T058 [P] Security audit: Review provider registration for injection risks
- [ ] T059 [P] Add unit tests for ProviderDescriptor in `tests/test_provider_runtime.py`
- [ ] T060 [P] Add unit tests for ProviderContext lazy loading in `tests/test_provider_runtime.py`
- [ ] T061 [P] Add unit tests for ProviderRegistry in `tests/test_provider_runtime.py`
- [ ] T062 [P] Add unit tests for NodeFactory resolution in `tests/test_node_factory.py`
- [ ] T063 [P] Add unit tests for ServiceMapping in `tests/test_service_mapping.py`
- [ ] T064 Run `poetry run pre-commit run --all-files` and fix any issues
- [ ] T065 Validate test coverage improvement: Run `poetry run pytest --cov` and verify >80% coverage (SC-007 from spec.md)
- [ ] T066 Run full integration test suite: `poetry run pytest tests/integration_test.py -v`
- [ ] T067 Run quickstart.md end-to-end validation with fresh contributor perspective

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Builds on US1 patterns but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Validates extensibility of US1+US2 implementation

### Within Each User Story

#### User Story 1 (AWS Backwards Compatibility)
- Extract config files (T013-T016) can run in parallel
- Provider registration (T017) depends on extracts completing
- Module updates (T018-T022) can start after T017
- Validation tasks (T023-T025) run last

#### User Story 2 (Multi-Cloud Support)
- Azure/GCP config creation (T026-T027) can run in parallel
- Provider registration (T028-T029) can run in parallel after config creation
- CLI flag (T030-T031) independent of provider configs
- Module updates (T032-T035) depend on CLI flag + provider registration
- Test fixture creation (T036-T038) can run in parallel
- Validation tasks (T039-T041) run last

#### User Story 3 (Extensibility Validation)
- Quickstart validation (T042-T050) must run sequentially (follows tutorial flow)
- Documentation (T051-T052) runs last

### Parallel Opportunities

- **Phase 1**: All setup tasks can run in parallel
- **Phase 2**: T004-T005 can run in parallel; T006-T008 can run in parallel; T009-T012 are independent
- **Phase 3 (US1)**: T013-T016 can run in parallel; T018-T022 can run in parallel after T017
- **Phase 4 (US2)**: T026-T027 can run in parallel; T028-T029 can run in parallel; T036-T038 can run in parallel
- **Phase 6 (Polish)**: T053-T055 can run in parallel; T058-T063 can run in parallel
- **Cross-story parallelism**: With multiple developers, US1/US2/US3 can progress simultaneously after Phase 2

---

## Parallel Example: Foundational Phase

```bash
# Launch parallel foundational tasks:
# Group 1: Service mapping (independent)
Task T004: "Create ServiceMapping with 40+ categories"
Task T005: "Implement ServiceMapping class with resolution"

# Group 2: Provider runtime (independent of Group 1)
Task T006: "Create ProviderDescriptor dataclass"
Task T007: "Implement ProviderContext with lazy loading"
Task T008: "Implement ProviderRegistry singleton"

# Group 3: Other foundational pieces (independent)
Task T009: "Create NodeFactory with LRU cache"
Task T010: "Create cloud_config/common.py shared types"
Task T011: "Create cloud_config/__init__.py registration"
Task T012: "Add provider detection to tfwrapper.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

**Goal**: Achieve zero-regression AWS backwards compatibility

1. ✅ Complete Phase 1: Setup (T001-T003)
2. ✅ Complete Phase 2: Foundational (T004-T012) - CRITICAL blocker
3. ✅ Complete Phase 3: User Story 1 (T013-T025)
4. **STOP and VALIDATE**: 
   - Run `poetry run pytest tests/integration_test.py` - all tests pass
   - Run performance benchmark - overhead <200ms
   - Manually test existing AWS examples
5. **Deploy/demo if ready** - MVP delivers constitution requirement (backwards compatibility)

**Success Metrics for MVP**:
- Zero regressions in existing test suite (SC-001 ✅)
- Performance overhead <10% (SC-006 ✅)
- All AWS workflows unchanged (US1 acceptance criteria ✅)

---

### Incremental Delivery

**Iteration 1: MVP (US1 Only)**
1. Phases 1-3 (Setup + Foundation + US1)
2. Validate: Zero AWS regressions
3. Deploy: Existing users see no change
4. **Business Value**: Risk mitigation - safe refactor with zero user impact

**Iteration 2: Multi-Cloud (US1 + US2)**
1. Phase 4 (US2 - Azure + GCP)
2. Validate: All three providers work independently
3. Deploy: New `--provider` flag available
4. **Business Value**: Expanded market - Azure/GCP users can adopt TerraVision

**Iteration 3: Extensibility (US1 + US2 + US3)**
1. Phase 5 (US3 - Quickstart validation)
2. Validate: <2 hour contributor onboarding
3. Deploy: Community can add providers
4. **Business Value**: Community growth - reduced maintenance burden

**Iteration 4: Production Ready**
1. Phase 6 (Polish)
2. Validate: Test coverage >80%, docs complete
3. Deploy: Full production release
4. **Business Value**: Professional quality - enterprise adoption ready

---

### Parallel Team Strategy

**With 3 developers after Foundational phase completes:**

- **Developer A (US1 - MVP Critical Path)**:
  - T013-T025: AWS backwards compatibility
  - Focus: Zero regressions, performance validation
  - Timeline: 3-5 days
  
- **Developer B (US2 - Multi-Cloud)**:
  - T026-T041: Azure + GCP support
  - Focus: Provider configs, CLI integration, testing
  - Timeline: 5-7 days (can start after Dev A completes T017)
  
- **Developer C (US3 - Extensibility)**:
  - T042-T052: Quickstart validation
  - Focus: Documentation quality, contributor experience
  - Timeline: 2-3 days (can start after Dev B completes T029)

**Integration Points**:
- Day 3: Dev A completes US1 → Dev B starts Azure/GCP configs
- Day 6: Dev B completes US2 → Dev C starts quickstart validation
- Day 9: All stories merge → Phase 6 polish begins

---

## Critical Path Analysis

### Blocking Dependencies (Must Complete First)

**Critical Path**: Phase 1 → Phase 2 → Phase 3 (T013-T017) → Phase 3 (T018-T025) → MVP Complete

1. **T001-T003**: Directory structure (1 hour)
2. **T004-T012**: Foundational infrastructure (8-12 hours) - HIGHEST RISK
3. **T013-T017**: AWS config extraction + registration (4-6 hours)
4. **T018-T022**: Module refactoring (6-8 hours) - HIGHEST COMPLEXITY
5. **T023-T025**: Validation (2-4 hours)

**Total MVP Critical Path**: ~22-32 hours of focused development

### High-Risk Tasks

- **T006-T008** (ProviderRuntime): Complex lazy loading logic, caching strategy
- **T012** (Provider detection): Hybrid detection algorithm, edge case handling
- **T018-T022** (Module refactoring): Touches 5 core modules, high regression risk
- **T032-T034** (Multi-provider support): Icon fallback chain, context switching complexity

### Mitigation Strategies

1. **For T006-T008**: Write unit tests FIRST for ProviderContext lazy loading
2. **For T012**: Test with fixtures from research.md (AWS, Azure, GCP, mixed samples)
3. **For T018-T022**: One module at a time, run full test suite after each module
4. **For T032-T034**: Use existing generic icons as fallback to avoid blocking on icon creation

---

## Testing Strategy

### Test Pyramid

**Unit Tests** (Phase 6: T059-T063):
- `tests/test_provider_runtime.py`: ProviderDescriptor, ProviderContext, ProviderRegistry
- `tests/test_node_factory.py`: NodeFactory resolution, LRU cache behavior
- `tests/test_service_mapping.py`: Category mapping, fallback logic
- Target: >80% coverage for new modules

**Integration Tests** (Built into US phases):
- **US1 (T024)**: Existing `tests/integration_test.py` - zero regression validation
- **US2 (T036-T041)**: New Azure/GCP fixtures - multi-provider validation
- **US3 (T048-T049)**: DigitalOcean provider tests - extensibility validation

**Performance Tests**:
- **US1 (T025)**: Benchmark overhead <200ms with existing fixtures
- **Phase 6 (T057)**: Full benchmark suite <10% overhead (SC-006)

**Manual Validation**:
- **US1**: Run existing AWS examples manually
- **US2**: Test `--provider` flag with all three providers
- **US3**: Follow quickstart.md from contributor perspective (<2 hours)

---

## Notes

- **[P] tasks** = different files, no dependencies, can run in parallel
- **[Story] label** maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Performance budget**: <200ms overhead (T025, T057)
- **Test coverage target**: >80% for new modules (T065)
- **Contributor onboarding target**: <2 hours for new provider (T051)

---

## Task Count Summary

- **Phase 1 (Setup)**: 3 tasks
- **Phase 2 (Foundational)**: 9 tasks ⚠️ BLOCKS ALL STORIES
- **Phase 3 (US1 - MVP)**: 13 tasks
- **Phase 4 (US2 - Multi-cloud)**: 16 tasks
- **Phase 5 (US3 - Extensibility)**: 11 tasks
- **Phase 6 (Polish)**: 15 tasks

**Total**: 67 implementation tasks

**MVP Subset** (Phase 1 + 2 + 3): 25 tasks (~22-32 hours critical path)
