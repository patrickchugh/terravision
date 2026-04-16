# Tasks: Native draw.io mxGraph Emitter

**Input**: Design documents from `/specs/012-native-drawio-emitter/`  
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — the spec requires comprehensive test coverage for the new emitter.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No project initialization needed — this feature adds modules to an existing codebase. This phase ensures prerequisite knowledge is captured.

- [x] T001 Review existing drawio export code path in modules/drawing.py (lines 26-28, 1352-1373) to confirm current behavior before replacement
- [x] T002 Generate a sample xdot output by running `dot -Txdot` on an existing post-processed DOT file to use as reference for parser development

**Checkpoint**: Understand the current pipeline and have reference xdot output for parser development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The xdot parser is the core building block that ALL user stories depend on. No emitter work can begin until parsing is solid.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Create xdot parser module with `run_xdot()` function that invokes `dot -Txdot` via subprocess in modules/xdot_parser.py
- [x] T004 Implement `parse_xdot()` function to extract graph bounding box from root `bb=` attribute in modules/xdot_parser.py
- [x] T005 Implement node parsing in `parse_xdot()` to extract `pos`, `width`, `height`, `label`, `image`, and custom attrs (`_titlenode`, `_footernode`, `_legendnode`, `_clusterlabel`, `_edgenode`) in modules/xdot_parser.py
- [x] T006 Implement cluster/subgraph parsing in `parse_xdot()` to extract `bb`, `label`, `style`, and parent-child relationships in modules/xdot_parser.py
- [x] T007 Implement edge parsing in `parse_xdot()` to extract source/target node IDs, labels, label positions, and bidirectional markers in modules/xdot_parser.py
- [x] T008 [P] Write unit tests for xdot parser covering nodes, clusters, edges, empty graph, and malformed input in tests/test_xdot_parser.py
- [x] T009 Run `poetry run black modules/xdot_parser.py` and `poetry run pytest tests/test_xdot_parser.py -v` to validate

**Checkpoint**: xdot parser is complete, tested, and produces structured data from any post-processed DOT file

---

## Phase 3: User Story 1 — Generate draw.io Diagram from Terraform Code (Priority: P1) MVP

**Goal**: End-to-end drawio generation with native provider shape-library icons for AWS, Azure, and GCP. This is the core value — a working `.drawio` file from any Terraform project.

**Independent Test**: Run `poetry run terravision draw --source <terraform-dir> --format drawio`, open in draw.io, verify all resources/connections/groupings present with native icons.

### Implementation for User Story 1

