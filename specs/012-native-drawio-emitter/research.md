# Research: Native draw.io mxGraph Emitter

**Feature Branch**: `012-native-drawio-emitter`  
**Date**: 2026-04-16

## R1: xdot Output Format and Parsing Strategy

### Decision
Parse xdot output from `dot -Txdot` using regex on the plain-text xdot format (not xdot_json). The xdot format encodes node positions as `pos="x,y"`, cluster bounding boxes as `bb="x1,y1,x2,y2"`, edge splines as `pos="e,x,y s,x,y x,y x,y ..."`, and label positions as `lp="x,y"`.

### Rationale
- TerraVision already uses `dot -Txdot_json` in `tfwrapper.py:dot_file_to_graphdata()` (line 120), confirming the `dot` binary is available and the xdot output format is a known quantity.
- The plain-text xdot format is simpler to parse with regex than JSON for our needs — we only need positions, dimensions, and bounding boxes, not drawing commands.
- The gvpr post-processing script (`shiftLabel.gvpr`) already runs on the DOT file before we consume it, so all title/footer/legend/cluster-label positions are already correct in the post-processed DOT. We parse the **post-processed** DOT via `dot -Txdot` to get final coordinates.

### Alternatives Considered
- **xdot_json**: Richer but produces much larger output and includes drawing commands we don't need. Parsing overhead higher.
- **pydot/pygraphviz for parsing**: Adds dependency we're trying to remove. Regex is sufficient for position extraction.
- **graphviz Python library's `pipe()` with `-Txdot`**: Could work but subprocess call is simpler and consistent with existing `tfwrapper.py` pattern.

---

## R2: mxGraph XML Structure

### Decision
Emit mxGraph XML using Python's built-in `xml.etree.ElementTree` module. The structure follows draw.io's standard format:

```xml
<mxGraphModel>
  <root>
    <mxCell id="0"/>                          <!-- Root cell -->
    <mxCell id="1" parent="0"/>               <!-- Default parent -->
    <mxCell id="node_1" value="Label"         <!-- Resource node -->
            style="shape=mxgraph.aws4.lambda_function;..."
            vertex="1" parent="cluster_vpc">
      <mxGeometry x="100" y="200" width="60" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="edge_1" source="node_1" target="node_2"  <!-- Edge -->
            style="edgeStyle=orthogonalEdgeStyle;..."
            edge="1" parent="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
  </root>
</mxGraphModel>
```

### Rationale
- `xml.etree.ElementTree` is a Python stdlib module — no new dependencies.
- The mxGraph XML format is well-documented and stable across draw.io versions.
- Parent-child nesting via `parent=` attribute directly maps to our cluster hierarchy (`cluster_id_map`).

### Alternatives Considered
- **String concatenation**: Fragile, risks malformed XML with special characters.
- **lxml**: More powerful but adds a C-extension dependency — the exact problem we're solving.
- **Template-based (Jinja2)**: Overhead for what is fundamentally a tree construction problem.

---

## R3: Provider Shape Library Mapping Strategy

### Decision
Create per-provider mapping dictionaries that map TerraVision's internal resource type aliases (e.g., `aws_lambda_function`) to draw.io shape-library identifiers (e.g., `mxgraph.aws4.lambda_function`). Store these in `modules/config/drawio_shape_map_<provider>.py` files, following the existing provider-specific config pattern (CO-001).

Fallback chain:
1. Check provider shape map for native draw.io shape name
2. If no mapping, embed the PNG icon as base64 `data:image/png;base64,...` in the mxCell style

### Rationale
- draw.io's AWS4 library uses names like `mxgraph.aws4.<service>` which closely mirror Terraform resource type suffixes — many mappings are mechanical.
- Azure uses `mxgraph.azure.<category>.<service>` and GCP uses `mxgraph.gcp.<category>.<service>`.
- Separate config files per provider follow CO-001 and keep the mapping maintainable.
- Fallback to embedded PNG ensures 100% resource coverage even for unmapped types (FR-004).

### Alternatives Considered
- **Single mapping file for all providers**: Would violate CO-001 (provider isolation).
- **Dynamic name derivation (no lookup table)**: Too fragile — draw.io shape names don't always match Terraform names exactly.
- **External mapping file (JSON/YAML)**: Adds I/O overhead and another file format to maintain.

---

## R4: Cluster Rendering in mxGraph XML

