# Frequently Asked Questions

## About TerraVision

### What is TerraVision?

TerraVision is a command-line tool that converts Terraform code into professional cloud architecture diagrams using the official AWS, GCP, and Azure icon sets. It runs entirely on your local machine and keeps your infrastructure documentation in sync with your code.

### How is it different from `terraform graph`?

`terraform graph` outputs a raw dependency graph in Graphviz DOT format — technically accurate but not human-readable. TerraVision takes that raw graph as one input, enriches it with plan data and provider-specific layout rules, groups resources into VPCs/subnets/resource groups, applies official cloud icons, and produces a diagram you can actually put in front of a stakeholder.

### Is it free?

Yes. TerraVision is open source — see [LICENSE on GitHub](https://github.com/patrickchugh/terravision/blob/main/LICENSE).

---

## Security and Privacy

### Does TerraVision need cloud credentials?

**TerraVision itself does not.** It never calls any cloud API.

However, the tool it depends on — Terraform — does need credentials to run `terraform plan`, because Terraform resolves data sources and validates references against your cloud account. Two ways to avoid this:

1. **Use pre-generated plan files**: run `terraform plan` once (in a trusted environment), export the output, and pass it to TerraVision with `--planfile` and `--graphfile`. The diagramming step then needs no credentials at all. See [Pre-Generated Plan Input](usage-guide.md#pre-generated-plan-input).
2. **Run Terraform locally** with your normal developer credentials — the plan output stays on your machine.

### Does my Terraform code leave my machine?

**No.** TerraVision runs 100% client-side. Your `.tf` files, `.tfvars`, and plan output are parsed locally and never transmitted anywhere.

The only exception is when you opt into `--ai-annotate`, and even then the source code itself is not sent — see the next question.

### What data is sent to the LLM when I use `--ai-annotate`?

Only a compact summary:

- The **resource graph** — resource types (e.g. `aws_lambda_function`), logical names, and the edges between them
- **Lightweight metadata** — selected attributes like resource tags, labels, and port numbers that help the model generate useful connection labels and flow sequences

**Never sent:**

- Your `.tf` source code
- Variable values, secrets, access keys, or anything from your environment
- Plan state beyond the graph topology

The LLM response is written to `terravision.ai.yml` as a human-readable annotation file, which is merged on top of the deterministic graph at render time. You can inspect exactly what the AI suggested before it appears on your diagram. See the [Annotations Guide](annotations.md) for details.

### Can I audit what the AI changed?

Yes. The `terravision.ai.yml` file is a plain YAML file containing every AI-suggested label, title, external actor, and flow. The underlying graph (`graphdict`) is byte-identical with or without `--ai-annotate` — AI suggestions flow through the annotation layer only, never into the graph itself.

### Which LLM backends are supported?

- **Ollama** (local) — runs on your own machine, no data leaves it. Recommended for most users.
- **AWS Bedrock** — uses your AWS account and stays within AWS.

You can also skip AI entirely and write your own `terravision.yml` by hand.

---

## Running TerraVision

### Can I run it fully offline?

Yes — once installed, TerraVision works without a network connection. The `visualise` HTML output is a single self-contained file with no external dependencies (fonts, JS libraries, and icons are all inlined), so you can open it offline too.

If you point `--source` at a Git URL, that clone obviously needs network access, but local directories don't.

### What versions of Terraform are supported?

Terraform **1.x** (v1.0.0 or later). OpenTofu is supported via the same binary interface. Terraform 0.x is not supported.

### Does it work with Terragrunt?

Yes, with auto-detection:

- **Single-module** (`terragrunt.hcl` in the source directory): delegated to `terragrunt init` / `terragrunt plan`, then `terraform show` / `terraform graph` in the cache directory.
- **Multi-module** (child directories with their own `terragrunt.hcl`): each module is planned independently, outputs merged with `module.<name>.` prefixes, and `dependency` blocks are parsed to inject cross-module edges.

Requires Terragrunt v0.50+ for unified `run-all` syntax.

### Does it support Terraform modules from private Git repos?

Yes. TerraVision uses your local Git credentials (SSH keys, `GIT_ASKPASS`, etc.), and Terraform module sources like `git::ssh://...` or private `github.com/...` URLs work as normal.

### Does it support OpenTofu?

Yes. OpenTofu's CLI is a drop-in replacement for the Terraform binary on PATH.

### Why does my diagram look different from my actual deployed infrastructure?

The graph is built from `terraform plan` output, which represents the *desired* state declared in your code. If your deployed infrastructure has drifted (manual changes in the console, another tool, etc.), the diagram reflects the code, not the drift. Run `terraform plan` yourself to see the same divergence.

---

## Output and Customization

### What output formats are supported?

All Graphviz formats (png, svg, pdf, jpg, gif, bmp, eps, webp, dot, xdot, json, tif…) plus native draw.io XML export (`--format drawio`). See [Output Formats](usage-guide.md#output-formats) for the full list.

### Can I edit the diagram afterwards?

Yes — export with `--format drawio` and open the result in [draw.io](https://app.diagrams.net/), [Lucidchart](https://www.lucidchart.com/), or any other mxGraph-compatible editor. Everything is editable: move nodes, change colours, add annotations, swap icons.

For SVG output, any vector editor (Illustrator, Inkscape, Figma) will open it.

### How do I add custom labels, external actors, or override connections?

Create a `terravision.yml` in your Terraform directory. See the [Annotations Guide](annotations.md) for the full schema.

### Can I generate different diagrams for dev vs prod?

Yes — use `--varfile` with different `.tfvars` files:

```bash
terravision draw --source ./path-to-your-terraform --varfile dev.tfvars --outfile arch-dev
terravision draw --source ./path-to-your-terraform --varfile prod.tfvars --outfile arch-prod
```

Or use `--workspace` to target a specific Terraform workspace.

### How do I embed diagrams in my docs site?

- Export as `svg` and include it like any image — it scales cleanly.
- Or use the interactive HTML from `terravision visualise` as an iframe or standalone page (see the [AWS](https://patrickchugh.github.io/terravision/demo-aws.html), [Azure](https://patrickchugh.github.io/terravision/demo-azure.html), and [GCP](https://patrickchugh.github.io/terravision/demo-gcp.html) demos for examples).

---

## Cloud Providers and Scope

### Which cloud providers are supported?

| Provider     | Status      | Scope                                                  |
| ------------ | ----------- | ------------------------------------------------------ |
| AWS          | Full        | 200+ services (compute, networking, storage, data, …)  |
| Google Cloud | Partial     | Core services (GCE, GKE, Cloud SQL, VPC, Load Balancer, …) |
| Azure        | Partial     | Core services (VM, VMSS, AKS, VNet, Load Balancer, …)  |

### Can I use it for multi-cloud architectures?

Yes — a single Terraform project can declare resources from AWS, GCP, and Azure simultaneously, and TerraVision will render all three on the same diagram with each provider's own icon set.

### Can I add support for a new service or resource type?

Most services need no special handling — the baseline Terraform graph plus icon mapping produces an accurate diagram. If you find a resource rendering incorrectly, check the [Resource Handler Guide](resource-handler-guide.md) and either open an issue or submit a PR.

---

## CI/CD

### Do I need cloud credentials in my CI job that generates diagrams?

No, if you use `--planfile` and `--graphfile`. Run `terraform plan` in a trusted job with credentials, export the plan and graph, then pass them to `terravision draw` in a separate credential-free step. See the [CI/CD Integration Guide](cicd-integration.md) for GitHub Actions, GitLab, Jenkins, and Azure DevOps examples.

### Is there an official GitHub Action?

Yes — [patrickchugh/terravision-action](https://github.com/patrickchugh/terravision-action) installs TerraVision and Graphviz for you.

### Is there an official Docker image?

Yes — `patrickchugh/terravision:latest` on Docker Hub. Includes Terraform via `tfenv` so you can pin a Terraform version at runtime with `-e TFENV_TERRAFORM_VERSION=1.9.8`.

---

## Troubleshooting

### "dot command not found"

Graphviz isn't installed. See [Troubleshooting → Graphviz Not Found](troubleshooting.md).

### "terraform plan" fails inside TerraVision

TerraVision runs `terraform init` and `terraform plan` using your normal Terraform setup, so a plan failure inside TerraVision means the plan would fail outside it too. Run `terraform plan` yourself to debug, then retry. If plan succeeds but TerraVision still fails, that's a TerraVision bug — please open an issue.

### My diagram is too large / unreadable

Try `--simplified` to collapse networking infrastructure and focus on core services. For very large projects, generate per-module diagrams:

```bash
terravision draw --source ./path-to-your-terraform/modules/vpc --outfile arch-vpc
terravision draw --source ./path-to-your-terraform/modules/app --outfile arch-app
```

### More issues

See the [Troubleshooting Guide](troubleshooting.md) for a longer list of common problems and solutions.

---

## Still stuck?

- Open an [issue on GitHub](https://github.com/patrickchugh/terravision/issues)
- Ask on [GitHub Discussions](https://github.com/patrickchugh/terravision/discussions)
