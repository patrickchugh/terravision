# Implementation Summary: Interactive HTML Diagram Output

**Branch**: `011-interactive-html-output`  
**Status**: Complete  
**Total**: 3 commits, 20 files changed, ~3,750 insertions

This document captures the actual implementation as built, including architectural pivots made during development that diverged from the original plan.

## Feature Overview

A new `terravision visualise` CLI command that generates self-contained interactive HTML diagrams from Terraform code. The same Graphviz layout as PNG output, plus clickable resource nodes, metadata sidebar, search, related-resources navigation, on-demand edge flow animation, and pan/zoom — all in a single HTML file that works fully offline.

## Architectural Pivots from Original Plan

The original `research.md` and `plan.md` proposed using **d3-graphviz** with WebAssembly (WASM) Graphviz running in the browser. This approach was abandoned during implementation:

### What was tried first
- Vendor `d3.js`, `d3-graphviz`, and `@hpcc-js/wasm-graphviz`
- Pass the DOT graph string to d3-graphviz in the browser
- Let WASM Graphviz render it client-side

### Why it failed
- d3-graphviz's UMD build references `graphvizlib.wasm` externally and tries to fetch it at runtime
- For a self-contained HTML file opened via `file://`, there is no server to fetch from — Chrome blocks the request
- The `@hpcc-js/wasm-graphviz` module format doesn't work cleanly as a `<script>` tag inline
- Result: blank grey rectangles where the diagram should be

