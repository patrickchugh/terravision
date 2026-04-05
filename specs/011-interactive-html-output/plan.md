# Implementation Plan: Interactive HTML Diagram Output

**Branch**: `011-interactive-html-output` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-interactive-html-output/spec.md`

## Summary

Add a new `terravision visualise` CLI command that generates a self-contained interactive HTML file from Terraform code. The HTML diagram is rendered server-side using the local Graphviz installation (same neato engine as PNG output), then embedded as SVG in the HTML. d3.js provides zoom/pan and click interactivity. Interactive features include clickable resource nodes showing Terraform metadata in a cyberpunk-themed sidebar, related/connected resource navigation, copy-to-clipboard on values, and pan/zoom navigation for large diagrams.

## Technical Context

**Language/Version**: Python 3.11+ (existing project)  
**Primary Dependencies**: Click (CLI), graphviz (Python), d3.js (vendored, 273KB, embedded in HTML output)  
**Storage**: File-based (single .html output file)  
**Testing**: pytest (existing), browser-based manual testing for HTML output  
**Target Platform**: macOS/Linux/Windows CLI → HTML viewable in Chrome/Firefox/Safari/Edge  
**Project Type**: CLI tool  
**Performance Goals**: HTML generation within 2x of PNG generation time; 100+ node diagrams render smoothly in browser  
**Constraints**: Self-contained HTML (no CDN/network), ~500KB-1.5MB typical file size, offline-capable  
**Scale/Scope**: Same scale as existing draw command (tested up to ~200 resources)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source: `docs/constitution.md` v1.5.0*

| Principle / Rule | Status | Notes |
| ---------------- | ------ | ----- |
| I. Code as Source of Truth | PASS | `visualise` consumes the same `compile_tfdata()` pipeline — diagrams generated from Terraform code |
| II. Client-Side Security & Privacy | PASS | All processing client-side. HTML file generated locally. No cloud credentials needed. SVG rendered server-side, interactivity runs in user's browser locally |
| III. Docs as Code (DaC) | PASS | HTML output is a file artifact — versionable, CI/CD-compatible, same as PNG/SVG |
| IV. Dynamic Parsing & Accuracy | PASS | Shares the same dynamic parsing pipeline as `draw` |
| V. Multi-Cloud & Provider Agnostic | PASS | Uses provider-specific icons via existing `_load_icon()` / config system. No provider-specific logic in `html_renderer.py` |
| VI. Extensibility Through Annotations | PASS | FR-015 requires annotation support via `--annotate` flag |
| VII. AI-Assisted Refinement | N/A | `--aibackend` explicitly excluded from `visualise` (being dropped from project) |
| CO-001 to CO-005: Provider isolation | PASS | New module `html_renderer.py` is provider-agnostic — consumes DOT + metadata, no provider-specific code |
| CO-005.1: No unnecessary handlers | N/A | Feature adds no resource handlers |
| QR-001: No deployed infra needed | PASS | Works from `terraform plan`, same as `draw` |
| QR-004: Debug mode | PASS | `--debug` flag supported, produces `tfdata.json` |
| TS-005: Poetry | PASS | All commands use `poetry run` prefix |
| TS-006: Black formatting | PASS | New Python files will be formatted with Black |
| TS-007: Pre-commit hooks | PASS | New tests will follow slow/non-slow marking conventions |

**Post-Phase 1 re-check**: All gates still pass. The new `html_renderer.py` module is provider-agnostic (CO-003 compliant). No common modules are modified with provider-specific logic. The `visualise` command is a new output format, which per constitution versioning policy (MINOR) is an acceptable addition.

## Project Structure

### Documentation (this feature)

```text
specs/011-interactive-html-output/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart guide
├── contracts/
│   └── cli-contract.md  # CLI command contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
terravision/
└── terravision.py           # Add new 'visualise' Click command

modules/
├── html_renderer.py         # NEW: HTML generation logic
│   ├── render_html()        # Main entry point
│   ├── _embed_icons_as_base64() # Icon path → base64 replacement
│   ├── _serialize_metadata() # Metadata + graphdict + siblings JSON serialization
│   └── _assemble_html()     # Template assembly with d3.js + SVG + metadata
├── drawing.py               # MODIFIED: added generate_dot() and generate_svg()
├── vendor/
│   └── d3.min.js            # Vendored d3.js (~273KB) — only JS dependency
└── templates/
    └── interactive.html     # NEW: HTML template with JS/CSS (cyberpunk theme)

