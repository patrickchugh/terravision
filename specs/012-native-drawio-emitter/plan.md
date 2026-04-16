# Implementation Plan: Native draw.io mxGraph Emitter

**Branch**: `012-native-drawio-emitter` | **Date**: 2026-04-16 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/012-native-drawio-emitter/spec.md`

## Summary

Replace the `graphviz2drawio` library with a native mxGraph XML emitter that generates `.drawio` files directly from Graphviz's `-Txdot` layout output. The emitter uses draw.io's built-in provider shape libraries (AWS4, Azure, GCP) instead of embedded base64 PNG icons, eliminating the `pygraphviz` C-extension dependency and fixing known rendering issues (dropped cluster labels, mispositioned footer/legend, labels above icons).

## Technical Context

**Language/Version**: Python 3.11+ (per pyproject.toml)  
**Primary Dependencies**: Graphviz `dot` binary (already required), `xml.etree.ElementTree` (stdlib)  
**Storage**: File-based (`.drawio` XML output)  
**Testing**: pytest (existing framework), Black formatting (CI-enforced)  
**Target Platform**: macOS, Linux, Windows (cross-platform CLI)  
**Project Type**: CLI tool  
**Performance Goals**: drawio export should complete within same time as current `graphviz2drawio` path  
**Constraints**: No new external dependencies; must work with existing `dot` binary  
**Scale/Scope**: Handles 200+ resource diagrams (per QR-002)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code as Source of Truth** | PASS | No change — drawio output still generated from `terraform plan` data |
| **II. Client-Side Security & Privacy** | PASS | No cloud credentials, no external API calls. Removes a dependency. |
| **III. Docs as Code (DaC)** | PASS | `.drawio` files are version-controllable artifacts |
| **IV. Dynamic Parsing & Accuracy** | PASS | No change to parsing pipeline — only the rendering output changes |
| **V. Multi-Cloud & Provider Agnostic** | PASS | Shape maps for all three providers (AWS, Azure, GCP). Common emitter code is provider-agnostic per CO-003. Shape maps in `modules/config/` per CO-001. |
| **VI. Extensibility Through Annotations** | PASS | Annotations (title, labels, flows, legend) rendered correctly in drawio output |
| **VII. AI-Assisted Refinement** | PASS | AI-generated annotations render in drawio same as PNG |
| **CO-001** | PASS | Provider shape maps stored in `modules/config/drawio_shape_map_<provider>.py` |
| **CO-003** | PASS | Common modules (`drawing.py`, new `xdot_parser.py`, new `drawio_emitter.py`) contain no provider-specific logic |
| **TS-005** | PASS | Poetry used; all commands use `poetry run` prefix |
| **TS-006** | PASS | Black formatting enforced |
| **TS-007** | PASS | New tests will follow slow/non-slow marking convention |

**Post-Phase-1 Re-check**: All gates still pass. The design adds provider-specific shape mapping files in `modules/config/` (CO-001 compliant) and keeps common modules provider-agnostic (CO-003 compliant). No new external dependencies introduced.

## Project Structure

### Documentation (this feature)

```text
specs/012-native-drawio-emitter/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart
├── contracts/
│   └── cli-contract.md  # CLI interface contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
modules/
├── xdot_parser.py                          # NEW: Parse xdot output into structured data
├── drawio_emitter.py                       # NEW: Generate mxGraph XML from parsed data
├── drawing.py                              # MODIFIED: Replace drawio block, remove graphviz2drawio import
└── config/
    ├── drawio_shape_map_aws.py             # NEW: AWS resource type → draw.io shape mapping
    ├── drawio_shape_map_azure.py           # NEW: Azure resource type → draw.io shape mapping
    └── drawio_shape_map_gcp.py             # NEW: GCP resource type → draw.io shape mapping

