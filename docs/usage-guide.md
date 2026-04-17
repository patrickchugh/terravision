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

### Try It on the Bundled Test Fixtures

If you're not ready to point TerraVision at your own Terraform yet, the repo ships with real Terraform projects under [`tests/fixtures/`](https://github.com/patrickchugh/terravision/tree/main/tests/fixtures) that you can use to see the tool in action. Clone the repo first, then run any of the examples below:

```bash
git clone https://github.com/patrickchugh/terravision.git
cd terravision
```

=== "AWS"

    EKS cluster in auto mode (fully managed node groups, ingress controller, sample workload):

    ```bash
    terravision draw --source tests/fixtures/aws_terraform/eks_automode --show
    ```

    Other AWS fixtures worth trying:
    `api_gateway_rest_lambda`, `dynamodb_streams_lambda`, `ecs-ec2`, `elasticache_redis`, `sagemaker_endpoint`, `stepfunctions_multi_service`, `waf_cloudfront`, `static-website`.

=== "Azure"

    VM scale set behind a load balancer in a VNet:

    ```bash
    terravision draw --source tests/fixtures/azure_terraform/test_vm_vmss --show
    ```

    Other Azure fixtures worth trying:
    `test_aks` (AKS cluster), `test_appgw_lb` (Application Gateway + LB).

=== "GCP"

    Classic three-tier web app (GCE + LB + Cloud SQL):

    ```bash
    terravision draw --source tests/fixtures/gcp_terraform/three_tier_webapp --show
    ```

    Other GCP fixtures worth trying:
    `us4_gke_cluster` (GKE), `us6_serverless` (Cloud Run / Functions), `us8_vpc_firewall` (networking), `us9_data_services` (BigQuery, Pub/Sub, Dataflow).

=== "Terragrunt"

    Multi-module Terragrunt project — TerraVision auto-detects `terragrunt.hcl` and stitches each module into one diagram:

    ```bash
    terravision draw --source tests/fixtures/terragrunt-multi --show
    ```

!!! tip "Skip the `--show` flag"
    Omit `--show` to generate the PNG without opening a viewer — useful in CI or over SSH. The default output file is `architecture.png` in the current directory.

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
| `--source` | Source location (folder, Git URL, or JSON) | Current directory | `./path-to-your-terraform` |
| `--format` | Output format (png, svg, pdf, bmp) | `png` | `--format svg` |
| `--outfile` | Output filename | `architecture` | `--outfile my-diagram` |
| `--workspace` | Terraform workspace | `default` | `--workspace production` |
| `--varfile` | Variable file (can use multiple times) | None | `--varfile prod.tfvars` |
| `--show` | Open diagram after generation | False | `--show` |
| `--simplified` | Generate simplified high-level diagram | False | `--simplified` |
| `--annotate` | Path to annotations YAML file | None | `--annotate custom.yml` |
| `--ai-annotate` | Generate AI annotations with specified backend (bedrock, ollama) | None | `--ai-annotate ollama` |
| `--planfile` | Pre-generated Terraform plan JSON | None | `--planfile plan.json` |
| `--graphfile` | Pre-generated Terraform graph DOT | None | `--graphfile graph.dot` |
| `--debug` | Enable debug output | False | `--debug` |

### `terravision visualise`

Generates a self-contained interactive HTML diagram with clickable resource nodes, metadata sidebar, and pan/zoom navigation. The diagram is rendered server-side using the same Graphviz engine as `draw`, so the layout is identical.

**See it live — interactive demos:**