- [x] T010 [US1] Create mxGraph emitter skeleton with `emit_drawio()` function, root cell generation (id=0, id=1), and coordinate transformation (Y-flip) in modules/drawio_emitter.py
- [x] T011 [US1] Implement node mxCell generation in `emit_drawio()` — convert XdotNode positions/dimensions to mxCell vertices with geometry in modules/drawio_emitter.py
- [x] T012 [US1] Implement cluster mxCell generation in `emit_drawio()` — convert XdotCluster bounding boxes to group cells with parent-child hierarchy in modules/drawio_emitter.py
- [x] T013 [US1] Implement edge mxCell generation in `emit_drawio()` — create edge cells with source/target references, orthogonal routing style, and bidirectional arrow support in modules/drawio_emitter.py
- [x] T014 [US1] Implement title, footer, and legend node rendering — detect `_titlenode`, `_footernode`, `_legendnode` attributes and render as plaintext mxCells at xdot positions in modules/drawio_emitter.py
- [x] T015 [US1] Implement `load_shape_map()` function with dynamic provider import following CO-004 pattern in modules/drawio_emitter.py
- [x] T016 [US1] Implement native shape style construction — build mxCell style strings using draw.io shape-library identifiers (e.g., `shape=mxgraph.aws4.lambda_function;...`) in modules/drawio_emitter.py
- [x] T017 [US1] Implement fallback PNG style construction — read icon file, encode as base64, build `shape=image;image=data:image/png;base64,...` style for unmapped resource types in modules/drawio_emitter.py
- [x] T018 [P] [US1] Create AWS shape mapping dictionary (top 100+ resource types) in modules/config/drawio_shape_map_aws.py
- [x] T019 [P] [US1] Create Azure shape mapping dictionary (top 80+ resource types) in modules/config/drawio_shape_map_azure.py
- [x] T020 [P] [US1] Create GCP shape mapping dictionary (top 40+ resource types) in modules/config/drawio_shape_map_gcp.py
- [x] T021 [US1] Replace the `if format == "drawio":` block in modules/drawing.py (lines 1352-1373) with native emitter: call `run_xdot()`, `parse_xdot()`, `load_shape_map()`, `emit_drawio()`, write output, and handle `--show` via `click.launch()`
- [x] T022 [US1] Remove conditional import of `graphviz2drawio` (lines 26-28) in modules/drawing.py
- [x] T023 [US1] Implement XML escaping for all label/attribute values to prevent malformed XML from special characters in modules/drawio_emitter.py
- [x] T024 [P] [US1] Write unit tests for mxGraph emitter covering valid XML output, root cells, node count, coordinate transformation, XML escaping, native vs fallback styles in tests/test_drawio_emitter.py
- [x] T025 [US1] Run `poetry run black modules/drawio_emitter.py modules/drawing.py modules/config/drawio_shape_map_aws.py modules/config/drawio_shape_map_azure.py modules/config/drawio_shape_map_gcp.py` to format all new/modified files
- [x] T026 [US1] Run `poetry run pytest tests/test_drawio_emitter.py tests/test_xdot_parser.py -v` to validate all unit tests pass

**Checkpoint**: `terravision draw --format drawio` produces a valid `.drawio` file with native icons, edges, and clusters. All resources from PNG output appear in drawio output. This is the MVP.

---

## Phase 4: User Story 2 — HTML Labels and Embedded Images in Clusters (Priority: P1)

**Goal**: Cluster containers display HTML-table labels with embedded images — AWS corner icons, Azure/GCP cluster header images — that were previously dropped by `graphviz2drawio`.

**Independent Test**: Generate drawio from a Terraform project with VPCs/subnets. Open in draw.io, verify cluster containers show corner icons and formatted labels.

### Implementation for User Story 2

- [x] T027 [US2] Implement HTML label parser to extract image paths and text from DOT HTML-table labels (`<TABLE>...<IMG>...<TD>`) in modules/drawio_emitter.py
- [x] T028 [US2] Implement cluster label mxCell rendering — for nodes with `_clusterlabel="1"`, create separate image mxCell + text mxCell within the cluster, positioned at xdot coordinates in modules/drawio_emitter.py
- [x] T029 [US2] Handle the three label positions (`bottom-left`, `bottom-right`, `bottom-center`) from the `_labelposition` attribute for cluster label placement in modules/drawio_emitter.py
- [x] T030 [US2] For cluster label icons, check shape map for native draw.io equivalent; if none, embed as base64 PNG in modules/drawio_emitter.py
- [x] T031 [P] [US2] Write tests verifying cluster label rendering for AWS (corner icons), Azure (header images), and GCP (header images) in tests/test_drawio_emitter.py
- [x] T032 [US2] Run `poetry run black modules/drawio_emitter.py` and `poetry run pytest tests/test_drawio_emitter.py -v`

**Checkpoint**: Clusters in drawio output show provider-specific icons and labels for all three providers. Nested clusters (VPC > AZ > Subnet) render correctly.

---

## Phase 5: User Story 3 — Simplified Installation (Priority: P2)

**Goal**: Remove `graphviz2drawio` and `pygraphviz` dependencies so drawio export works out of the box without C-extension compilation.

**Independent Test**: In a clean Python environment, install TerraVision (without `[drawio]` extra), run `terravision draw --format drawio`, verify it succeeds.

