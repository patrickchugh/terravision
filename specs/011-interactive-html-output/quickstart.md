# Quickstart: Interactive HTML Diagram Output

**Date**: 2026-04-05  
**Feature**: 011-interactive-html-output

## What This Feature Does

Adds a new `terravision visualise` command that generates a self-contained interactive HTML file from Terraform code. The HTML diagram:
- Renders identically to the existing PNG output (same Graphviz engine renders SVG server-side)
- Lets users click any resource node or group container to inspect Terraform metadata in a cyberpunk-themed sidebar
- Shows related/connected resources with clickable navigation
- Provides copy-to-clipboard and expand modal on attribute values
- Supports pan, zoom, and fit-to-screen for navigating large diagrams
- Works fully offline — no internet connection needed to view (~500KB-1.5MB file size)

## Try It

```bash
# Generate an interactive HTML diagram
poetry run terravision visualise --source ./path/to/terraform

# Open the generated file
open architecture.html    # macOS
xdg-open architecture.html  # Linux

# Or auto-open in browser
poetry run terravision visualise --source ./path/to/terraform --show
```

## Key Interaction Points

In the generated HTML:
- **Click** any resource icon or group container (VPC, subnet, security group) to see its metadata in the detail panel
- **Detail panel** shows resource attributes in a cyberpunk dark blue sidebar with tabbed view (Attributes / Raw Plan)
- **Copy/Expand** buttons on each attribute value for clipboard copy and full-value modal view
- **Related Resources** section shows Connected Resources (green) and Related Same Type (blue), all clickable
- **Scroll wheel** to zoom in/out
- **Click + drag** on empty space to pan
- **Fit to screen** button to reset the view
- **Escape key** to close the detail panel
- Selected nodes glow with a pulsing cyan highlight

## Architecture Overview

```
terravision visualise --source ./terraform
        │
        ├── compile_tfdata()          ← Shared with 'draw' command
        │   ├── tf_initplan()
        │   ├── tf_makegraph()
        │   ├── read_tfsource()
        │   └── _enrich_graph_data()
        │
        ├── simplify_graphdict()      ← If --simplified
        │
        └── render_html()             ← NEW (replaces render_diagram)
            ├── generate_svg()        ← NEW function in drawing.py
            │   ├── generate_dot()    ← NEW: builds DOT, runs gvpr, returns DOT + node_id_map
            │   └── Render DOT → SVG via local Graphviz (neato)
            │   └── Replace icon paths with base64 data URIs in SVG
            ├── _serialize_metadata() ← Builds metadata + graphdict + siblings JSON
            └── _assemble_html()      ← Template assembly
                ├── d3.js (vendored, ~273KB — only JS dependency)
                ├── Pre-rendered SVG with embedded icons
                ├── Metadata JSON (metadata, original_metadata, graphdict,
                │   node_id_map, cluster_id_map, original_name_map, resource_siblings)
                ├── CSS styles (cyberpunk dark blue theme)
                └── Interactivity JS (click handlers, detail panel, zoom/pan)
```

## File Structure

New and modified files for this feature:
```
modules/
├── html_renderer.py         # Main HTML generation logic
├── drawing.py               # MODIFIED: added generate_dot() and generate_svg()
├── vendor/
│   └── d3.min.js            # Vendored d3.js (~273KB) — only JS dependency
└── templates/
    └── interactive.html     # HTML template with JS/CSS (cyberpunk theme)

terravision/
└── terravision.py           # New 'visualise' Click command
```