tests/
├── test_xdot_parser.py                    # NEW: Unit tests for xdot parsing
├── test_drawio_emitter.py                 # NEW: Unit tests for mxGraph XML generation
└── test_drawio_integration.py             # NEW: Integration tests for full drawio pipeline
```

**Structure Decision**: New modules follow the existing flat structure in `modules/`. Provider-specific shape maps go in `modules/config/` per CO-001. No new directories needed beyond what exists.

## Complexity Tracking

No constitution violations to justify. All design choices align with existing patterns.

## Implementation Phases

### Phase 1: xdot Parser (`modules/xdot_parser.py`)

**Goal**: Parse `dot -Txdot` output into structured Python objects.

**What to build**:
- Function `parse_xdot(xdot_text: str) -> XdotGraph` that extracts:
  - Graph bounding box from `bb="x1,y1,x2,y2"` on the root graph
  - Node positions from `pos="x,y"`, dimensions from `width`/`height`, labels, image paths, and custom attributes (`_titlenode`, `_footernode`, `_legendnode`, `_clusterlabel`, `_edgenode`)
  - Cluster bounding boxes from `bb=` on subgraphs, with parent-child relationships
  - Edges with source/target node IDs, labels, and label positions
- Function `run_xdot(dot_file_path: str) -> str` that runs `dot -Txdot <file>` via subprocess and returns the raw output

**Key parsing patterns**:
- Nodes: `node_id [pos="x,y", width="w", height="h", image="path", label="text", ...];`
- Clusters: `subgraph cluster_name { bb="x1,y1,x2,y2"; ... }`
- Edges: `node_a -> node_b [label="text", lp="x,y", ...];`

**Dependencies**: None (stdlib `re`, `subprocess`)

**Tests**: `test_xdot_parser.py`
- Parse a known xdot string and verify all nodes/clusters/edges extracted
- Handle malformed input gracefully (missing `pos`, empty graph)
- Verify coordinate values are correctly parsed as floats

---

### Phase 2: mxGraph Emitter Core (`modules/drawio_emitter.py`)

**Goal**: Convert parsed xdot data into valid mxGraph XML.

**What to build**:
- Function `emit_drawio(xdot_graph: XdotGraph, shape_map: dict, icon_paths: set, node_id_map: dict, cluster_id_map: dict) -> str` that produces the complete XML string
- Coordinate transformation: `drawio_y = graph_bb_height - graphviz_y`
- Graphviz dimensions are in inches (72 DPI); convert to pixels: `px = inches * 72`
- mxCell generation for:
  - Root cells (id="0" and id="1")
  - Cluster containers (vertex with `style="group"`, geometry from cluster `bb`)
  - Resource nodes (vertex with shape style from mapping, geometry from node pos/width/height)
  - Edges (edge with source/target, orthogonal routing style)
  - Title, footer, legend nodes (special positioning from xdot)
  - Cluster label nodes (icon + text cells at cluster top-left)

**Style string construction**:
- Native shape: `shape=mxgraph.aws4.lambda_function;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor=#ED7100;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;pointerEvents=1;`
- Fallback PNG: `shape=image;verticalLabelPosition=bottom;labelBackgroundColor=default;verticalAlign=top;aspect=fixed;imageAspect=0;image=data:image/png;base64,<data>;`
- Cluster: `group;rounded=1;whiteSpace=wrap;html=1;fillColor=<color>;strokeColor=<border>;dashed=1;`
- Edge: `edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;`
- Bidirectional edge: add `startArrow=classic;startFill=1;` to edge style

**XML generation** using `xml.etree.ElementTree`:
```python
root = ET.Element("mxGraphModel")
root_elem = ET.SubElement(root, "root")
ET.SubElement(root_elem, "mxCell", id="0")
ET.SubElement(root_elem, "mxCell", id="1", parent="0")
# ... add all cells
return ET.tostring(root, encoding="unicode", xml_declaration=True)
```