tests/
├── test_html_renderer.py    # NEW: Unit tests for HTML renderer
└── test_visualise_command.py # NEW: CLI command tests
```

**Structure Decision**: Follows existing single-project layout. New module `html_renderer.py` is a peer of `drawing.py` — both are renderers consuming the same `tfdata` pipeline output. HTML template is in `modules/templates/` to keep it close to the renderer code. Only d3.js is vendored (no WASM files).

## Complexity Tracking

No constitution violations to justify.

## Key Design Decisions

### D1: DOT Reuse via Existing Drawing Pipeline

The `visualise` command reuses the DOT generation from `drawing.py` (Canvas, Node, Cluster classes, `render_diagram()` up through gvpr post-processing). Two new functions were extracted from `render_diagram()`:

1. **`generate_dot()`** — Builds the complete DOT graph (nodes, clusters, edges, footer), runs gvpr label positioning, and returns the post-processed DOT string, icon file paths, `node_id_map` (Graphviz UUID to Terraform address), and `cluster_id_map`. Also snapshots `pre_draw_metadata` before drawing overwrites entries.
2. **`generate_svg()`** — Calls `generate_dot()`, writes the DOT to a temp file, renders to SVG via `graphviz.Source` with neato engine, then replaces icon file paths with base64 data URIs in the SVG output.

The HTML renderer calls `generate_svg()` to get a fully rendered SVG with embedded icons, then wraps it in the HTML template. The existing `render_diagram()` was NOT modified to call `generate_dot()` — it retains its original implementation for backward compatibility.

**Note**: A `pretty_name()` bug was fixed during implementation where module names were incorrectly used as display labels for resources in modules.

### D2: JavaScript Dependencies Bundled as Static Assets

Only **d3.js (~273KB minified)** is vendored in `modules/vendor/`. d3-graphviz and @hpcc-js/wasm-graphviz were abandoned because the WASM loading approach fails for self-contained `file://` HTML files (d3-graphviz tries to `fetch()` the WASM binary at runtime, which fails without a server). The HTML renderer reads `d3.min.js` and inlines it into the HTML output.

### D3: Data Serialization

The following tfdata structures are embedded in the HTML as a single JSON object:
1. **`metadata`** — sourced from `pre_draw_metadata` (snapshot taken before drawing overwrites entries) or falls back to `meta_data`
2. **`original_metadata`** — raw Terraform plan attributes before handler processing
3. **`graphdict`** — graph structure for connected-node highlighting
4. **`node_id_map`** — mapping from Graphviz SVG node UUID to Terraform resource address
5. **`cluster_id_map`** — mapping from Graphviz cluster ID to Terraform resource address (for group click support)
6. **`original_name_map`** — reverse mapping from current metadata keys to original_metadata keys (covers renames/consolidations)
7. **`resource_siblings`** — mapping from resource names to related resources (from CONSOLIDATED_NODES config and shared type prefixes)

The detail panel shows both raw and processed metadata as tabs, letting users see both what Terraform plans and what TerraVision enriched.

The serializer:
1. Deep copies `pre_draw_metadata` (or `meta_data`) and `original_metadata`
2. Removes non-serializable keys (`node`, internal markers starting with `_` except `_synthetic` and `_data_source`)
3. Replaces boolean `True` values for `(known after apply)` attributes with the string `"Computed (known after apply)"` (with a list of known boolean attributes excluded)
4. Adds `_instance_info` for numbered resources
5. Builds `original_name_map` via resource_name_map, `~N` suffix stripping, and attribute content matching
6. Builds `resource_siblings` from CONSOLIDATED_NODES config and shared type prefix grouping
7. Includes `graphdict` as-is (already JSON-serializable)

### D4: Detail Panel UX

The detail panel is a slide-in sidebar (right side, 520px wide) with a **cyberpunk dark blue theme**:
- **Brand header**: "Terra" (white) + "Vision" (gold) with close button
- **Resource header**: Resource name in cyan, full Terraform address in monospace, instance badge for numbered resources
- **Tabbed content**: "Attributes" (processed metadata) and "Raw Plan" (original_metadata) tabs
- **Attribute table**: Key-value rows with copy-to-clipboard and expand modal buttons on each value
- **Related Resources section**: "Connected Resources" (green, from graphdict edges) and "Related Same Type" (blue, from resource_siblings). Clickable to navigate.
- **Close**: X button, clicking diagram background, or pressing Escape key
- Scrollable content area for resources with many attributes

### D5: Edge Animation Implementation (NOT YET IMPLEMENTED)

Edge animation is planned but not yet built. T016-T018 remain pending.

### D6: Node Highlight

When a resource node is clicked, it receives a **pulsing CSS animation** (`node-pulsing` class) with:
- `transform: scale(1.05)` pulse at 1.5s interval
- `drop-shadow` glow effect in cyan (`#00d4ff`)
- Previous highlight is removed when a new node is clicked or the panel is closed

### D7: Cluster/Group Click Support

Security groups, subnets, VPCs, and other group containers are clickable in the SVG. The implementation:
1. `cluster_id_map` maps Graphviz cluster IDs to Terraform resource addresses
2. d3.js attaches click handlers to `.cluster` SVG elements
3. On click, the cluster's Terraform address is looked up and its metadata displayed in the detail panel
4. The node map is merged with the cluster map so `openPanel()` works uniformly for both
