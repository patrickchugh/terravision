# CLI Contract: `terravision visualise`

**Date**: 2026-04-05  
**Feature**: 011-interactive-html-output

## Command Signature

```
terravision visualise [OPTIONS]
```

## Options

| Flag | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `--source` | string | `.` | Source files location (Git URL, folder, or .JSON file) |
| `--workspace` | string | `default` | Terraform workspace to initialise |
| `--varfile` | string (multiple) | `[]` | Path to .tfvars variables file (can be specified multiple times) |
| `--outfile` | string | `architecture` | Output filename (`.html` extension appended automatically) |
| `--show` | flag | `false` | Open HTML file in default browser after generation |
| `--simplified` | flag | `false` | Simplified high-level services shown only |
| `--annotate` | string | `""` | Path to custom annotations file (YAML) |
| `--planfile` | path | `""` | Path to Terraform plan JSON (`terraform show -json`) |
| `--graphfile` | path | `""` | Path to Terraform graph DOT (`terraform graph`) |
| `--debug` | flag | `false` | Dump exception tracebacks, creates tfdata.json replay file |
| `--upgrade` | flag | `false` | Run terraform init with -upgrade |

## Ignored Flags (Warning Emitted)

| Flag | Behavior |
| ---- | -------- |
| `--format` | Print warning: "WARNING: --format is not applicable to the visualise command. HTML is the only output format." Continue execution. |
| `--aibackend` | Print warning: "WARNING: --aibackend is not applicable to the visualise command." Continue execution. |

## Output

- **Success**: Single self-contained `.html` file at `{outfile}.html` in current working directory
- **With `--show`**: File opens in default browser via `webbrowser.open()`
- **Exit code 0**: Success
- **Exit code 1**: Error (Terraform failure, missing dependencies, etc.)

## Examples

```bash
# Basic usage
terravision visualise --source ./terraform

# Custom output filename
terravision visualise --source ./terraform --outfile my-architecture

# Auto-open in browser
terravision visualise --source ./terraform --show

# From pre-generated plan files
terravision visualise --planfile plan.json --graphfile graph.dot --source ./terraform

# Simplified diagram
terravision visualise --source ./terraform --simplified

# With annotations
terravision visualise --source ./terraform --annotate custom.yml
```