### What we actually built
- **Server-side SVG rendering** using the local Graphviz installation (already a TerraVision dependency)
- Render DOT → SVG via Python's `graphviz` library
- Replace icon file paths with base64 data URIs **after** SVG rendering (Graphviz can't handle base64 in image attributes during layout)
- Embed the SVG directly into the HTML template
- Use `d3.js` only for interactivity (zoom/pan, click handlers, selection)
- **Result**: smaller files (~500KB-1.5MB instead of 2-3MB), no WASM, identical layout to PNG, works perfectly offline

The vendored `d3-graphviz` and `@hpcc-js/wasm-graphviz` files were deleted; only `d3.min.js` (273KB) remains.

---

## File-by-File Changes

### Implementation Files

#### `terravision/terravision.py` (+126 lines)
Adds the new `visualise` Click command alongside `draw` and `graphdata`. Wires it to call `compile_tfdata()` (shared with `draw`), optionally `simplify_graphdict()`, then `html_renderer.render_html()`. Accepts the same flags as `draw` (`--source`, `--workspace`, `--varfile`, `--outfile`, `--show`, `--simplified`, `--annotate`, `--planfile`, `--graphfile`, `--debug`, `--upgrade`). Emits a warning if `--format` or `--aibackend` are passed (not applicable to HTML output). Registers the command in `main()`'s default_map.

#### `modules/html_renderer.py` (+533 lines, NEW)
The core HTML generation module. Main components:

- **`render_html()`** — entry point that orchestrates SVG generation, metadata serialization, and HTML assembly. Handles empty graphs and `--show` browser auto-open
- **`_serialize_metadata()`** — builds the JSON payload embedded in the HTML containing `metadata`, `original_metadata`, `graphdict`, `node_id_map`, `cluster_id_map`, `original_name_map`, and `resource_siblings`
- **`_clean_metadata_dict()` / `_normalize_value()` / `_clean_string_value()`** — normalize Terraform plan attributes for display:
  - Parse Python repr strings back to dicts/lists (so `"[{'type': 'forward'}]"` becomes a real array, pretty-printed as JSON in the UI)
  - Decode base64 + gzip user_data fields back to readable cloud-init/script content
  - Strip `${...}` Terraform expression wrappers using existing `helpers.remove_terraform_functions()`
  - Replace `"UNKNOWN"` markers (left when interpreter can't resolve a variable) — see Note below
  - Unwrap surrounding quotes and trailing whitespace from interpreter artifacts
- **`_get_instance_info()`** — extracts instance numbering for numbered resources, correctly handling both `~N` suffix and `[N]` indices in the base name
- **`_embed_icons_as_base64()`** — replaces icon file paths in SVG with base64 data URIs for self-containment
- **`_assemble_html()`** — merges template + d3.js + SVG + metadata JSON into the final output file
- **`_write_empty_diagram()`** — produces a friendly empty-state HTML when no resources exist
- **`_try_decode_base64()`** — handles base64 + gzip decoding for cloud-init user_data, with proper padding correction
- Sibling discovery uses `CONSOLIDATED_NODES` config (from `cloud_config_aws.py`) AND prefix-matching within module scope (so `aws_route_table`, `aws_route_table_association`, `aws_route` are automatically grouped because they share a prefix)

> **Note on "UNKNOWN" markers**: These are left by the variable interpreter when a variable can't be resolved. The current implementation cosmetically replaces `"UNKNOWN"` with `<unknown>` in display. This is a UX trade-off — `"UNKNOWN"` is more explicit about *why* the value is missing, while `<unknown>` is cleaner. May be revisited based on user feedback.

#### `modules/templates/interactive.html` (+1,361 lines, NEW)
The HTML template with embedded CSS and JavaScript. Cyberpunk dark blue theme. Key features:

- **Pre-rendered SVG** is embedded directly (rendered server-side via local Graphviz, no WASM in browser)
- **Detail panel** — slide-in sidebar with cyberpunk theme (dark navy `#0a1628` with cyan `#00d4ff` accents and yellow brand "Vision"), TerraVision brand header with close button, "Plan Attributes" / "Enriched" tabs, copy-to-clipboard and expand-to-modal buttons on each field, instance count badges
- **Empty/computed field hiding** — `null`, `""`, `[]`, `{}`, and "Computed (known after apply)" hidden by default with a "Show N empty/computed fields" toggle
- **Click handlers** for both resource nodes and group containers (VPCs, subnets, security groups). Group containers were added late in development based on user feedback
- **Pan/zoom** via d3-zoom with `+`/`−`/`Fit` toolbar buttons
- **Search box** to find resources by name with live filtering and click-to-jump
- **Pulsing yellow glow highlight** on the selected node (using CSS drop-shadow filter + scale animation)
- **Edge flow animation** — on-demand only:
  - Default state: clean, static diagram (no ambient animation)
  - Click a resource → cyan flowing line segments trace its connected edges using `stroke-dasharray` + animated `stroke-dashoffset`
  - **Bidirectional edges** get TWO flow trails moving in opposite directions
  - Navy blue (`#1a3a8a`) bold underlay (2.5px) on connected edges so they stand out where lines cross
  - Toolbar `▶` button toggles "animate all edges always" mode for users who want ambient effect
  - This was a major UX iteration — initially it was always-on dots which looked like "ants running around" on complex diagrams
- **Related resources** section with two groups:
  - **"Connected Resources"** (green chips) — direct graph edges, navigates to next resource
  - **"Related (Same Type)"** (blue chips) — sibling resources from `CONSOLIDATED_NODES` config + prefix-matching, lets users see consolidated/non-drawn resources like the actual route tables when clicking a route table association
- **Diagram title** displayed top-left from annotations
- **Escape key** closes the panel/modal
- **Expand modal** for viewing long field values

#### `modules/vendor/d3.min.js` (273KB, NEW)
Vendored d3.js v7. Only client-side JS dependency. Originally we vendored d3-graphviz and @hpcc-js/wasm-graphviz too, but those were deleted after the WASM approach was abandoned.

#### `modules/drawing.py` (+299 lines, mostly additions)
Refactored to support HTML output without breaking the existing `draw` command:

- **`generate_dot()`** — new function extracted from `render_diagram()`. Builds the complete DOT graph (nodes, clusters, edges, footer), runs the gvpr label positioning script, and returns the post-processed DOT string plus `node_id_map` (Graphviz UUID → Terraform address) and `cluster_id_map` (cluster Graphviz ID → Terraform address). Also snapshots metadata into `tfdata["pre_draw_metadata"]` BEFORE drawing overwrites entries with `{"node": newNode}` placeholders
- **`generate_svg()`** — new function that calls `generate_dot()`, renders the DOT to SVG using local Graphviz, then post-processes the SVG to replace icon file paths with base64 data URIs
- **`render_diagram()`** — unchanged behavior, still produces PNG/SVG/PDF output
- **`handle_group()`** — added 4 lines to populate `tfdata["cluster_id_map"]` so the HTML renderer can map clicked clusters back to Terraform resources

#### `modules/graphmaker.py` (+5 lines)
Tracks resource renames during consolidation in `tfdata["resource_name_map"]` (new name → original name). Used by `html_renderer._serialize_metadata()` to build the `original_name_map` so the HTML can find original metadata for resources that got renamed during graph enrichment (e.g., `aws_rds_aurora_mysql.this` was originally `aws_rds_cluster.this`).

#### `modules/helpers.py` (+21 lines, BUG FIX)
Fixed a pre-existing `pretty_name()` bug discovered during HTML implementation: `module.vpc.aws_nat_gateway.this[0]~1` was being labeled "VPC" because the function used the innermost module name (`vpc`) as the label whenever the instance name was a placeholder (`this`). Now only uses module name as label for genuinely generic resource types (`lambda_function`, `instance`, `function`, `bucket`, etc.) where the module name adds meaningful context. **This fix benefits both PNG and HTML outputs** — the bug had been present in PNG renders all along.

---

### Tests (NEW, 31 tests)

#### `tests/test_html_renderer.py` (+228 lines)
25 unit tests across 7 test classes:
- `TestCleanMetadataDict` — node key stripping, internal markers, known-after-apply replacement, real boolean preservation
- `TestCleanStringValue` — quote stripping, Terraform expression unwrapping, UNKNOWN marker replacement, whitespace handling
- `TestNormalizeValue` — Python repr parsing for lists/dicts, passthrough for real types
- `TestTryDecodeBase64` — plain base64, gzip+base64, binary detection, missing padding
- `TestGetInstanceInfo` — non-numbered resources, numbered with `~N`, numbered with `[N]` index
- `TestEmbedIconsAsBase64` — real icon embedding, missing file handling
- `TestSerializeMetadata` — required fields, pre_draw_metadata fallback, JSON serializability

#### `tests/test_visualise_command.py` (+113 lines)
6 CLI tests:
- Command registration in CLI group
- `--help` runs without error
- All expected flags listed in help output
- `--format` warning when passed
- `--aibackend` warning when passed
- `.html` extension auto-appended to outfile

**Test count**: 378 total (up from 347 before this branch).

---

### Documentation

#### `docs/USAGE_GUIDE.md` (+56 lines)
New `terravision visualise` section with command syntax, full options table, interactive features list, and six usage examples covering basic, custom outfile, browser auto-open, planfile mode, simplified mode, and debug replay.

#### `docs/README.md` (+21 lines)
New "Generate Interactive HTML Diagram" section with three example commands and a feature summary, linking to USAGE_GUIDE.md.

#### `CLAUDE.md` (+29 lines, NEW at repo root)
Auto-generated by `update-agent-context.sh` during planning. Contains tech stack notes for future Claude sessions.

---

### Specification Artifacts (NEW, in `specs/011-interactive-html-output/`)

| File | Purpose |
| ---- | ------- |
| `spec.md` | Feature specification with 4 prioritized user stories, 23 functional requirements, edge cases, success criteria, assumptions, and rendering approach decision. Contains a Clarifications section with implementation decisions made during the build. |
| `plan.md` | Implementation plan with technical context, constitution check (against `docs/constitution.md` v1.5.0), project structure, and 7 key design decisions (D1-D7). |
| `research.md` | 7 research items including the rendering engine selection (chose SVG post-processing after d3-graphviz failed). |
| `data-model.md` | Entity definitions for `HTMLDiagramData`, `ResourceMetadata`, `ConnectionEdge`, plus state transitions and data volume estimates. |
| `contracts/cli-contract.md` | Full CLI contract for `terravision visualise`. |
| `quickstart.md` | Quick-start guide with architecture diagram and file structure. |
| `tasks.md` | 26 implementation tasks across 7 phases, all marked complete. |
| `checklists/requirements.md` | Spec quality checklist used to validate the spec before implementation. |
| `IMPLEMENTATION_SUMMARY.md` | This file. |

---

## Architecture Diagram

```
terravision visualise --source ./terraform
        │
        ├── compile_tfdata()              ← Shared with `draw`
        │   ├── tf_initplan()
        │   ├── tf_makegraph()
        │   ├── read_tfsource()
        │   └── _enrich_graph_data()
        │
        ├── simplify_graphdict()          ← If --simplified
        │
        └── html_renderer.render_html()   ← NEW
            ├── drawing.generate_svg()    ← NEW
            │   ├── drawing.generate_dot()  ← NEW (extracted from render_diagram)
            │   │   - builds DOT graph via existing Canvas/Node/Cluster classes
            │   │   - runs gvpr label positioning script
            │   │   - extracts node_id_map and cluster_id_map
            │   │   - snapshots pre_draw_metadata
            │   ├── Render DOT → SVG via local Graphviz (neato)
            │   └── Replace icon paths with base64 data URIs in SVG
            ├── _serialize_metadata()    ← Build embedded JSON payload
            │   - metadata (from pre_draw_metadata snapshot)
            │   - original_metadata (raw Terraform plan data)
            │   - graphdict (for related resources navigation)
            │   - node_id_map / cluster_id_map / original_name_map
            │   - resource_siblings (from CONSOLIDATED_NODES + prefix matching)
            └── _assemble_html()          ← Merge template + d3.js + SVG + JSON
                Result: single self-contained .html file (~500KB-1.5MB)
```

## Notable UX Iterations During Build

These features evolved significantly based on user testing during development:

1. **Edge animation** — went through 4 iterations:
   - v1: Always-on cyan dots (looked like ants on complex diagrams)
   - v2: Always-on with toggle to disable
   - v3: On-demand only — animate edges connected to selected node
   - v4: Added bold navy underlay on connected edges so they stand out where lines cross

2. **Node highlight** — went through 5 iterations:
   - v1: Blue outline (too subtle)
   - v2: Yellow rectangle overlay (looked tacky)
   - v3: Yellow circle overlay (too transparent)
   - v4: Pulsing icon scale (subtle but invisible on busy backgrounds)
   - v5: Pulsing scale + drop-shadow yellow glow (final, naturally soft)

3. **Detail panel data** — major refactor:
   - Initial: showed `meta_data` directly (mostly empty for drawn resources because drawing.py overwrites it with `{"node": newNode}`)
   - Fixed by snapshotting metadata BEFORE drawing into `pre_draw_metadata`
   - Then added `original_name_map` to handle resources renamed during consolidation
   - Then added attribute value cleaning (Python repr → JSON, base64 decode, expression stripping, quote unwrapping)
   - Then added empty/computed field hiding by default

4. **Related resources** — three approaches:
   - v1: Only graphdict edges (missed consolidated resources)
   - v2: Hardcoded type families (fragile, didn't cover all cases)
   - v3: `CONSOLIDATED_NODES` config + prefix matching within module scope (current — automatic and comprehensive)
