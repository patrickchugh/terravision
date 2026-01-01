# Usage Guide

## Quick Start Examples

### Generate Your First Diagram

```bash
# Basic usage - analyze current directory
terravision draw

# Specify source directory
terravision draw --source ~/projects/my-terraform-code

# Open diagram automatically after generation
terravision draw --source ~/projects/my-terraform-code --show
```

---

## Commands

### `terravision draw`

Generates architecture diagrams from Terraform code.

**Syntax:**
```bash
terravision draw [OPTIONS]
```

**Common Options:**

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--source` | Source location (folder, Git URL, or JSON) | Current directory | `./terraform` |
| `--format` | Output format (png, svg, pdf, bmp) | `png` | `--format svg` |
| `--outfile` | Output filename | `architecture` | `--outfile my-diagram` |
| `--workspace` | Terraform workspace | `default` | `--workspace production` |
| `--varfile` | Variable file (can use multiple times) | None | `--varfile prod.tfvars` |
| `--show` | Open diagram after generation | False | `--show` |
| `--simplified` | Generate simplified high-level diagram | False | `--simplified` |
| `--annotate` | Path to annotations YAML file | None | `--annotate custom.yml` |
| `--aibackend` | AI backend (bedrock, ollama) | `bedrock` | `--aibackend ollama` |
| `--debug` | Enable debug output | False | `--debug` |

### `terravision graphdata`

Exports resource relationships and metadata as JSON.

**Syntax:**
```bash
terravision graphdata [OPTIONS]
```

**Common Options:**

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--source` | Source location | Current directory | `./terraform` |
| `--outfile` | Output JSON filename | `architecture.json` | `--outfile resources.json` |
| `--show_services` | Show only unique services list | False | `--show_services` |

---

## Usage Examples

### Local Terraform Directory

```bash
# Generate PNG diagram
terravision draw --source ./terraform

# Generate SVG diagram with custom name
terravision draw --source ./terraform --format svg --outfile my-architecture

# Use specific workspace
terravision draw --source ./terraform --workspace production

# Use variable files
terravision draw --source ./terraform --varfile prod.tfvars --varfile secrets.tfvars
```

### Remote Git Repositories

```bash
# Analyze entire repository
terravision draw --source https://github.com/user/terraform-repo.git

# Analyze specific subfolder
terravision draw --source https://github.com/user/terraform-repo.git//aws/vpc

# Analyze specific branch
terravision draw --source https://github.com/user/terraform-repo.git?ref=develop
```

### Multiple Output Formats

```bash
# Generate all formats
terravision draw --source ./terraform --format png --outfile arch-png
terravision draw --source ./terraform --format svg --outfile arch-svg
terravision draw --source ./terraform --format pdf --outfile arch-pdf

# Batch processing
for format in png svg pdf; do
  terravision draw --source ./terraform --format $format --outfile arch-$format
done
```

### Working with Annotations

```bash
# Use annotations file
terravision draw --source ./terraform --annotate custom-annotations.yml

# Annotations file will be auto-loaded if named terravision.yml in source directory
terravision draw --source ./terraform
```

See [ANNOTATIONS.md](ANNOTATIONS.md) for annotation file format.

### Export and Reuse Graph Data

```bash
# Export graph data
terravision graphdata --source ./terraform --outfile graph.json

# Generate diagram from exported data (faster)
terravision draw --source graph.json --format svg

# Show only services used
terravision graphdata --source ./terraform --show_services
```

### Debug Mode

```bash
# Enable debug output
terravision draw --source ./terraform --debug

# This creates tfdata.json which can be reused
terravision draw --source tfdata.json --format svg
```

---

## Output Formats

### PNG (Default)
- **Use for**: Documentation, wikis, presentations
- **Pros**: Universal support, good quality
- **Cons**: Not scalable, larger file size

```bash
terravision draw --source ./terraform --format png
```

### SVG
- **Use for**: Web pages, scalable diagrams
- **Pros**: Scalable, smaller file size, editable
- **Cons**: Some tools don't support SVG

```bash
terravision draw --source ./terraform --format svg
```

### PDF
- **Use for**: Reports, documentation, printing
- **Pros**: Professional, portable, printable
- **Cons**: Larger file size

```bash
terravision draw --source ./terraform --format pdf
```

---

## Advanced Usage

### Multiple Environments

```bash
# Generate diagrams for different environments
terravision draw --source ./terraform --varfile dev.tfvars --outfile arch-dev
terravision draw --source ./terraform --varfile staging.tfvars --outfile arch-staging
terravision draw --source ./terraform --varfile prod.tfvars --outfile arch-prod
```

### Simplified Diagrams

For large infrastructures, generate high-level overview:

```bash
terravision draw --source ./terraform --simplified --outfile overview
```

### AI-Powered Refinement

```bash
# Use AWS Bedrock (default)
terravision draw --source ./terraform --aibackend bedrock

# Use local Ollama
terravision draw --source ./terraform --aibackend ollama
```

See [AI_REFINEMENT.md](AI_REFINEMENT.md) for setup instructions.

---

## Performance Tips

### Large Terraform Projects

1. **Use simplified mode** for overview diagrams:
   ```bash
   terravision draw --source ./terraform --simplified
   ```

2. **Export to JSON first**, then generate multiple variants:
   ```bash
   terravision graphdata --source ./terraform --outfile graph.json
   terravision draw --source graph.json --format png
   terravision draw --source graph.json --format svg
   ```

3. **Use specific workspaces** to reduce scope:
   ```bash
   terravision draw --source ./terraform --workspace production
   ```

### Batch Processing

```bash
# Process multiple Terraform directories
for dir in terraform/*; do
  terravision draw --source $dir --outfile $(basename $dir)
done
```

---

## Common Workflows

### Daily Development

```bash
# Quick check of current infrastructure
terravision draw --show
```

### Code Review

```bash
# Generate diagram for PR review
terravision draw --source ./terraform --format svg --outfile pr-${PR_NUMBER}
```

### Documentation Updates

```bash
# Generate all formats for documentation
terravision draw --format png --outfile docs/images/architecture
terravision draw --format svg --outfile docs/images/architecture
```

### CI/CD Pipeline

```bash
# Generate diagram with build number
terravision draw --format svg --outfile architecture-${BUILD_NUMBER}
```

See [CICD_INTEGRATION.md](CICD_INTEGRATION.md) for complete CI/CD examples.

---

## Next Steps

- **[Annotations Guide](ANNOTATIONS.md)** - Customize your diagrams
- **[CI/CD Integration](CICD_INTEGRATION.md)** - Automate diagram generation
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
