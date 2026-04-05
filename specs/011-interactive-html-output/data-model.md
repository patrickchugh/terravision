# Data Model: Interactive HTML Diagram Output

**Date**: 2026-04-05  
**Feature**: 011-interactive-html-output

## Entities

### HTMLDiagramData

The data structure embedded in the generated HTML file as the `TERRAVISION_DATA` JavaScript object. Contains everything needed to interact with the pre-rendered SVG diagram.

| Field | Type | Description |
| ----- | ---- | ----------- |
| svg_content | string | Pre-rendered SVG string (from `generate_svg()`) with base64-embedded icons. Embedded directly in the HTML `<div id="graph">` element, not in the JSON. |
| metadata | dict[string, ResourceMetadata] | Processed resource metadata keyed by node name. Sourced from `pre_draw_metadata` (snapshot before drawing overwrites entries) or falls back to `meta_data` |
| original_metadata | dict[string, dict] | Raw Terraform plan attributes before handler processing, keyed by node name |
| graphdict | dict[string, list[string]] | Graph structure — node name to list of connected node names. Used for connected-node highlighting |
| node_id_map | dict[string, string] | Mapping from Graphviz SVG node UUID to Terraform resource address. Used by JS click handlers to identify which resource was clicked |
| cluster_id_map | dict[string, string] | Mapping from Graphviz cluster ID to Terraform resource address. Used for group/container click handling (VPCs, subnets, security groups) |
| original_name_map | dict[string, string] | Reverse mapping from current metadata keys to original_metadata keys. Covers renames from consolidation, `~N` suffix stripping, and attribute content matching |
| resource_siblings | dict[string, list[string]] | Related resources from CONSOLIDATED_NODES config and shared type prefix grouping. Used for "Related Resources" section in detail panel |

### ResourceMetadata

Per-resource metadata displayed in the detail panel when a node is clicked.

| Field | Type | Description |
| ----- | ---- | ----------- |
| resource_type | string | Terraform resource type (e.g., "aws_instance") |
| resource_name | string | Terraform resource name (e.g., "web") |
| full_address | string | Full resource address (e.g., "aws_instance.web" or "module.vpc.aws_subnet.private") |
| attributes | dict[string, any] | All Terraform plan attributes (instance_type, ami, tags, etc.) |
| is_synthetic | boolean | True if this is a TerraVision-generated numbered instance (not from real count/for_each) |
| instance_number | int or null | Instance number for numbered resources (e.g., 2 for `web~2`), null otherwise |
| total_instances | int or null | Total instance count for numbered resources, null otherwise |
| module | string | Module name ("main" for root, or module path) |

### ConnectionEdge

Edge data used for rendering animated flow dots.

| Field | Type | Description |
| ----- | ---- | ----------- |
| source | string | Source node name |
| target | string | Target node name |
| label | string or null | Edge label text (from annotations or implied connections) |
| bidirectional | boolean | True if edge has flow in both directions |

## Relationships

```
HTMLDiagramData
├── metadata: {node_name → ResourceMetadata}       (1:many, processed)
├── original_metadata: {node_name → raw_attrs}     (1:many, unprocessed)
├── graphdict: {node_name → [connected_nodes]}     (1:many, edge structure)
├── icons: {path → base64_data}                    (1:many, deduplicated)
└── dot_source: contains node/edge definitions
     └── ConnectionEdge data derived from graphdict edges
```

## State Transitions

The HTML diagram has the following UI states (managed client-side in JavaScript):

```
[Initial Load] → [Diagram Ready]
                      ↓
                 [Node/Cluster Clicked] → [Detail Panel Open] → [Navigate Related Resource]
                      ↓                        ↓                         ↓
                 [Panning/Zooming]        [Panel Closed]          [New Panel Open]
                      ↓                   (X / Escape / bg click)
                 [Fit to Screen]
```

- **Initial Load**: SVG is pre-rendered and embedded — no WASM compilation or DOT processing needed. Diagram is immediately interactive.
- **Diagram Ready**: SVG visible, pan/zoom active via d3-zoom.
- **Node/Cluster Clicked**: Click on node or cluster group → node highlighted with pulsing glow → panel slides in with metadata.
- **Detail Panel Open**: Shows tabbed attributes + related resources. Close via X button, Escape key, or clicking diagram background.
- **Navigate Related Resource**: Clicking a related/connected resource link in the panel opens that resource's details (or shows non-drawn resource metadata).

## Data Volume Estimates

| Component | Typical Size | Large Diagram |
| --------- | ------------ | ------------- |
| Pre-rendered SVG (with base64 icons) | 100-400 KB | 500 KB - 2 MB |
| Metadata JSON | 50-200 KB | 500 KB - 2 MB |
| d3.js | ~273 KB | ~273 KB |
| CSS + JS (template) | ~25 KB | ~25 KB |
| **Total HTML file** | **~500 KB - 1 MB** | **~1.5 - 4 MB** |

Note: No WASM module is needed. The SVG is rendered server-side by the local Graphviz installation.