### Implementation for User Story 3

- [x] T033 [US3] Remove `graphviz2drawio>=1.1.0; sys_platform == 'linux'` from `[project.dependencies]` in pyproject.toml
- [x] T034 [US3] Remove `[project.optional-dependencies] drawio` section from pyproject.toml
- [x] T035 [P] [US3] Remove `graphviz2drawio` from requirements.txt (if present)
- [x] T036 [US3] Run `poetry lock` to regenerate the lockfile without graphviz2drawio
- [x] T037 [US3] Run `poetry install` to verify clean installation without C-extension compilation
- [x] T038 [US3] Run `poetry run pytest -m "not slow" -v` to verify no existing tests break from dependency removal

**Checkpoint**: TerraVision installs cleanly without `pygraphviz`/`graphviz2drawio`. All existing tests pass. drawio export works from base installation.

---

## Phase 6: User Story 4 — Footer, Legend, and Label Positioning (Priority: P3)

**Goal**: Footer, flow legend table, and node labels are positioned correctly in drawio output — matching the PNG output — without post-processing XML fixups.

**Independent Test**: Generate drawio from a project with `terravision.yml` annotations (title) and `--ai-annotate` (legend). Open in draw.io, verify footer at bottom, legend in correct position, labels below icons.

### Implementation for User Story 4

- [x] T039 [US4] Verify that title node (`_titlenode`) is rendered at the xdot-provided position (top center, above cloud content) in the emitter output — add assertion test in tests/test_drawio_emitter.py
- [x] T040 [US4] Verify that footer node (`_footernode`) is rendered at the xdot-provided position (bottom of canvas) in the emitter output — add assertion test in tests/test_drawio_emitter.py
- [x] T041 [US4] Verify that legend node (`_legendnode`) is rendered at the xdot-provided position (beside footer) in the emitter output — add assertion test in tests/test_drawio_emitter.py
- [x] T042 [US4] Ensure node labels use `verticalLabelPosition=bottom;verticalAlign=top` in the mxCell style string so labels appear below icons in modules/drawio_emitter.py
- [x] T043 [US4] Run `poetry run black modules/drawio_emitter.py` and `poetry run pytest tests/test_drawio_emitter.py -v`

**Checkpoint**: Footer, legend, and title appear in correct positions in drawio output. Node labels are below icons.

---

## Phase 7: User Story 5 — Users Can Replace Shapes from draw.io Sidebar (Priority: P3)

**Goal**: Native draw.io shapes allow users to right-click and replace with sibling shapes from the provider library.

**Independent Test**: Open generated drawio in draw.io, select a resource node, verify shape picker shows related provider shapes.

### Implementation for User Story 5

- [x] T044 [US5] Verify shape mapping coverage — write a test that checks at least the top 50 most common resource types per provider have mappings in tests/test_drawio_emitter.py
- [x] T045 [P] [US5] Verify all mapped shape names follow `mxgraph.<provider>.*` naming convention and contain no duplicates in tests/test_drawio_emitter.py
- [x] T046 [US5] Run `poetry run pytest tests/test_drawio_emitter.py -v`

**Checkpoint**: Native shapes render in draw.io and integrate with draw.io's shape picker sidebar.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing, documentation, and final cleanup.

- [ ] T047 [P] Write integration test: full pipeline from Terraform source to `.drawio` file, verify valid XML output and node/edge counts in tests/test_drawio_integration.py
- [ ] T048 [P] Write integration test: compare resource count between PNG and drawio outputs for same Terraform input in tests/test_drawio_integration.py
- [ ] T049 [P] Write integration test: verify cluster hierarchy in drawio matches DOT structure in tests/test_drawio_integration.py
- [ ] T050 Update README.md to remove `[drawio]` installation instructions, CFLAGS/LDFLAGS workaround, and note native shape support
- [ ] T051 [P] Update docs/usage-guide.md to document improved drawio export with native shapes and simplified installation
- [x] T052 Run full test suite: `poetry run pytest -m "not slow" -v` to verify no regressions
- [x] T053 Run `poetry run black modules/ tests/` to ensure all files are formatted
- [ ] T054 Manual validation: generate drawio from a real Terraform project, open in draw.io desktop, verify visual correctness

