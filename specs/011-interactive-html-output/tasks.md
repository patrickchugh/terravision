# Tasks: Interactive HTML Diagram Output

**Input**: Design documents from `/specs/011-interactive-html-output/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Vendor JS dependencies and create project structure for the HTML renderer

- [x] T001 Download and vendor d3.js (minified) as static asset in modules/vendor/. d3-graphviz and @hpcc-js/wasm-graphviz were abandoned (WASM fetch fails for file:// HTML).
- [x] T002 Create modules/html_renderer.py with module docstring and empty function stubs: render_html(), _embed_icons_as_base64(), _serialize_metadata(), _assemble_html()
- [x] T003 [P] Create modules/templates/interactive.html as a skeleton HTML template with placeholder sections for JS, CSS, DOT data, and metadata JSON

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Refactor DOT generation out of render_diagram() and wire up the new `visualise` CLI command. MUST complete before any user story work.

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Refactor modules/drawing.py to extract DOT generation into `generate_dot()` (returns DOT string, icon paths, node_id_map, cluster_id_map) and `generate_svg()` (calls generate_dot, renders to SVG via local Graphviz, replaces icon paths with base64 in SVG). Also snapshots `pre_draw_metadata` before drawing overwrites entries. Fixed `pretty_name()` bug where module name was used as label. `render_diagram()` was NOT modified to call `generate_dot()` — it retains its original implementation.
- [x] T005 Add the `visualise` Click command in terravision/terravision.py as a peer of `draw`. Wire it to call `compile_tfdata()`, optionally `simplify_graphdict()`, then `html_renderer.render_html()`. Include all flags from the CLI contract (--source, --workspace, --varfile, --outfile, --show, --simplified, --annotate, --planfile, --graphfile, --debug, --upgrade). Emit warnings for --format and --aibackend if provided. Run `poetry run black terravision/terravision.py`.
- [x] T006 Implement `_serialize_metadata()` in modules/html_renderer.py. Deep copies `pre_draw_metadata` (or `meta_data`), `original_metadata`, and `graphdict`. Removes non-serializable keys. Replaces boolean `True` values (known-after-apply) with "Computed (known after apply)" (with known boolean attribute exclusion list). Adds `_instance_info` for numbered resources. Builds `original_name_map` (reverse mapping for renames/consolidations). Builds `resource_siblings` from CONSOLIDATED_NODES config and shared type prefix grouping. Returns dict with keys: `metadata`, `original_metadata`, `graphdict`, `original_name_map`, `resource_siblings`. `node_id_map` and `cluster_id_map` are added by `render_html()` after serialization.

**Checkpoint**: `visualise` command is wired up, DOT generation is reusable, metadata is serializable. No HTML output yet.

---

## Phase 3: User Story 1 - Generate Interactive HTML Diagram (Priority: P1) MVP

**Goal**: `terravision visualise --source <path>` produces a self-contained HTML file that renders the architecture diagram in-browser with identical layout to PNG.

**Independent Test**: Run `poetry run terravision visualise --source tests/fixtures/terragrunt-multi`, open the resulting HTML file in a browser, verify all nodes, groups, and connections match the PNG output.

### Implementation for User Story 1

- [x] T007 [US1] Implement `_embed_icons_as_base64()` in modules/html_renderer.py. Accept the set of icon file paths from `generate_dot()` and the DOT string. Read each icon file, base64-encode it, replace the absolute file path in the DOT string with a `data:image/png;base64,...` data URI. Return the modified DOT string and a dict of {path: base64_data} for any icons that couldn't be inlined. Run `poetry run black modules/html_renderer.py`.
- [x] T008 [US1] Build the interactive.html template in modules/templates/interactive.html. Embed inline `<script>` tag for d3.js (read from modules/vendor/). Add `<div id="graph">` for pre-rendered SVG content and `<script>` for metadata JSON. No WASM or d3-graphviz — SVG is pre-rendered server-side. Template uses placeholder tokens ({{D3_JS}}, {{SVG_CONTENT}}, {{METADATA_JSON}}) replaced by _assemble_html().
- [x] T009 [US1] Implement `_assemble_html()` in modules/html_renderer.py. Read the interactive.html template. Replace placeholders with: vendored d3.js, pre-rendered SVG string (with base64 icons), and serialized metadata JSON. No WASM binary. Write the assembled HTML to the output file.
- [x] T010 [US1] Implement `render_html()` in modules/html_renderer.py as the main entry point. Orchestrate: call `drawing.generate_svg()` to get SVG string with embedded icons + node_id_map + cluster_id_map, call `_serialize_metadata()`, merge maps into metadata JSON, call `_assemble_html()`. Handle `--outfile` (append .html if needed), handle `--show` (use `webbrowser.open()` to open in default browser).
- [x] T011 [US1] End-to-end validation: run `poetry run terravision visualise --source tests/fixtures/terragrunt-multi --outfile test-output` and verify: (1) test-output.html exists, (2) file is self-contained (grep for no absolute file paths), (3) file opens in a browser and renders the diagram. Also test with `--annotate` flag using a sample annotations YAML to verify custom labels, added/removed nodes, and edge labels render correctly in HTML (FR-015). Fix any issues found.

**Checkpoint**: `terravision visualise` produces a working HTML file with the architecture diagram rendered via server-side Graphviz SVG. All nodes, groups, and connections visible. This is the MVP.

---

## Phase 4: User Story 2 - Click Resource Node to View Metadata Details (Priority: P2)

**Goal**: Clicking any resource node opens a slide-in sidebar showing the resource's Terraform metadata.

**Independent Test**: Open the HTML diagram, click an EC2 instance node, verify the detail panel shows instance_type, ami, tags, etc. Click a security group, verify ingress/egress rules are shown.

### Implementation for User Story 2

- [x] T012 [US2] Add detail panel CSS to modules/templates/interactive.html. Cyberpunk dark blue theme (#0a1628 background). 520px wide slide-in sidebar with TerraVision brand header (white "Terra" + gold "Vision"). Tabbed content (Attributes / Raw Plan). Styles for attribute table with copy/expand action buttons, related resources section (green Connected, blue Related Same Type), and pulsing node highlight animation.
- [x] T013 [US2] Add click handler JavaScript to modules/templates/interactive.html. Select all `.node` and `.cluster` SVG groups via d3, attach click event listeners. On click: extract node ID from SVG title element, look up Terraform address via node_id_map/cluster_id_map, populate detail panel with resource type, name, and attribute key-value pairs. Show both raw (original_metadata) and processed (metadata) tabs. Close panel on X button click, clicking the diagram background, or pressing Escape key. Add pulsing highlight to selected node.
- [x] T014 [US2] Implement synthetic vs real instance display logic in the detail panel JavaScript. For synthetic instances (_synthetic flag is true): show shared metadata once with a note "Instance N of M" (using _instance_info). For real count/for_each instances: show the individual instance's metadata. Display "Computed (known after apply)" for pre-replaced boolean True values.
- [x] T015 [US2] Handle edge cases in the detail panel: resources with no metadata (show resource type and name only with "No additional metadata available" message), resources with very long attribute values (copy-to-clipboard button + expand modal for full value), nested objects and arrays in metadata (render as formatted JSON blocks). Added `buildRelatedLinks()` to show Connected Resources (from graphdict edges) and Related Same Type (from resource_siblings) in the panel. Added `showNonDrawnResource()` for resources not on the diagram but present in original_metadata.

**Checkpoint**: Clicking any resource node or cluster group opens a detail panel with full metadata, copy/expand actions, and related resource navigation. Synthetic and real instances handled correctly.

---

## Phase 5: User Story 3 - Animated Data Flow on Connection Lines (Priority: P3)

**Goal**: Pulsing dots animate along edge paths in the direction of data flow.

**Independent Test**: Open the HTML diagram, verify dots move from source to destination on each directed edge. Toggle animations off and on.

### Implementation for User Story 3

- [ ] T016 [US3] Add edge animation JavaScript to modules/templates/interactive.html. Select all edge `<path>` elements in the pre-rendered SVG. For each edge, create a small SVG `<circle>` element. Use the embedded graphdict to determine source-to-target direction. Animate each circle along its path using `getPointAtLength()` with `requestAnimationFrame`. Loop the animation smoothly.
- [ ] T017 [US3] Handle bidirectional edges in the animation JavaScript. Detect bidirectional connections from graphdict (A→B and B→A both exist). For bidirectional edges, create two animated dots moving in opposite directions simultaneously.
- [ ] T018 [US3] Add animation toggle button to modules/templates/interactive.html. Place a toggle button in a toolbar/controls area (top-right or bottom-right). Default state: animations ON. Clicking pauses all dot animations (stop requestAnimationFrame loop, freeze dot positions). Clicking again resumes. Style the button with a play/pause icon or text label.

**Checkpoint**: All edges have animated flow dots. Bidirectional edges show dots in both directions. Toggle button pauses/resumes animations.

---

## Phase 6: User Story 4 - Pan, Zoom, and Navigate Large Diagrams (Priority: P4)

**Goal**: Users can zoom, pan, and fit-to-screen for navigating large diagrams.

**Independent Test**: Open the HTML diagram, verify scroll-to-zoom, click-drag-to-pan, and fit-to-screen button all work.

### Implementation for User Story 4

- [x] T019 [US4] Add pan and zoom JavaScript to modules/templates/interactive.html. Apply d3-zoom to the SVG container. Configure scroll-wheel zoom (centered on cursor), click-and-drag pan on the SVG background. Ensure zoom does not interfere with node click handlers (clicks on nodes trigger detail panel, not pan). Set reasonable min/max zoom bounds.
- [x] T020 [US4] Add fit-to-screen button to the controls toolbar in modules/templates/interactive.html. On click, calculate the SVG bounding box and apply a d3-zoom transform that fits the entire diagram within the viewport with padding. Style the button consistently with the animation toggle.

**Checkpoint**: Large diagrams are fully navigable. Pan, zoom, and fit-to-screen all functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, tests, and documentation

- [ ] T021 [P] Handle empty graph edge case in modules/html_renderer.py. If graphdict is empty (no resources), generate an HTML file with a meaningful message: "No resources found in Terraform plan. Ensure your source contains valid Terraform configuration." instead of an empty diagram.
- [ ] T022 [P] Add unit tests in tests/test_html_renderer.py: test _serialize_metadata() with known-after-apply values, synthetic instances, and empty metadata. Test _embed_icons_as_base64() with a sample DOT string and icon paths. Test render_html() produces a valid HTML file. Test --outfile appends .html extension.
- [ ] T023 [P] Add CLI command tests in tests/test_visualise_command.py: test that `visualise` command is registered and accepts all expected flags. Test warning output when --format or --aibackend is passed. Test --outfile produces correctly named file.
- [ ] T024 Update docs/USAGE_GUIDE.md to add a `terravision visualise` section with usage examples, flag reference, and sample output description.
- [ ] T025 Update docs/README.md to mention the `visualise` command in the commands section and add an example.
- [ ] T026 Manual validation of SC-006: run `poetry run terravision visualise` against a real-world Terraform project with 100+ resources. Open the HTML in a browser and verify pan/zoom interactions remain smooth without noticeable lag. Document results.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 (Phase 3) must complete before US2 (Phase 4), US3 (Phase 5), US4 (Phase 6)
  - US2, US3, US4 can proceed in parallel after US1 (they all build on the rendered HTML)
- **Polish (Phase 7)**: Can start after US1; some tasks parallelizable with US2-US4

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational only. All other stories depend on US1.
- **User Story 2 (P2)**: Depends on US1 (needs rendered SVG nodes to attach click handlers)
- **User Story 3 (P3)**: Depends on US1 (needs rendered SVG edge paths to animate)
- **User Story 4 (P4)**: Depends on US1 (needs rendered SVG to apply zoom/pan)
- **US2, US3, US4 are independent of each other** and can be done in parallel

### Within Each User Story

- Core rendering before interactions
- CSS/HTML structure before JavaScript behavior
- Basic functionality before edge case handling

### Parallel Opportunities

- T002 and T003 can run in parallel (Phase 1)
- T004, T005, T006 are sequential (Phase 2 — T005 depends on T004's refactored function)
- T007, T008 can start in parallel within US1 (different files)
- US2 (T012-T015), US3 (T016-T018), US4 (T019-T020) can all run in parallel after US1 completes
- T021, T022, T023 can all run in parallel (Phase 7)
- T024 and T025 can run in parallel (Phase 7)

---

## Parallel Example: After US1 Completes

```bash
# Launch US2, US3, and US4 in parallel (they modify the same template file
# but different sections — coordinate via clearly separated code regions):

