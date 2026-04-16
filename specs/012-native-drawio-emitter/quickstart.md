# Quickstart: Native draw.io mxGraph Emitter

**Feature Branch**: `012-native-drawio-emitter`  
**Date**: 2026-04-16

## Overview

This feature replaces the `graphviz2drawio` library with a native mxGraph XML emitter that generates `.drawio` files directly from Graphviz's xdot layout output. It also uses draw.io's built-in AWS/Azure/GCP shape libraries instead of embedded base64 PNG icons.

## Architecture

```
Existing pipeline (unchanged):
  graphdict → drawing.py → DOT file → gvpr post-processing → post.dot

New drawio path (replaces graphviz2drawio.convert()):
  post.dot → dot -Txdot → xdot_parser.py → drawio_emitter.py → .drawio file
                                ↓
                    drawio_shape_map_*.py (shape lookups)
```

## New Modules

| Module | Location | Purpose | ~LOC |
|--------|----------|---------|------|
| `xdot_parser.py` | `modules/` | Parse xdot output into structured data | ~80 |
| `drawio_emitter.py` | `modules/` | Generate mxGraph XML from parsed xdot data | ~250 |
| `drawio_shape_map_aws.py` | `modules/config/` | AWS resource type → draw.io shape mapping | ~150 |
| `drawio_shape_map_azure.py` | `modules/config/` | Azure resource type → draw.io shape mapping | ~100 |
| `drawio_shape_map_gcp.py` | `modules/config/` | GCP resource type → draw.io shape mapping | ~50 |

## Modified Files

| File | Change |
|------|--------|
| `modules/drawing.py` | Replace `if format == "drawio":` block (~20 lines) with native emitter call. Remove `graphviz2drawio` import. |
| `pyproject.toml` | Remove `graphviz2drawio` dependency and `[drawio]` optional group |
| `requirements.txt` | Remove `graphviz2drawio` line |

## Key Design Decisions

1. **xdot parsing, not DOT re-parsing**: We run `dot -Txdot` on the post-processed DOT to get exact layout coordinates, then build mxGraph XML from those coordinates.

2. **Coordinate flip**: Graphviz Y-axis points up; draw.io Y-axis points down. Transform: `drawio_y = graph_height - graphviz_y`.

3. **Native shapes with PNG fallback**: If a resource type has a draw.io shape mapping, use it. Otherwise, read the PNG icon file and embed as base64.

4. **Cluster hierarchy via parent attribute**: mxGraph uses `parent=` on child cells to express containment — maps directly to Graphviz's subgraph nesting.

5. **Edge auto-routing**: We set source/target on edge mxCells and let draw.io handle routing. No need to transfer Graphviz spline data.

## Testing Strategy

```bash
# Unit tests for xdot parser
poetry run pytest tests/test_xdot_parser.py -v

# Unit tests for mxGraph emitter
poetry run pytest tests/test_drawio_emitter.py -v

# Integration test: full pipeline
poetry run pytest tests/test_drawio_integration.py -v

# Manual validation: open in draw.io
poetry run terravision draw --source tests/terraform/aws_simple --format drawio --show
```

## Development Order

1. xdot parser (can be developed and tested independently)
2. mxGraph emitter skeleton (nodes only, no clusters)
3. Cluster rendering
4. Shape library mappings (AWS first, then Azure, GCP)
5. Edge rendering
6. Integration into drawing.py
7. Dependency cleanup
8. Tests
