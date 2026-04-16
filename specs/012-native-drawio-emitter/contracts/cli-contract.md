# CLI Contract: draw.io Export

**Feature Branch**: `012-native-drawio-emitter`  
**Date**: 2026-04-16

## Command Interface

The CLI interface for drawio export remains **unchanged**. This contract documents the existing interface that must be preserved.

### Command

```bash
terravision draw --format drawio [OPTIONS]
```

### Options (applicable to drawio)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--source` | string | `.` | Terraform source directory, Git URL, or JSON debug file |
| `--format` | choice | `png` | Output format — `drawio` triggers the native emitter |
| `--outfile` | string | `architecture` | Output filename (`.drawio` extension added automatically) |
| `--workspace` | string | `default` | Terraform workspace |
| `--varfile` | string (multiple) | None | Variable files |
| `--show` | flag | False | Auto-open the `.drawio` file after generation |
| `--simplified` | flag | False | Generate simplified high-level diagram |
| `--annotate` | string | None | Path to custom annotations YAML |
| `--ai-annotate` | choice | None | Generate AI annotations (`bedrock` or `ollama`) |
| `--planfile` | string | None | Pre-generated Terraform plan JSON |
| `--graphfile` | string | None | Pre-generated Terraform graph DOT |
| `--debug` | flag | False | Enable debug output |

### Output

| Condition | Output |
|-----------|--------|
| Success | `{outfile}.drawio` file in current working directory |
| Success + `--show` | File created AND opened in system default `.drawio` handler |
| Missing Graphviz | Error message with installation instructions, exit code 1 |
| Empty plan | Error message (existing behavior from `setup_tfdata`), exit code 1 |

### Behavioral Changes from Current Implementation

| Aspect | Before (graphviz2drawio) | After (native emitter) |
|--------|--------------------------|------------------------|
| Dependencies | Requires `graphviz2drawio` + `pygraphviz` | No additional dependencies beyond `dot` |
| `--show` flag | Silently ignored for drawio | Opens file in default handler |
| Cluster icons | Silently dropped | Correctly rendered |
| Footer position | Incorrectly at top | Correctly at bottom |
| Node labels | Above icons | Below icons |
| Icon format | Embedded base64 PNG | Native draw.io shapes (with PNG fallback) |
| File size | ~600KB+ for medium diagrams | ~30-60KB for medium diagrams |
| `[drawio]` extra | Required for installation | Not needed |

### Error Messages

```
# When dot binary is not found (new)
Error: Graphviz 'dot' binary not found. Install Graphviz to use drawio export.

# When xdot parsing fails (new)
Error: Failed to parse layout data from Graphviz. Check that your Graphviz version supports -Txdot output.
```

### Removed Interface

The `[drawio]` optional dependency group in `pyproject.toml` will be removed:

```toml
# REMOVED
[project.optional-dependencies]
drawio = ["graphviz2drawio>=1.1.0"]
```

Installation instructions referencing `pip install 'terravision[drawio]'` will be updated to indicate drawio export works out of the box.
