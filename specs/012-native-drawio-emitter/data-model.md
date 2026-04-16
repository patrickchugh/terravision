# Data Model: Native draw.io mxGraph Emitter

**Feature Branch**: `012-native-drawio-emitter`  
**Date**: 2026-04-16

## Entities

### 1. XdotGraph

Parsed representation of the xdot output from the post-processed DOT file.

| Field | Type | Description |
|-------|------|-------------|
| bounding_box | (x1, y1, x2, y2) | Graph-level bounding box from root `bb=` attribute |
| nodes | dict[str, XdotNode] | All nodes keyed by DOT node ID |
| clusters | dict[str, XdotCluster] | All clusters keyed by DOT cluster name |
| edges | list[XdotEdge] | All edges with source/target references |

### 2. XdotNode

A parsed node from xdot output.

| Field | Type | Description |
|-------|------|-------------|
| id | str | DOT node ID (e.g., `aws_lambda_function.my_func`) |
| pos | (x, y) | Center position in Graphviz coordinates |
| width | float | Width in inches |
| height | float | Height in inches |
| label | str | Plain text or HTML label |
| image | str or None | Icon file path from `image=` attribute |
| label_pos | (x, y) or None | Label position from `lp=` attribute |
| attrs | dict | Additional DOT attributes (`_titlenode`, `_footernode`, `_legendnode`, `_clusterlabel`, `_edgenode`, etc.) |

### 3. XdotCluster

A parsed cluster/subgraph from xdot output.

| Field | Type | Description |
|-------|------|-------------|
| name | str | DOT cluster name (e.g., `cluster_VPCgroup.123`) |
| bb | (x1, y1, x2, y2) | Bounding box in Graphviz coordinates |
| label | str | Cluster label (plain text or HTML) |
| parent | str or None | Parent cluster name for nesting |
| style | dict | DOT style attributes (color, fillcolor, etc.) |

### 4. XdotEdge

A parsed edge from xdot output.

| Field | Type | Description |
|-------|------|-------------|
| source | str | Source node ID |
| target | str | Target node ID |
| label | str or None | Edge label text |
| label_pos | (x, y) or None | Label position |
| is_bidirectional | bool | Whether edge has arrows on both ends |

### 5. DrawioShapeMapping

Lookup table mapping TerraVision resource types to draw.io native shapes.

| Field | Type | Description |
|-------|------|-------------|
| resource_type | str | TerraVision resource type (e.g., `aws_lambda_function`) |
| drawio_shape | str | draw.io shape-library identifier (e.g., `mxgraph.aws4.lambda_function`) |
| style_overrides | dict or None | Optional style properties (width, height, aspect ratio) |

### 6. MxCell

An mxGraph XML cell to be emitted.

| Field | Type | Description |
|-------|------|-------------|
| id | str | Unique cell identifier |
| value | str | Display label (XML-escaped) |
| style | str | Semicolon-delimited style string |
| vertex | bool | True for nodes/clusters, False for edges |
| edge | bool | True for edges |
| parent | str | Parent cell ID (cluster ID or "1" for root) |
| source | str or None | Source cell ID (edges only) |
| target | str or None | Target cell ID (edges only) |
| geometry | MxGeometry | Position and dimensions |

### 7. MxGeometry

Position and size data for an mxCell.

| Field | Type | Description |
|-------|------|-------------|
| x | float | X position (draw.io coordinates, top-left origin) |
| y | float | Y position (draw.io coordinates, top-left origin) |
| width | float | Cell width in pixels |
| height | float | Cell height in pixels |
| relative | bool | Whether geometry is relative (used for edges) |

## Relationships

```
XdotGraph
  ├── 1:N → XdotNode
  ├── 1:N → XdotCluster (parent → child nesting)
  └── 1:N → XdotEdge (source/target → XdotNode)

DrawioShapeMapping (static lookup, per provider)
  └── maps resource_type → drawio_shape

MxCell (output)
  ├── parent → MxCell (cluster containment)
  ├── source → MxCell (edge origin)
  └── target → MxCell (edge destination)
```

## State Transitions

The data flows through these stages:

```
DOT file (post-gvpr) 
  → dot -Txdot 
  → raw xdot text
  → XdotGraph (parsed)
  → List[MxCell] (transformed, coordinates flipped)
  → mxGraphModel XML (serialized)
  → .drawio file
```

## Validation Rules

- Every node in `graphdict` must produce exactly one MxCell vertex
- Every edge must reference valid source/target MxCell IDs
- Cluster parent references must form a tree (no cycles)
- All XML text content must be escaped (no raw `<`, `>`, `&`, `"` in attribute values)
- Node dimensions must be positive (width > 0, height > 0)
- Bounding box coordinates must satisfy x2 > x1 and y2 > y1