# US2: Detail panel
Task: "Add detail panel CSS to modules/templates/interactive.html"
Task: "Add click handler JavaScript to modules/templates/interactive.html"

# US3: Edge animation
Task: "Add edge animation JavaScript to modules/templates/interactive.html"

# US4: Pan/zoom
Task: "Add pan and zoom JavaScript to modules/templates/interactive.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (vendor dependencies, create files)
2. Complete Phase 2: Foundational (refactor DOT generation, wire CLI command, metadata serializer)
3. Complete Phase 3: User Story 1 (icon embedding, HTML template, assembly, render_html)
4. **STOP and VALIDATE**: Run `poetry run terravision visualise --source <test-fixture>`, open HTML in browser
5. Deploy/demo if ready — a non-interactive but correctly rendered HTML diagram is already valuable

### Incremental Delivery

1. Setup + Foundational → Skeleton ready
2. Add User Story 1 → Static HTML diagram (MVP!)
3. Add User Story 2 → Clickable metadata panels
4. Add User Story 3 → Animated edge flow
5. Add User Story 4 → Pan/zoom navigation
6. Polish → Tests, docs, edge cases

### Sequential Execution (Single Developer)

1. Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4) → Phase 7
2. Each phase checkpoint validates before proceeding

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- All Python files must be formatted with `poetry run black <file>` immediately after modification
- Run `poetry run pytest tests -m "not slow"` after each phase to check for regressions
- The interactive.html template is shared across US2/US3/US4 — if parallelizing, coordinate on clearly separated `<script>` and `<style>` sections
- Commit after each completed phase or logical task group