- 🟧 [AWS demo](https://patrickchugh.github.io/terravision/demo-aws.html) — Wordpress on ECS Fargate with CloudFront, RDS, EFS
- 🟦 [Azure demo](https://patrickchugh.github.io/terravision/demo-azure.html) — VM scale set with load balancer and VNet
- 🟩 [GCP demo](https://patrickchugh.github.io/terravision/demo-gcp.html) — Core GCP networking and compute

Click nodes to inspect metadata, use the search box, or pan/zoom around to explore.

**Syntax:**
```bash
terravision visualise [OPTIONS]
```

**Common Options:**

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--source` | Source location (folder, Git URL, or JSON) | Current directory | `./path-to-your-terraform` |
| `--outfile` | Output filename (`.html` appended automatically) | `architecture` | `--outfile my-diagram` |
| `--workspace` | Terraform workspace | `default` | `--workspace production` |
| `--varfile` | Variable file (can use multiple times) | None | `--varfile prod.tfvars` |
| `--show` | Auto-open HTML in default browser | False | `--show` |
| `--simplified` | Generate simplified high-level diagram | False | `--simplified` |
| `--annotate` | Path to annotations YAML file | None | `--annotate custom.yml` |
| `--planfile` | Pre-generated Terraform plan JSON | None | `--planfile plan.json` |
| `--graphfile` | Pre-generated Terraform graph DOT | None | `--graphfile graph.dot` |
| `--debug` | Enable debug output | False | `--debug` |

**Interactive features in the generated HTML:**

- **Click any resource or group container** (VPC, subnet, security group) to see its Terraform metadata in a slide-in sidebar
- **Search box** in the top-right to find resources by name and jump to them
- **Pan/zoom controls** plus mouse wheel zoom and click-drag pan
- **Pulsing flow dots** on connection edges showing data flow direction
- **Related Resources** section in the sidebar — click to navigate to connected nodes (graph edges, green) or sibling resources of the same type (blue)
- **Copy/Expand buttons** on each metadata field for clipboard copy and full-text modal view
- **Escape key** closes the detail panel
- **Empty/computed fields** hidden by default with a "Show N fields" toggle

**Examples:**

```bash
# Basic usage
terravision visualise --source ./path-to-your-terraform

# Custom output filename and auto-open in browser
terravision visualise --source ./path-to-your-terraform --outfile my-arch --show

# From pre-generated plan files (no Terraform credentials needed)
terravision visualise --planfile plan.json --graphfile graph.dot --source ./path-to-your-terraform

# Simplified high-level diagram
terravision visualise --source ./path-to-your-terraform --simplified

# Replay from debug JSON for fast iteration
terravision visualise --source tfdata.json
```

The output is a single self-contained HTML file (~500KB-1.5MB) that works fully offline — no internet connection or external resources required.

### `terravision graphdata`

Exports resource relationships and metadata as JSON.

**Syntax:**
```bash
terravision graphdata [OPTIONS]
```

**Common Options:**

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--source` | Source location | Current directory | `./path-to-your-terraform` |
| `--outfile` | Output JSON filename | `architecture.json` | `--outfile resources.json` |
| `--show_services` | Show only unique services list | False | `--show_services` |
| `--planfile` | Pre-generated Terraform plan JSON | None | `--planfile plan.json` |
| `--graphfile` | Pre-generated Terraform graph DOT | None | `--graphfile graph.dot` |

---

## Usage Examples

### Local Terraform Directory

```bash
# Generate PNG diagram
terravision draw --source ./path-to-your-terraform

# Generate SVG diagram with custom name
terravision draw --source ./path-to-your-terraform --format svg --outfile my-architecture

# Use specific workspace
terravision draw --source ./path-to-your-terraform --workspace production

# Use variable files
terravision draw --source ./path-to-your-terraform --varfile prod.tfvars --varfile secrets.tfvars
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
terravision draw --source ./path-to-your-terraform --format png --outfile arch-png
terravision draw --source ./path-to-your-terraform --format svg --outfile arch-svg
terravision draw --source ./path-to-your-terraform --format pdf --outfile arch-pdf

# Batch processing
for format in png svg pdf; do
  terravision draw --source ./path-to-your-terraform --format $format --outfile arch-$format
done
```

### Working with Annotations

```bash
# Use annotations file
terravision draw --source ./path-to-your-terraform --annotate custom-annotations.yml

# Annotations file will be auto-loaded if named terravision.yml in source directory
terravision draw --source ./path-to-your-terraform
```

See [annotations.md](annotations.md) for annotation file format.

### Export and Reuse Graph Data

```bash
# Export graph data
terravision graphdata --source ./path-to-your-terraform --outfile graph.json

# Generate diagram from exported data (faster)
terravision draw --source graph.json --format svg

# Show only services used
terravision graphdata --source ./path-to-your-terraform --show_services
```

### Debug Mode

```bash
# Enable debug output
terravision draw --source ./path-to-your-terraform --debug

# This creates tfdata.json which can be reused
terravision draw --source tfdata.json --format svg
```

---

## Output Formats

TerraVision supports all output formats provided by Graphviz. Use the `--format` option to specify your desired format.

### Common Formats

| Format | Description | Best For |
|--------|-------------|----------|
| `png` | Portable Network Graphics (default) | Documentation, wikis, presentations |
| `svg` | Scalable Vector Graphics | Web pages, scalable diagrams, editing |
| `pdf` | Portable Document Format | Reports, printing, professional docs |
| **`drawio`** | **Native draw.io / mxGraph XML — fully editable** | **Editing in draw.io, Lucidchart, or any mxGraph tool** |
| `jpg` / `jpeg` | JPEG image | Photos, web (lossy compression) |
| `gif` | Graphics Interchange Format | Simple graphics, animations |
| `bmp` | Windows Bitmap | Windows applications |
| `eps` | Encapsulated PostScript | Print publishing, LaTeX |
| `ps` / `ps2` | PostScript | Print publishing |
| `tif` / `tiff` | Tagged Image File Format | High-quality archival |
| `webp` | WebP format | Modern web (good compression) |
| `dot` | Graphviz DOT source | Further editing, custom rendering |
| `json` | Graphviz JSON with layout info | Advanced programmatic processing (note: different from `graphdata` output) |
| `xdot` | Extended DOT with layout | Advanced rendering applications |

For the complete list of supported formats, see the [Graphviz Output Formats documentation](https://graphviz.org/docs/outputs/).

**Note**: `--format json` produces Graphviz's internal JSON format with layout coordinates. For TerraVision's simple graph dictionary (just nodes and connections), use the `graphdata` command instead.
 
### Pre-Generated Plan Input

If you already have Terraform plan and graph output files (e.g. from a CI/CD pipeline), you can generate diagrams without running Terraform. This is useful when:

- Terraform runs in a separate pipeline step or environment
- Cloud credentials are not available in the diagram generation environment
- You want to generate diagrams from archived plan files

**Step 1: Generate plan and graph files** (in your Terraform environment):

```bash
cd /path/to/terraform
terraform init
terraform plan -out=tfplan.bin
terraform show -json tfplan.bin > plan.json
terraform graph > graph.dot
```

**Step 2: Generate diagrams** (no Terraform or cloud credentials needed):

```bash
# Draw diagram from pre-generated files
terravision draw --planfile plan.json --graphfile graph.dot --source ./path-to-your-terraform

# Export graph data from pre-generated files
terravision graphdata --planfile plan.json --graphfile graph.dot --source ./path-to-your-terraform --outfile resources.json

# Combine with other options
terravision draw --planfile plan.json --graphfile graph.dot --source ./path-to-your-terraform \
  --format svg --outfile my-architecture --annotate custom.yml
```

**Requirements**:
- `--planfile` must be a JSON file from `terraform show -json` (not a binary `.tfplan` file)
- `--graphfile` must be a DOT file from `terraform graph`
- `--source` must point to the Terraform source directory (for HCL parsing)
- All three options (`--planfile`, `--graphfile`, `--source`) are required together

**Notes**:
- `--workspace` and `--varfile` are ignored when `--planfile` is used (a warning is printed)
- Terraform does not need to be installed when using `--planfile` mode
- The plan JSON must contain `resource_changes` with at least one resource

See [CI/CD Integration](cicd-integration.md) for pipeline examples using pre-generated plan files.

---

## Advanced Usage

### Multiple Environments

```bash
# Generate diagrams for different environments
terravision draw --source ./path-to-your-terraform --varfile dev.tfvars --outfile arch-dev
terravision draw --source ./path-to-your-terraform --varfile staging.tfvars --outfile arch-staging
terravision draw --source ./path-to-your-terraform --varfile prod.tfvars --outfile arch-prod
```

### Simplified Diagrams

For large infrastructures, generate high-level overview:

```bash
terravision draw --source ./path-to-your-terraform --simplified --outfile overview
```

### AI-Powered Annotations

When you pass `--ai-annotate <backend>`, TerraVision uses an LLM to generate a `terravision.ai.yml` annotation file containing AI-suggested edge labels, titles, external actors, and flow sequences. The deterministic graph is never modified by the AI -- all suggestions are written to the annotation file and merged with any existing `terravision.yml` at render time.

This replaces the old `refine_with_llm` behaviour, which modified the graph directly. The new approach is safer (the graph is byte-identical with or without `--ai-annotate`) and auditable (you can inspect `terravision.ai.yml` to see exactly what the AI suggested).

```bash
# Generate AI annotations with local Ollama
poetry run terravision draw --source ./path-to-your-terraform --ai-annotate ollama

# Generate AI annotations with AWS Bedrock
poetry run terravision draw --source ./path-to-your-terraform --ai-annotate bedrock
```

**How it works:**
1. TerraVision builds the graph deterministically (identical to a non-AI run)
2. The graph and HCL context are sent to the LLM, which returns YAML annotations
3. The AI annotations are written to `terravision.ai.yml` in the source directory
4. If a user `terravision.yml` also exists, both files are merged (user file takes precedence)
5. The merged annotations are applied to the graph before rendering

### Two-File Model

TerraVision uses a two-file annotation model that separates AI-generated suggestions from your manual customizations:

| File | Purpose | Created By |
|------|---------|------------|
| `terravision.yml` | User-authored annotations | You (manually) |
| `terravision.ai.yml` | AI-generated annotations | TerraVision with `--ai-annotate <backend>` |

Both files use the same YAML schema (format 0.2). When both are present in the source directory, they are merged automatically at render time. You never need to edit `terravision.ai.yml` by hand -- it is regenerated on each AI-enabled run.

**Precedence (highest to lowest):**

| Source | Priority | Example |
|--------|----------|---------|
| `--annotate <path>` (CLI flag) | Highest | Explicit path overrides everything |
| `terravision.yml` (user file) | Medium | Your manual edits always beat AI suggestions |
| `terravision.ai.yml` (AI file) | Lowest | AI suggestions apply only when no conflict exists |

This means you can let the AI generate a baseline annotation file, then selectively override specific labels, connections, or flows in your `terravision.yml` without losing the rest of the AI output.

### Flow Annotations

Flows describe named request paths through your architecture (e.g., "User Login", "Data Ingestion"). Each flow is a sequence of steps that map to resources in your diagram.

**Example `terravision.yml` with flows:**

```yaml
format: 0.2
title: Payment Processing Architecture

flows:
  payment_request:
    description: "Customer payment flow"
    steps:
      - node: Internet
        label: "1. Customer submits payment"
      - edge: [Internet, aws_api_gateway_rest_api.payments]
        label: "2. HTTPS POST /pay"
      - node: aws_lambda_function.process_payment
        label: "3. Validate and process"
      - edge: [aws_lambda_function.process_payment, aws_dynamodb_table.transactions]
        label: "4. Store transaction"
      - node: aws_sqs_queue.notifications
        label: "5. Queue confirmation"

  refund_flow:
    description: "Refund processing"
    steps:
      - node: aws_lambda_function.process_refund
        label: "1. Initiate refund"
      - edge: [aws_lambda_function.process_refund, aws_dynamodb_table.transactions]
        label: "2. Update transaction status"
```

**How flows render on diagrams:**

- Each step produces a small colored circle (badge) with the step number on the corresponding node or edge.
- A legend table is automatically generated at the bottom of the diagram listing each flow name, step number, and label.
- Step numbers are continuous across multiple flows. If "payment_request" uses steps 1-5, "refund_flow" continues from 6. This ensures every badge number on the diagram is unique.
- If a node appears in multiple flows, it displays a combined badge showing all step numbers (e.g., "3, 8").

**Generating flows with AI:**

When you use `--ai-annotate <backend>`, TerraVision can generate flow sequences automatically based on the architecture:

```bash
poetry run terravision draw --source ./path-to-your-terraform --ai-annotate ollama
```

The AI writes its suggested flows to `terravision.ai.yml`. To override a specific flow, define a flow with the same name in your `terravision.yml` -- the user version entirely replaces the AI version for that flow name.

See [annotations.md](annotations.md) for the full annotation file format and precedence rules.

---

## Performance Tips

### Large Terraform Projects

1. **Use simplified mode** for overview diagrams:
   ```bash
   terravision draw --source ./path-to-your-terraform --simplified
   ```

2. **Export to JSON first**, then generate multiple variants:
   ```bash
   terravision graphdata --source ./path-to-your-terraform --outfile graph.json
   terravision draw --source graph.json --format png
   terravision draw --source graph.json --format svg
   ```

3. **Use specific workspaces** to reduce scope:
   ```bash
   terravision draw --source ./path-to-your-terraform --workspace production
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
terravision draw --source ./path-to-your-terraform --format svg --outfile pr-${PR_NUMBER}
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

See [cicd-integration.md](cicd-integration.md) for complete CI/CD examples.

---

## Next Steps

- **[Annotations Guide](annotations.md)** - Customize your diagrams
- **[CI/CD Integration](cicd-integration.md)** - Automate diagram generation
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