### Decision
Render clusters as mxCells with `style="group"` and child cells referencing the cluster's ID via `parent=`. Cluster labels with HTML tables and embedded images will be rendered as separate child mxCells within the cluster, positioned at the coordinates from the xdot output.

For cluster corner icons (AWS) and header images (Azure/GCP):
- Parse the HTML-table label from the DOT source to extract the image path and text
- Create a small image mxCell at the top-left corner of the cluster bounding box
- Create a text mxCell beside it for the label text
- Both reference the cluster as parent

### Rationale
- draw.io's group model matches Graphviz's subgraph model — both use parent-child containment.
- The xdot output provides exact bounding box coordinates for each cluster via `bb=` attribute.
- Separating icon and text into distinct mxCells gives full control over positioning — the exact problem that `graphviz2drawio` failed to solve.

### Alternatives Considered
- **HTML labels in mxCell**: draw.io supports limited HTML in cell values, but embedded `<img>` with local paths doesn't work — we'd still need to convert to base64 or native shapes.
- **Single cell with formatted label**: Loses control over icon positioning within the cluster.

---

## R5: Edge Rendering Strategy

### Decision
Render edges as mxCells with `edge="1"`, using `source=` and `target=` attributes referencing node IDs. Edge routing will use draw.io's `edgeStyle=orthogonalEdgeStyle` for clean right-angle routing, matching the visual style of the PNG output. Edge labels (from annotations/flows) will be set as the mxCell `value=` attribute.

For bidirectional edges: use `startArrow=classic;endArrow=classic` in the style string.

### Rationale
- The xdot output provides edge spline control points, but draw.io re-routes edges automatically based on node positions — we don't need to transfer exact spline data.
- Orthogonal edge style matches the existing PNG diagram aesthetic.
- draw.io natively handles edge label positioning when `value=` is set.

### Alternatives Considered
- **Transfer exact spline coordinates**: Overly complex and brittle — coordinates would be in Graphviz space, requiring coordinate transformation. draw.io's auto-routing produces cleaner results.
- **Straight-line edges**: Less readable for complex architectures.

---

## R6: Coordinate System Transformation

### Decision
Graphviz uses a coordinate system with origin at bottom-left (y increases upward). draw.io uses origin at top-left (y increases downward). Transform coordinates by: `drawio_y = canvas_height - graphviz_y`, where `canvas_height` is derived from the graph's bounding box.

### Rationale
- This is a standard transformation well-documented in Graphviz literature.
- The graph bounding box (`bb=` on the root graph in xdot output) provides the canvas dimensions.

### Alternatives Considered
- **Negate all Y values**: Would place the graph at negative coordinates — draw.io handles this but produces confusing coordinate values.
- **Apply transform in gvpr**: Would complicate the existing gvpr script for no benefit.

---

## R7: Dependency Removal

### Decision
Remove `graphviz2drawio` from both `pyproject.toml` (main dependencies and `[drawio]` optional group) and `requirements.txt`. Remove the conditional import at the top of `drawing.py`. Remove the `[drawio]` extra from installation documentation.

### Rationale
- The native emitter replaces all functionality provided by `graphviz2drawio`.
- Removing the dependency eliminates the `pygraphviz` C-extension compilation issues on Apple Silicon and Windows.
- The `[drawio]` extra becomes unnecessary since drawio export will work with the base installation.

### Alternatives Considered
- **Keep as optional fallback**: Adds maintenance burden for two code paths with no benefit.
- **Deprecation period**: The existing drawio output has known quality issues (dropped cluster labels, footer positioning) — users will prefer the improved native output immediately.

---

## R8: Existing Code Reuse

### Decision
The new drawio emitter will:
- **Reuse**: All existing DOT generation (`render_diagram()`, `generate_dot()`, `handle_group()`, `handle_nodes()`), gvpr post-processing, and the `pre_render()` call.
- **Replace**: Only the `if format == "drawio":` block in `render_diagram()` and the `graphviz2drawio.convert()` call.
- **Remove**: The `_postprocess_drawio_xml()` function (if it exists) and the `graphviz2drawio` import.
- **Extract**: Icon path resolution logic (regex from `generate_dot()` lines 1040-1043) into a shared helper for reuse by both SVG embedding and drawio shape mapping.

### Rationale
- The DOT generation pipeline is battle-tested and produces correct graph structure. The native emitter only changes how the DOT is consumed for drawio output.
- Extracting icon path resolution follows the DRY principle and prevents divergence between SVG and drawio icon handling.