**Tests**: `test_drawio_emitter.py`
- Verify output is valid XML (parses without error)
- Verify root cells (0, 1) present
- Verify node count matches input
- Verify cluster parent-child relationships
- Verify coordinate transformation (Y-flip)
- Verify special characters in labels are XML-escaped

---

### Phase 3: Provider Shape Library Mappings

**Goal**: Create lookup tables mapping TerraVision resource types to draw.io shape names.

**What to build**:

`modules/config/drawio_shape_map_aws.py`:
- Dict `DRAWIO_SHAPE_MAP_AWS` mapping ~100+ AWS resource types
- draw.io AWS4 library uses: `mxgraph.aws4.<service_name>`
- Example mappings:
  - `aws_lambda_function` → `mxgraph.aws4.lambda_function`
  - `aws_instance` → `mxgraph.aws4.ec2`
  - `aws_s3_bucket` → `mxgraph.aws4.s3`
  - `aws_rds_cluster` → `mxgraph.aws4.rds`
  - `aws_vpc` → `mxgraph.aws4.vpc`

`modules/config/drawio_shape_map_azure.py`:
- Dict `DRAWIO_SHAPE_MAP_AZURE` mapping ~80+ Azure resource types
- draw.io Azure library uses: `mxgraph.azure.<service_name>`

`modules/config/drawio_shape_map_gcp.py`:
- Dict `DRAWIO_SHAPE_MAP_GCP` mapping ~40+ GCP resource types
- draw.io GCP library uses: `mxgraph.gcp.<category>.<service_name>`

**Loader function** in `drawio_emitter.py`:
```python
def load_shape_map(provider: str) -> dict:
    """Load draw.io shape mapping for a provider."""
    # Dynamic import following CO-004 pattern
```

**Tests**: Verify all mapped shape names follow draw.io naming conventions

---

### Phase 4: Cluster Label and Corner Icon Rendering

**Goal**: Correctly render HTML-table cluster labels with embedded images.

**What to build**:
- Parse HTML labels from DOT source to extract image paths and text
- For each cluster with a label node (`_clusterlabel="1"`):
  - Create an image mxCell at the label node's xdot position (icon)
  - Create a text mxCell beside it (label text)
  - Both cells reference the cluster as parent
- Handle the three label positions: `bottom-left`, `bottom-right`, `bottom-center`
- For corner icons: check if the icon image has a draw.io shape equivalent; if so, use native shape; otherwise embed as base64

**Key**: The xdot output already contains the positioned label nodes (gvpr placed them). We just need to read those positions and create the corresponding mxCells.

---

### Phase 5: Integration into `drawing.py`

**Goal**: Replace the `graphviz2drawio` code path with the native emitter.

**Changes to `modules/drawing.py`**:

1. **Remove** the conditional import of `graphviz2drawio` (lines 26-28)
2. **Replace** the `if format == "drawio":` block (lines 1352-1373) with:
   ```python
   if format == "drawio":
       from modules.xdot_parser import run_xdot, parse_xdot
       from modules.drawio_emitter import emit_drawio, load_shape_map
       
       # Run xdot to get layout coordinates
       xdot_output = run_xdot(str(path_to_postdot))
       xdot_graph = parse_xdot(xdot_output)
       
       # Load provider shape mapping
       provider = get_primary_provider_or_default(tfdata)
       shape_map = load_shape_map(provider)
       
       # Emit mxGraph XML
       xml_content = emit_drawio(xdot_graph, shape_map, icon_paths, node_id_map, cluster_id_map)
       
       # Write output
       drawio_output = Path.cwd() / f"{outfile}.drawio"
       with open(drawio_output, "w", encoding="utf-8") as f:
           f.write(xml_content)
       click.echo(f"  Output file: {drawio_output}")
       
       # Auto-open if --show flag set
       if picshow:
           click.launch(str(drawio_output))
       
       # Clean up temp files
       os.remove(path_to_predot)
       os.remove(path_to_postdot)
   ```

