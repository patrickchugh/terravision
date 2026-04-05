# Research: Interactive HTML Diagram Output

**Date**: 2026-04-05  
**Feature**: 011-interactive-html-output

## R1: Rendering Engine Selection

**Decision**: SVG post-processing with d3.js for interactivity

**Originally planned**: d3-graphviz (using @hpcc-js/wasm-graphviz) for in-browser DOT rendering.

**Why d3-graphviz was abandoned**: d3-graphviz's UMD build (`d3-graphviz.js`) references `graphvizlib.wasm` externally and calls `fetch()` to load it at runtime. For self-contained `file://` HTML files, there is no server to serve the WASM binary, so the fetch fails. Attempting to inline the WASM as a base64 data URL is not supported by d3-graphviz's initialization API. The `@hpcc-js/wasm-graphviz` package uses ESM module format which cannot be loaded via a simple `<script>` tag in the HTML.

**Chosen approach**: Render DOT to SVG server-side using the local Graphviz installation (`neato` engine), then embed the pre-rendered SVG in the HTML file. d3.js (273KB, vendored) provides zoom/pan (d3-zoom), click handlers (d3-selection), and DOM manipulation for the detail panel.

**Alternatives considered**:
- **d3-graphviz**: Failed due to WASM loading issues described above.
- **Viz.js/@viz-js/viz**: Same WASM loading problem as d3-graphviz.
- **Cytoscape.js**: Different layout engine, no DOT import. Would require complete layout reimplementation and lose fidelity to current output.

## R2: DOT String Capture Point

**Decision**: Capture DOT from the post-processed `.dot` file (after gvpr label positioning), then render to SVG server-side

**Rationale**: The rendering pipeline in `drawing.py` has two DOT stages:
1. Pre-render DOT (`myDiagram.pre_render()`) — raw DOT from graphviz library
2. Post-processed DOT (after gvpr `shiftLabel.gvpr` script) — has corrected label positions

The new `generate_dot()` function captures the post-processed DOT, and `generate_svg()` renders it to SVG using `graphviz.Source` with the neato engine (neato_no_op=2). This ensures the HTML layout matches PNG exactly. Both functions also build `node_id_map` (Graphviz UUID to Terraform address) and `cluster_id_map` for JavaScript click handling.

**Important**: The gvpr script (`shiftLabel.gvpr`) requires the `gvpr` tool from the Graphviz installation. This is already a requirement for TerraVision, so no new dependency.

## R3: Icon Embedding Strategy

**Decision**: Replace absolute file paths with base64 data URIs in the SVG output (after rendering)

**Rationale**: Icons are referenced as absolute file paths in DOT node attributes (e.g., `image="/full/path/to/resource_images/aws/compute/lambda.png"`).

Two approaches were considered:
1. **Pre-process DOT string** — replace file paths with `data:image/png;base64,...` URIs before rendering
2. **Post-process SVG** — render DOT to SVG with original file paths, then replace `<image>` href attributes in the SVG

**Option 2 was chosen** because Graphviz cannot handle base64 data URIs in `image` attributes — the strings are too long and get corrupted during rendering. The `generate_svg()` function renders DOT with original file paths, then does string replacement on the SVG output to embed base64 data URIs.

**Icon size**: AWS icons are small PNG files (~5-20KB each). A diagram with 30 unique resource types adds ~300-600KB of base64 data. Total file size remains well under 2MB.

## R4: Data Embedding Strategy

**Decision**: Embed the following data structures from tfdata in the HTML file as a single JSON object (`TERRAVISION_DATA`):
1. **`metadata`** — sourced from `pre_draw_metadata` (snapshot taken before drawing overwrites entries with `{"node": ...}`), or falls back to `meta_data`
2. **`original_metadata`** — raw Terraform plan attributes before handler processing
3. **`graphdict`** — graph structure (node to connections list), for connected-node highlighting
4. **`node_id_map`** — Graphviz SVG node UUID to Terraform resource address (for click handling)
5. **`cluster_id_map`** — Graphviz cluster ID to Terraform resource address (for group click handling)
6. **`original_name_map`** — reverse mapping from current metadata keys to original_metadata keys (covers renames/consolidations/numbered instances)
7. **`resource_siblings`** — related resources from CONSOLIDATED_NODES config and shared type prefix grouping

