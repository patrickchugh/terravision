# Feature Specification: Interactive HTML Diagram Output

**Feature Branch**: `011-interactive-html-output`  
**Created**: 2026-04-05  
**Status**: Draft  
**Input**: User description: "Generate interactive HTML diagrams as output via a new `visualise` command. Self-contained HTML file viewable in browser showing architecture diagram with clickable resource nodes displaying metadata details and animated pulsing dots on edges showing data flow direction."

## Clarifications

### Session 2026-04-05

- Q: Should `visualise` support the `--show` flag to auto-open HTML in the default browser? → A: Yes, include `--show` flag.
- Q: How should the detail panel handle numbered resource instances (e.g., `web~1`, `web~2`)? → A: Distinguish synthetic instances (show shared metadata once with instance count note) from real count/for_each instances (show each instance's individual metadata, as values may differ).
- Q: Should users be able to toggle edge animations on/off? → A: Yes, include a pause/resume toggle button. Animations on by default.

### Session 2026-04-05 (Implementation Decisions)

- **Rendering approach changed from d3-graphviz to SVG post-processing.** d3-graphviz's UMD build references `graphvizlib.wasm` externally and tries to fetch it at runtime via `fetch()`. This fails for self-contained `file://` HTML files (no server to serve the WASM). The `@hpcc-js/wasm-graphviz` ESM module format doesn't work as a simple `<script>` tag include. We now render DOT to SVG server-side using the local Graphviz installation and embed the pre-rendered SVG in the HTML. d3.js is still used for zoom/pan/interactivity.
- **Icon embedding happens in SVG, not DOT.** Graphviz cannot handle base64 data URIs in `image` attributes (the strings are too long and get corrupted). Icons are embedded as base64 data URIs after SVG rendering by replacing file paths in the SVG `<image>` elements.
- **`pre_draw_metadata` snapshot added.** The drawing pipeline overwrites `meta_data` entries with `{"node": nodeObj}` as it draws resources. A deep copy is taken before drawing begins and stored as `tfdata["pre_draw_metadata"]` so the HTML renderer can access the original metadata.
- **Related/sibling resources feature added.** The detail panel shows "Connected Resources" (from graphdict edges, green links) and "Related Same Type" (from shared type prefix or CONSOLIDATED_NODES config, blue links). Both sections are clickable for navigation.
- **Cyberpunk dark blue theme chosen** for the detail panel with TerraVision brand header (white "Terra" + gold "Vision").
- **Copy-to-clipboard and expand modal** added to attribute values in the detail panel.
- **Keyboard shortcut: Escape to close** the detail panel.
- **Cluster/group click support added.** Security groups, subnets, VPCs are clickable and show their metadata in the detail panel via `cluster_id_map`.
- **Node highlight effect:** pulsing CSS scale animation with drop-shadow glow when a node is selected.
- **`pretty_name()` bug fix:** Module name was incorrectly used as the display label; fixed to use the resource name portion instead.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Interactive HTML Diagram via Visualise Command (Priority: P1)

A cloud engineer runs `terravision visualise --source ./terraform` and receives a single self-contained HTML file. They open this file in any modern browser and see their cloud architecture diagram rendered with the same resource nodes, groupings (VPCs, subnets, availability zones), and connections as the existing PNG output from `terravision draw`. The diagram layout is identical to the static PNG because the same Graphviz engine renders the DOT to SVG server-side, and the SVG is embedded directly in the HTML file.

**Why this priority**: Without a rendered HTML diagram that matches the existing output, no other interactive features have value. This is the foundational capability.

**Independent Test**: Can be fully tested by running `terravision visualise --source <path>`, opening the resulting `.html` file in a browser, and verifying all resource nodes, groupings, and connections from the PNG output are present.

**Acceptance Scenarios**:

1. **Given** a Terraform project with valid `.tf` files, **When** the user runs `terravision visualise --source ./terraform`, **Then** a single `.html` file is created in the output directory.
2. **Given** the generated HTML file, **When** the user opens it in Chrome, Firefox, Safari, or Edge, **Then** the architecture diagram renders without errors and without requiring an internet connection.
3. **Given** the generated HTML file, **When** the user compares it to the PNG output of the same source, **Then** all resource nodes, group boundaries (VPCs, subnets, AZs), and connection lines are present with identical layout.
4. **Given** a Terraform project using any supported provider (AWS, GCP, Azure), **When** the user generates HTML output, **Then** the correct provider-specific icons are displayed for each resource.
5. **Given** the user runs `terravision visualise --source ./terraform --outfile my-diagram`, **Then** the output file is named `my-diagram.html`.

---

### User Story 2 - Click Resource Node to View Metadata Details (Priority: P2)

A cloud architect opens the HTML diagram and clicks on an EC2 instance node. A detail panel appears showing the instance's metadata: instance type, AMI, availability zone, tags, and other Terraform-plan attributes. They click on a security group and see the ingress/egress rules. They click on a route table and see the routes. Each resource type displays the relevant metadata attributes from the Terraform plan.

**Why this priority**: Metadata inspection is the primary interactive value — it transforms a static picture into an explorable documentation artifact. However, it depends on Story 1's rendering being complete first.

**Independent Test**: Can be tested by generating an HTML diagram, opening it, clicking on various resource types, and verifying the displayed metadata matches the Terraform plan output.

**Acceptance Scenarios**:

1. **Given** an HTML diagram is open in a browser, **When** the user clicks on any resource node, **Then** a detail panel appears showing that resource's metadata attributes.
2. **Given** the detail panel is open for a security group, **When** the user reads the panel content, **Then** the ingress and egress rules are listed with protocol, port range, and source/destination.
3. **Given** the detail panel is open for an EC2 instance, **When** the user reads the panel content, **Then** the instance type, AMI ID, availability zone, and tags are displayed.
4. **Given** a detail panel is open, **When** the user clicks elsewhere on the diagram or clicks a close button, **Then** the detail panel closes.
5. **Given** a resource with no metadata beyond its name and type, **When** the user clicks on it, **Then** the detail panel shows the resource type and name gracefully (no empty or broken panel).

---

### User Story 3 - Animated Data Flow on Connection Lines (Priority: P3)

A solutions architect opens the HTML diagram to present to their team. The connection lines between resources have small pulsing dots that animate in the direction of data flow — for example, from CloudFront toward S3 for a static website, or from an API Gateway toward a Lambda function. This makes the diagram more visually engaging and immediately communicates the directionality of relationships.

**Why this priority**: Animated flow indicators add visual polish and communication value but are not essential for the diagram to be useful. The diagram already shows arrow directions; animation enhances comprehension.

**Independent Test**: Can be tested by generating an HTML diagram with directional connections, opening it in a browser, and verifying that dots animate along edges in the correct direction.

**Acceptance Scenarios**:

1. **Given** an HTML diagram with directed connections (e.g., CloudFront to S3), **When** the user views the diagram, **Then** small dots pulse along the connection line from the source node toward the destination node.
2. **Given** a bidirectional connection between two resources, **When** the user views the diagram, **Then** dots animate in both directions simultaneously.
3. **Given** the animation is running, **When** the user observes the diagram over time, **Then** the animation loops smoothly without visual jitter or performance degradation.

---

### User Story 4 - Pan, Zoom, and Navigate Large Diagrams (Priority: P4)

A DevOps engineer opens an HTML diagram of a large infrastructure with 50+ resources. They can zoom in and out using mouse scroll or pinch gestures, pan the diagram by clicking and dragging, and use a minimap or fit-to-screen button to reset the view. This makes large diagrams navigable rather than overwhelming.

**Why this priority**: Large diagrams are unusable without navigation controls. This is critical for real-world adoption but is lower priority than the core rendering and metadata features.

**Independent Test**: Can be tested by generating an HTML diagram from a large Terraform project, opening it, and verifying zoom, pan, and fit-to-screen controls work.

**Acceptance Scenarios**:

1. **Given** an HTML diagram is open, **When** the user scrolls the mouse wheel, **Then** the diagram zooms in or out centered on the cursor position.
2. **Given** an HTML diagram is open, **When** the user clicks and drags on the background, **Then** the diagram pans in the direction of the drag.
3. **Given** a zoomed-in view, **When** the user clicks a "fit to screen" button, **Then** the diagram zooms and pans to show the entire architecture within the viewport.

---

### Edge Cases

- What happens when a resource has metadata attributes with very long values (e.g., large IAM policy documents)? The detail panel should handle overflow gracefully with scrolling or truncation.
- What happens when the Terraform plan contains resources with `(known after apply)` placeholder values? These should display as "Computed (known after apply)" rather than raw boolean `True`.
- What happens with an empty graph (no resources)? The HTML file should render a meaningful empty state message rather than a blank page.
- What happens when the diagram has circular references or self-referencing connections? The animation and rendering should handle these without infinite loops or visual artifacts.
- What happens when the user generates HTML from a pre-existing JSON debug file (`tfdata.json`)? The HTML output should work identically to generating from a live Terraform source.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a new `visualise` CLI command, separate from the existing `draw` command, that generates interactive HTML output.
- **FR-002**: The `visualise` command MUST accept the same `--source`, `--workspace`, `--varfile`, `--outfile`, `--annotate`, `--simplified`, `--planfile`, `--graphfile`, `--show`, `--debug`, and `--upgrade` flags as the `draw` command. The `--show` flag MUST auto-open the generated HTML file in the user's default browser.
- **FR-002a**: If the user passes `--format` or `--aibackend` to the `visualise` command, the system MUST print a warning that the flag is not applicable and continue execution (not fail).
- **FR-003**: System MUST generate a single self-contained HTML file with all styles, scripts, icons, and data embedded inline (no external dependencies).
- **FR-004**: The HTML output MUST render correctly in current versions of Chrome, Firefox, Safari, and Edge without requiring an internet connection.
- **FR-005**: The HTML diagram MUST display all resource nodes present in the equivalent PNG/SVG output, using provider-specific icons.
- **FR-006**: The HTML diagram MUST display group containers (VPCs, subnets, availability zones, resource groups) matching the hierarchical structure of the PNG output.
- **FR-007**: The HTML diagram MUST display directed connection lines between resources matching the edges in the graph data.
- **FR-008**: The diagram layout MUST be identical to the existing Graphviz output (achieved by rendering the DOT graph to SVG server-side using the same local Graphviz installation, then embedding the pre-rendered SVG in the HTML file).
- **FR-009**: Each resource node MUST be clickable, triggering a detail panel that displays the resource's metadata attributes from the Terraform plan.
- **FR-010**: The detail panel MUST display resource type, resource name, and all available metadata key-value pairs. For numbered resource instances, the detail panel MUST distinguish between two cases:
  - **Synthetic instances** (created by TerraVision for diagram clarity, e.g., a resource spanning multiple subnets): Show shared metadata once with a note indicating the total number of instances (e.g., "1 of 3 instances").
  - **Real count/for_each instances** (from actual Terraform `count` or `for_each` attributes): Show each instance's individual metadata, as values may differ between instances (e.g., different availability zones, subnet CIDRs, or tags).
- **FR-011**: Connection lines MUST have animated dots that pulse in the direction of the edge (from source to destination). The HTML diagram MUST include a toggle button to pause/resume edge animations. Animations MUST be enabled by default.
- **FR-012**: The HTML diagram MUST support pan (click-drag) and zoom (scroll wheel) interactions for navigating large diagrams.
- **FR-013**: The HTML diagram MUST include a "fit to screen" control to reset the viewport to show the full diagram.
- **FR-014**: The HTML output MUST work with all existing input modes: local Terraform directories, Git URLs, pre-generated JSON files, and `tfdata.json` debug files.
- **FR-015**: The HTML output MUST respect annotations (from `terravision.yml` or `--annotate` flag) including custom labels, added/removed nodes, and edge labels.
- **FR-016**: The `--outfile` flag MUST work with the `visualise` command, appending `.html` extension if not already present.
- **FR-017**: Resource icons MUST be embedded in the HTML file (e.g., as base64-encoded images or inline SVGs) so the file is fully self-contained.
- **FR-018**: Metadata values that are `(known after apply)` (represented as boolean `True` internally) MUST display as "Computed (known after apply)" in the detail panel.
- **FR-019**: The detail panel MUST show a "Related Resources" section listing connected resources (from graphdict edges) and related same-type resources (from CONSOLIDATED_NODES config and shared type prefixes). Each related resource MUST be clickable to navigate to its details.
- **FR-020**: The detail panel MUST provide copy-to-clipboard buttons on attribute values and an expand modal for viewing long values.
- **FR-021**: The Escape key MUST close the detail panel when it is open.
- **FR-022**: Group containers (VPCs, subnets, security groups) MUST be clickable to display their metadata in the detail panel.
- **FR-023**: The currently selected resource node MUST be visually highlighted with a pulsing animation and glow effect.

### Key Entities

- **Resource Node**: A visual representation of a Terraform resource. Has a type, name, icon, label, position, and associated metadata key-value pairs. Belongs to zero or one group container.
- **Group Container**: A visual boundary representing a logical grouping (VPC, subnet, availability zone). Contains one or more resource nodes or nested group containers.
- **Connection Edge**: A directed line between two resource nodes representing a dependency or data flow. Has a source, destination, optional label, and animation direction.
- **Detail Panel**: An overlay or sidebar that appears when a resource node is clicked. Displays the resource's metadata in a readable key-value format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can generate an interactive HTML diagram from any supported Terraform source in the same time it takes to generate a PNG (within 2x overhead maximum).
- **SC-002**: The generated HTML file opens and renders correctly in all four major browsers (Chrome, Firefox, Safari, Edge) on first attempt without errors.
- **SC-003**: 100% of resource nodes visible in the PNG output are also present and identifiable in the HTML output.
- **SC-004**: Users can click any resource node and see its metadata within 1 second of clicking.
- **SC-005**: The generated HTML file is fully functional offline — no network requests are made when viewing the diagram.
- **SC-006**: Users can navigate a diagram with 100+ resources smoothly using pan and zoom without noticeable lag.

## Assumptions

- Users have access to a modern browser (Chrome, Firefox, Safari, or Edge, released within the last 2 years) for viewing HTML output.
- The existing graph data structure (`graphdict`, `original_metadata`, `meta_data`) contains sufficient information to render the diagram and populate metadata panels — no additional Terraform queries are needed.
- The existing icon files in `resource_classes/` directories can be embedded in the HTML file (they are PNG/SVG files of reasonable size).
- The HTML diagram layout will be identical to the current Graphviz PNG output because the DOT graph is rendered to SVG server-side using the same local Graphviz installation (neato engine), then embedded in the HTML file.
- Mobile/tablet touch interaction is not required for v1 — desktop browser support is sufficient.
- The `--simplified` flag behavior applies to HTML output the same way it applies to other formats (fewer nodes in simplified mode).
- The animated pulsing dots follow the same edge direction as the arrows in the existing diagram output.
- The `visualise` command shares the same `compile_tfdata()` pipeline as the `draw` command — they diverge only at the final rendering step.
- The self-contained HTML file will be approximately 500KB-1.5MB (d3.js ~273KB + pre-rendered SVG + metadata JSON + base64 icons). No WASM module is needed.

## Rendering Approach Decision

The following rendering approaches were evaluated during specification:

| Approach | Layout Fidelity | Interactivity | Self-Contained | Base File Size |
| -------- | --------------- | ------------- | -------------- | -------------- |
| d3-graphviz | Identical — IS Graphviz via WASM | Click handlers via D3 selection, d3-zoom for pan/zoom | **No** (WASM fetch fails for file://) | ~2-3 MB |
| Viz.js / @viz-js/viz | Identical — also Graphviz WASM | Manual — renders SVG only, no D3 | Same WASM issue | ~2 MB |
| Cytoscape.js | Different layout engine | Excellent built-in | Yes | ~500 KB |
| **SVG post-processing (chosen)** | Identical — Python Graphviz | D3.js for zoom/pan/click | Yes | ~300 KB |

**Chosen approach: SVG post-processing with d3.js** because:

1. **d3-graphviz was attempted and failed.** Its UMD build references `graphvizlib.wasm` externally and tries to `fetch()` it at runtime. For self-contained `file://` HTML files, there is no server to serve the WASM binary. Inlining the WASM as base64 is not supported by the d3-graphviz initialization API. The `@hpcc-js/wasm-graphviz` ESM module cannot be loaded as a simple `<script>` tag.
2. SVG post-processing renders DOT to SVG server-side using the same local Graphviz `neato` engine, guaranteeing identical layout to PNG output.
3. d3.js (vendored, 273KB) provides d3-zoom for pan/zoom, d3-selection for click handlers on SVG nodes, and SVG animation capabilities.
4. The resulting HTML file is smaller (~500KB-1.5MB vs ~3-5MB with WASM) and loads instantly (no WASM compilation step).
5. Cytoscape.js was rejected because it uses a different layout engine with no DOT import.
6. The only tradeoff is that SVG is pre-rendered (not re-layoutable in-browser), which is acceptable since the layout should not change after generation.