3. **Fix `--show` for drawio**: Add `click.launch()` call (currently missing for drawio format)

---

### Phase 6: Dependency Cleanup

**Goal**: Remove `graphviz2drawio` and `pygraphviz` dependencies.

**Changes**:
1. `pyproject.toml`: Remove `graphviz2drawio>=1.1.0; sys_platform == 'linux'` from `[project.dependencies]` and remove `[project.optional-dependencies] drawio` section
2. `requirements.txt`: Remove `graphviz2drawio` line (if present)
3. `README.md`: Update installation instructions to remove `[drawio]` extra references and CFLAGS/LDFLAGS workaround documentation
4. `docs/usage-guide.md`: Update drawio export section if needed
5. Run `poetry lock` to regenerate lockfile

---

### Phase 7: Testing

**Goal**: Comprehensive test coverage for the new emitter.

**Unit tests** (`test_xdot_parser.py`):
- Parse nodes with all attribute types
- Parse clusters with bounding boxes and nesting
- Parse edges with labels and bidirectional markers
- Handle empty graph, malformed input, missing attributes
- Verify coordinate parsing precision

**Unit tests** (`test_drawio_emitter.py`):
- Valid XML output (parseable, well-formed)
- Correct root cell structure
- Node count matches input
- Cluster parent-child hierarchy preserved
- Coordinate transformation (Y-flip) correct
- XML escaping of special characters in labels
- Native shape style for mapped resources
- Fallback PNG style for unmapped resources
- Edge source/target references valid
- Bidirectional edge style correct
- Title/footer/legend node positioning

**Integration tests** (`test_drawio_integration.py`):
- Full pipeline from DOT file to `.drawio` output
- Output file opens without XML parsing errors
- All nodes from `graphdict` present in output
- All edges from `graphdict` present in output
- Cluster hierarchy matches DOT structure
- Compare node count between PNG and drawio outputs for same input

**Shape mapping tests**:
- All mapped shape names follow `mxgraph.<provider>.*` convention
- No duplicate mappings
- Coverage check: top 50 resource types per provider have mappings

---

### Phase 8: Documentation

**Goal**: Update user-facing documentation.

**Changes**:
- `README.md`: Remove `[drawio]` installation instructions, CFLAGS/LDFLAGS workaround
- `docs/usage-guide.md`: Update drawio section to note native shapes and simplified installation
- `docs/CLAUDE.md`: Add drawio emitter to architecture section if relevant
- `CHANGELOG.md` or release notes: Document the breaking change (dependency removal)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| xdot format differs between Graphviz versions | Low | Medium | Test with Graphviz 2.x, 8.x, 12.x; the pos/bb format has been stable for 15+ years |
| draw.io shape names change in future versions | Low | Low | Shape names in draw.io's AWS4/Azure/GCP libraries have been stable since their introduction |
| Complex HTML labels don't parse cleanly | Medium | Medium | Use regex to extract just image paths and text; don't try to fully parse HTML |
| Large diagrams (200+ resources) produce slow xdot parsing | Low | Low | xdot is a compact format; 200 resources is ~10KB of text, trivial to parse |
| Existing tests fail due to DOT format changes | None | None | DOT generation pipeline is unchanged; only the output format conversion changes |

## Dependencies Between Phases

```
Phase 1 (xdot parser) ──────────┐
                                 ├──→ Phase 2 (emitter core) ──→ Phase 5 (integration)
Phase 3 (shape maps) ───────────┘              │                        │
                                                │                        ├──→ Phase 6 (deps)
Phase 4 (cluster labels) ──────────────────────┘                        │
                                                                         ├──→ Phase 7 (tests)
                                                                         └──→ Phase 8 (docs)
```

Phases 1 and 3 can be developed in parallel. Phase 4 depends on Phase 2. Phases 6, 7, 8 can partially overlap after Phase 5.