**Rationale**: `pre_draw_metadata` was added because the drawing pipeline overwrites `meta_data[resource]` with `{"node": nodeObj}` as each resource is drawn. The snapshot preserves the original metadata for the HTML renderer. `node_id_map` and `cluster_id_map` allow JavaScript to translate SVG element IDs back to Terraform addresses for click handling. `original_name_map` handles the case where resources are renamed during consolidation (e.g., `aws_ecs_service.this` becomes `aws_ecs.this`). `resource_siblings` enables the "Related Resources" panel section.

Other tfdata sections were evaluated and excluded:
- `tf_resources_created` — change.actions always "create" due to forced local backend. Not useful.
- `all_resource` — HCL source attributes with unresolved expressions. Confusing for users.
- `original_graphdict`, `tfgraph`, `node_list` — derivable from graphdict or DOT. Redundant.

**Synthetic vs real instances**: The `original_metadata` preserves pre-processing state. Synthetic instances share the same base resource metadata. Real count/for_each instances have distinct entries with index suffixes. The metadata JSON includes `_instance_info` with `is_synthetic` flag.

## R5: Self-Contained HTML Bundle Strategy

**Decision**: Single HTML file with inline `<script>` and `<style>` tags containing all dependencies

**Rationale**: The HTML file embeds:
1. **d3.js** (~273KB minified) — only JS dependency
2. **Pre-rendered SVG** (variable, typically 50-200KB)
3. **Metadata JSON** (variable, typically 50-500KB)
4. **Icons** (base64-encoded in SVG, ~300-600KB for typical diagram)
5. **CSS styles** for detail panel, controls, layout (~10KB)
6. **JavaScript** for interactivity, zoom/pan, detail panel (~15KB)

**Total estimated file size**: 500KB-1.5MB for a typical diagram. No WASM module needed.

**Note**: The WASM approach (d3-graphviz / @hpcc-js/wasm-graphviz) was abandoned because the WASM binary cannot be loaded from an inline source in `file://` HTML. The server-side SVG rendering approach produces smaller files and loads faster.

## R6: Command Integration with Existing Pipeline

**Decision**: New `visualise` Click command sharing `compile_tfdata()`, with a new `render_html()` function

**Rationale**: The existing pipeline in `terravision.py`:
1. `compile_tfdata()` — shared, produces `tfdata` with `graphdict`, `meta_data`, etc.
2. `simplify_graphdict()` — shared, applies `--simplified` flag
3. `drawing.render_diagram()` — NOT shared, this is the Graphviz-specific rendering

The `visualise` command will:
1. Call `compile_tfdata()` (identical to `draw`)
2. Call `simplify_graphdict()` if `--simplified` (identical to `draw`)
3. Call a new `html_renderer.render_html()` function instead of `drawing.render_diagram()`

The new renderer will still need the DOT generation from `drawing.py` (node creation, clustering, edge drawing) but will diverge at the final output step. Two sub-approaches:
- **Option A**: Refactor `render_diagram()` to return DOT string, then HTML renderer consumes it
- **Option B**: HTML renderer calls `render_diagram()` internals up to DOT generation, then takes over

Option A is cleaner but requires modifying `render_diagram()`. Option B duplicates some code. The planning phase should determine the best refactoring approach.

## R7: `--show` Flag for HTML

**Decision**: Use `webbrowser.open()` from Python standard library

**Rationale**: Python's `webbrowser` module opens URLs in the default browser. For a local HTML file, `webbrowser.open(f"file://{absolute_path}")` works cross-platform (macOS, Linux, Windows). This is simpler than the current `--show` for PNG which relies on Graphviz's `view=True` parameter.
