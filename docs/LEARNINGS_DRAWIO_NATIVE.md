# Learnings: Native draw.io Emitter (Issue #188)

**Date**: 2026-04-16
**Branch**: `012-native-drawio-emitter`
**Status**: Working MVP for AWS, needs refinement for Azure/GCP

## What We Built

Replaced the `graphviz2drawio` library (which required `pygraphviz` C-extension compilation) with a native mxGraph XML emitter that generates `.drawio` files directly from Graphviz layout data. The emitter uses draw.io's built-in AWS4/Azure/GCP shape libraries instead of embedded base64 PNG icons.

### Pipeline

```
graphdict → drawing.py → DOT file → gvpr post-processing → post.dot
    → neato -n2 -Tjson0 (parse layout coords)
    → xdot_parser.py (structured Python objects)
    → drawio_emitter.py (mxGraph XML)
    → .drawio file
```

### New Files

| File | Purpose |
|------|---------|
| `modules/xdot_parser.py` | Parse Graphviz JSON layout output into XdotGraph/XdotNode/XdotCluster/XdotEdge dataclasses |
| `modules/drawio_emitter.py` | Generate mxGraph XML from parsed layout data with native draw.io shapes |
| `modules/config/drawio_shape_map_aws.py` | Terraform resource type → draw.io shape name mapping (AWS) |
| `modules/config/drawio_shape_map_azure.py` | Same for Azure |
| `modules/config/drawio_shape_map_gcp.py` | Same for GCP |
| `modules/config/drawio_aws4_shapes.py` | Authoritative AWS4 direct shape names + fill colors (from Sidebar-AWS4.js) |
| `modules/config/drawio_resicon_colors.py` | AWS4 resourceIcon fill colors by category (from Sidebar-AWS4.js) |
| `scripts/generate_drawio_shape_maps.py` | Auto-generate shape maps from draw.io GitHub repo |
| `tests/test_xdot_parser.py` | Unit tests for xdot parser |
| `tests/test_drawio_emitter.py` | Unit tests for drawio emitter |

### Modified Files

| File | Change |
|------|--------|
| `modules/drawing.py` | Replaced `graphviz2drawio` import and drawio export block with native emitter. Added `--show` support via `click.launch()`. Added `node_id_map` population in `handle_nodes()`. |
| `pyproject.toml` | Removed `graphviz2drawio` from dependencies and `[drawio]` optional group |
| `requirements.txt` | Removed `graphviz2drawio` |

---

## Key Learnings

### 1. draw.io Shape System Has Three Distinct Patterns

draw.io AWS4 shapes are NOT just `shape=mxgraph.aws4.<name>`. There are three patterns, each requiring different style attributes:

**a) Direct shapes** (590 shapes like `instance2`, `lambda_function`, `nat_gateway`):
```
shape=mxgraph.aws4.instance2;fillColor=#ED7100;strokeColor=none;...
```
- Monochrome SVG, coloured entirely by `fillColor`
- Size: 48x48 px
- `strokeColor=none`

**b) resourceIcon shapes** (373 shapes like `ec2`, `s3`, `identity_and_access_management`):
```
shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.ec2;fillColor=#ED7100;strokeColor=#ffffff;points=[[...]];...
```
- Coloured background box with inner icon
- Size: 78x78 px
- `strokeColor=#ffffff` (white border is essential)
- Requires `points=[[0,0,0],[0.25,0,0],...]]` for connection handles

**c) Group shapes** (15 shapes like `group_vpc2`, `group_security_group`):
```
shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=none;...
```
- Container shapes with corner icons
- Each has specific `strokeColor` and `fontColor` from AWS style guide

### 2. All draw.io Stencils Are Monochrome

Every draw.io stencil SVG is monochrome — the colour comes entirely from `fillColor` in the style string. Without `fillColor`, icons render as invisible outlines. The fill color is category-specific (orange `#ED7100` for compute, purple `#8C4FFF` for networking, red `#DD344C` for security, etc.).

### 3. Authoritative Source for Shape Names

The stencil XML file (`stencils/aws4.xml`) uses **spaces** in shape names (e.g., `"lambda function"`), but the runtime uses **underscores** (e.g., `lambda_function`). The stencil names and the sidebar JS names don't always match:

| Stencil XML name | Sidebar JS name | Pattern |
|-----------------|----------------|---------|
| `lambda function` | `lambda_function` | Direct shape |
| `ec2` | `ec2` | resourceIcon |
| `iam` | (doesn't exist) | Wrong name! |
| (doesn't exist) | `identity_and_access_management` | resourceIcon |
| `instance` | `instance2` | Different name! |

**The authoritative source is `Sidebar-AWS4.js`**, not the stencil XML. The sidebar JS defines:
- `var n = '...'` — base style for direct shapes
- `var n2 = '...'` — base style for resourceIcon shapes  
- `var n4 = '...'` — base style for group shapes
- Each shape entry with exact dimensions (`s * 48` for direct, `w2 = s * 78` for resourceIcon)

**Location**: `jgraph/drawio` repo → `src/main/webapp/js/diagramly/sidebar/Sidebar-AWS4.js`

### 4. draw.io XML Structure

A valid `.drawio` file requires:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="TerraVision" agent="TerraVision" version="1.0">
  <diagram id="terravision" name="Architecture">
    <mxGraphModel dx="1326" dy="798" grid="1" ...>
      <root>
        <mxCell id="0"/>                    <!-- Root cell -->
        <mxCell id="1" parent="0"/>         <!-- Default parent -->
        <!-- All other cells here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Without the `<mxfile><diagram>` wrapper, draw.io desktop may not open the file correctly.

### 5. Coordinate System: Absolute vs Relative

- **Graphviz**: Bottom-left origin, Y increases upward, units in points (1/72 inch)
- **draw.io**: Top-left origin, Y increases downward, units in pixels

Conversion: `drawio_y = graph_height - graphviz_y`

**Critical**: draw.io child cells use coordinates **relative to their immediate parent container**, not absolute. When a node is inside a subnet inside an AZ inside a VPC, its geometry `(x, y)` is relative to the subnet, not the canvas. Each nesting level subtracts only the immediate parent's absolute position.

### 6. Edge Waypoints from Graphviz

Graphviz computes exact edge spline paths in the `pos` attribute:
```
pos="e,2781.8,804 1582,1319 1582,1165 1582,804 1582,804 1582,804 2770.3,804"
```

These are Bezier control points. We extract them and pass as `<mxPoint>` waypoints in draw.io's edge geometry. This ensures edges follow the same paths as the PNG/SVG output.

Edge style uses `rounded=0` for straight orthogonal lines (not `rounded=1` which produces curves).

### 7. Node ID Mapping Challenge

TerraVision's Graphviz node IDs use the Python class format: `aws.compute.EC2Instance.uuid`. The terraform resource type (`aws_instance`) must be extracted to look up the draw.io shape. This requires either:
- `node_id_map` (populated during `handle_nodes()`) to get the terraform address
- Fallback: class-name-to-alias matching (e.g., `ElasticIP` → `aws_eip`)

Some abbreviations (`ElasticIP` vs `eip`) need a hardcoded `_CLASS_TO_ALIAS` map.

### 8. Shape Map Generation Strategy

The `scripts/generate_drawio_shape_maps.py` script:
1. Fetches the stencil XML from `jgraph/drawio` GitHub repo
2. Discovers all TerraVision resource class aliases via Python import introspection
3. Auto-matches by normalized name similarity (spaces/underscores stripped, lowercased)
4. Applies manual overrides for abbreviations and non-obvious mappings (LLM-assisted)
5. Writes the `modules/config/drawio_shape_map_*.py` files

Re-run with `poetry run python scripts/generate_drawio_shape_maps.py` when draw.io updates shapes.

Current coverage (terraform-style aliases only):
- AWS: 304/322 (94%)
- Azure: 156/160 (98%)  
- GCP: 191/227 (84%)

### 9. AWS Icon Style Evolution

AWS updated their architecture diagram style guidance — newer diagrams use border-only containers (no fill) for VPCs, subnets, and security groups. draw.io's AWS4 stencils follow this newer style. TerraVision's PNG output still uses the older filled style (defined in `resource_classes/aws/groups.py`). The drawio output correctly uses the newer border-only style.

### 10. GCP Stencil Limitations

draw.io's `gcp2` stencil library has not been updated to match Google's latest icon set. Many GCP resources will fall back to PNG embedding or generic shapes. This is a draw.io limitation.

---

### 11. Provider-Specific Node Card Styles

Each provider renders nodes differently in the PNG output. The draw.io emitter must replicate these card styles, not just place standalone icons.

**AWS**: Standalone icon with label below (no card). This is what we currently emit and it matches.

**Azure**: Grey rounded card with icon inside. From `resource_classes/azure/__init__.py`:
```
shape=box; style=rounded,filled; fillcolor=#F2F2F2; color=#E0E0E0;
penwidth=1; fontcolor=#2C2C2C; margin=0.4
```
In draw.io this would be a rounded rectangle cell (`rounded=1;fillColor=#F2F2F2;strokeColor=#E0E0E0`) containing or overlaying the SVG icon.

**GCP**: HTML table card — icon on left (100x100), two lines of text on right (service name bold, resource name regular). From `resource_classes/gcp/__init__.py`:
```html
<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="8" WIDTH="360">
  <TR>
    <TD FIXEDSIZE="TRUE" WIDTH="100" HEIGHT="100"><IMG SRC="icon.png"/></TD>
    <TD ALIGN="LEFT" VALIGN="MIDDLE">
      <FONT POINT-SIZE="24"><B>Service Name</B></FONT><BR/>
      <FONT POINT-SIZE="18">resource_name</FONT>
    </TD>
  </TR>
</TABLE>
```
In draw.io this would need a group cell containing an image cell + text cell side by side, or a single cell with HTML label.

---

## What Still Needs Work

1. **Shape map generator**: Update `scripts/generate_drawio_shape_maps.py` to fetch sidebar JS directly:
   - **AWS**: Fetch `Sidebar-AWS4.js` → extract `resIcon=` names and `n + 'shapename;'` direct shapes with their `fillColor` per section. AWS uses **stencil shapes** (`shape=mxgraph.aws4.<name>;fillColor=<color>`)
   - **Azure**: Fetch `Sidebar-Azure.js` → but Azure does NOT use stencils like AWS. Azure uses **SVG image paths** (`image=img/lib/azure2/<category>/<Name>.svg`). The generator must map terraform aliases to the correct `img/lib/azure2/` SVG path, not to `mxgraph.azure.*` stencil names.
   - **GCP**: draw.io hasn't updated GCP stencils (`gcp2` is outdated). GCP sidebar also uses `shape=image;image=...` SVG paths for most icons. Until draw.io updates, use PNG fallback from TerraVision's local icons.
2. **Corner icon visibility**: Cluster label icons (VNet, Subnet, Resource Group corner icons) are positioned at bottom of parent but can be obscured by child clusters. Z-order fix is in place (emitted last in XML) but positioning still needs refinement.
3. **Azure logo**: The "Microsoft Azure" group label image (`azure.png` → `Azure.svg`) renders as broken image at the very bottom of the diagram.
4. **Edge routing**: Some edges cross through containers instead of routing around them. Graphviz spline waypoints are passed but `edgeStyle=orthogonalEdgeStyle` in draw.io may override them.
5. **Integration tests**: Full pipeline tests comparing PNG vs drawio output for multiple test cases.
6. **Documentation updates**: README and usage guide need updating to remove `[drawio]` installation instructions.
7. **`_CLASS_TO_ALIAS` map**: The hardcoded class-name-to-terraform-alias fallback grows as we test more fixtures. Consider auto-generating it from the resource_classes package.

---

## Commands

```bash
# Generate drawio diagram
poetry run terravision draw --source <path> --format drawio --outfile <name>

# Regenerate shape maps from draw.io GitHub
poetry run python scripts/generate_drawio_shape_maps.py
poetry run black modules/config/drawio_shape_map_*.py

# Run tests
poetry run pytest tests/test_xdot_parser.py tests/test_drawio_emitter.py -v
poetry run pytest -m "not slow" -v  # full suite
```