**Checkpoint**: All tests pass, documentation updated, manual validation confirms correct output.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — review and reference gathering
- **Foundational (Phase 2)**: Depends on Setup — xdot parser must be complete before any emitter work
- **US1 (Phase 3)**: Depends on Foundational — core emitter + shape maps + integration
- **US2 (Phase 4)**: Depends on US1 — extends emitter with cluster label rendering
- **US3 (Phase 5)**: Depends on US1 — dependency removal after native emitter replaces graphviz2drawio
- **US4 (Phase 6)**: Depends on US1 — positioning verification/refinement
- **US5 (Phase 7)**: Depends on US1 — shape mapping coverage validation
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2) — no dependencies on other stories
- **US2 (P1)**: Depends on US1 — extends the emitter built in US1
- **US3 (P2)**: Depends on US1 — can only remove old dependency after native emitter works
- **US4 (P3)**: Depends on US1 — verifies positioning already implemented in US1
- **US5 (P3)**: Depends on US1 — validates shape coverage from US1

### Within Each User Story

- Shape maps (T018-T020) can be built in parallel with emitter core (T010-T017)
- Tests within a story marked [P] can run in parallel
- Run Black formatting after each story's implementation tasks

### Parallel Opportunities

- **Phase 2**: T008 (tests) can run in parallel with T003-T007 development (write tests alongside parser)
- **Phase 3**: T018, T019, T020 (shape maps) are fully parallel with each other and with T010-T017 (emitter core)
- **Phase 3**: T024 (emitter tests) can be written in parallel with shape map work
- **Phase 5**: T033-T035 (dependency removal) can run in parallel
- **Phase 8**: T047-T049 (integration tests) and T050-T051 (docs) are all parallel

---

## Parallel Example: User Story 1 (Core Emitter)

```bash
# Launch shape maps in parallel (different files, no dependencies):
Task: T018 "Create AWS shape mapping in modules/config/drawio_shape_map_aws.py"
Task: T019 "Create Azure shape mapping in modules/config/drawio_shape_map_azure.py"
Task: T020 "Create GCP shape mapping in modules/config/drawio_shape_map_gcp.py"

# Launch emitter tests in parallel with shape maps:
Task: T024 "Write unit tests in tests/test_drawio_emitter.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (review existing code)
2. Complete Phase 2: Foundational (xdot parser)
3. Complete Phase 3: User Story 1 (core emitter + shape maps + integration)
4. **STOP and VALIDATE**: Run `terravision draw --format drawio`, open in draw.io, verify
5. This is a deployable MVP — drawio export works with native icons

### Incremental Delivery

1. Setup + Foundational → xdot parser ready
2. Add US1 → Core drawio generation works → **MVP!**
3. Add US2 → Cluster labels with icons render correctly
4. Add US3 → Dependency removed, clean installation
5. Add US4 → Positioning verified and refined
6. Add US5 → Shape coverage validated
7. Polish → Tests, docs, cleanup

### Single Developer Strategy (Recommended)

Given this is a single-developer project:
1. Phases 1-3 sequentially (Setup → Parser → Core Emitter)
2. Shape maps T018-T020 in quick succession (mechanical work)
3. Phase 4 (cluster labels) immediately after US1 validation
4. Phase 5 (dependency removal) — quick cleanup
5. Phases 6-7 are primarily validation/testing
6. Phase 8 wraps up with docs and final tests

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Always run `poetry run black <file>` after modifying any Python file
- Commit after each phase completion
- Stop at any checkpoint to validate independently
- Shape map files are the most mechanical/tedious work — consider building incrementally (top 50 first, expand later)