## Implementation Notes (Post-Build)

### Completed (beyond original tasks)
- **pretty_name() bug fix**: Module name was incorrectly used as the display label for resources in modules; fixed in drawing.py
- **Cluster/group click support**: VPCs, subnets, security groups are clickable via cluster_id_map
- **Related resources navigation**: Connected Resources (from graphdict) and Related Same Type (from resource_siblings/CONSOLIDATED_NODES) shown in detail panel
- **Cyberpunk dark blue theme**: Detail panel styled with dark blue background (#0a1628), cyan accents (#00d4ff), gold brand text
- **Copy-to-clipboard + expand modal**: Action buttons on every attribute value in the detail panel
- **Escape key closes panel**: Keyboard shortcut support
- **Node pulsing highlight**: CSS animation with scale + drop-shadow glow on selected node
- **pre_draw_metadata snapshot**: Deep copy of meta_data taken before drawing overwrites entries
- **original_name_map**: Reverse mapping for resource renames/consolidations
- **resource_siblings**: Auto-computed from CONSOLIDATED_NODES config and shared type prefixes
- **Non-drawn resource display**: showNonDrawnResource() handles resources in metadata but not on diagram

### Status Summary
- **Phase 1 (Setup)**: COMPLETE
- **Phase 2 (Foundational)**: COMPLETE
- **Phase 3 (US1 - HTML Diagram)**: COMPLETE
- **Phase 4 (US2 - Detail Panel)**: COMPLETE (with enhancements beyond spec)
- **Phase 5 (US3 - Edge Animation)**: PENDING (T016-T018)
- **Phase 6 (US4 - Pan/Zoom)**: COMPLETE (T019-T020)
- **Phase 7 (Polish)**: PENDING (T021-T026)
