# TerraVision

**Turn Terraform code into professional cloud architecture diagrams that stay in sync with your infrastructure — automatic, secure, living documents**

[![lint-and-test](https://github.com/patrickchugh/terravision/actions/workflows/lint-and-test.yml/badge.svg)](https://github.com/patrickchugh/terravision/actions/workflows/lint-and-test.yml)
[![PyPI version](https://img.shields.io/pypi/v/terravision?style=flat-square)](https://pypi.org/project/terravision/)
[![PyPI downloads](https://img.shields.io/pypi/dm/terravision?style=flat-square)](https://pypi.org/project/terravision/)
[![Python version](https://img.shields.io/pypi/pyversions/terravision?style=flat-square)](https://pypi.org/project/terravision/)
[![GitHub stars](https://img.shields.io/github/stars/patrickchugh/terravision?style=flat-square)](https://github.com/patrickchugh/terravision/stargazers)
[![License](https://img.shields.io/github/license/patrickchugh/terravision?style=flat-square)](https://github.com/patrickchugh/terravision/blob/main/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)

**📖 [Full documentation site →](https://patrickchugh.github.io/terravision/)**

---

## Watch a 2-Minute Intro

[![TerraVision intro video](https://img.youtube.com/vi/bTrWHBI2mF4/maxresdefault.jpg)](https://youtu.be/bTrWHBI2mF4)

---
## What is TerraVision?

TerraVision automatically converts your Terraform code into professional-grade cloud architecture diagrams using the official AWS, GCP, and Azure icon sets. Your diagrams stay in sync with your infrastructure — no more outdated Visio, draw.io or Lucidchart files.

## Why TerraVision?

- ✅ **Always up-to-date** — diagrams generated directly from your Terraform code
- ✅ **100% client-side** — no cloud access required, runs locally, your code never leaves your machine
- ✅ **CI/CD ready** — automate diagram updates on every PR merge
- ✅ **Free & open source** — no expensive diagramming tool licenses
- ✅ **Multi-cloud** — AWS (full), GCP, and Azure (core services)
- ✅ **Interactive HTML output** — clickable nodes, pan/zoom, search, animated data flow
- ✅ **Editable draw.io export** — open in draw.io, Lucidchart, or any mxGraph editor
- ✅ **Optional AI annotations** — labels, titles, and flow sequences from Ollama (local) or AWS Bedrock
- ✅ **Terragrunt compatible** — auto-detects single- and multi-module Terragrunt projects

---

## Supported Cloud Providers

| Provider         | Status             | Resources     |
| ---------------- | ------------------ | ------------- |
| **AWS**          | ✅ Full support    | 200+ services |
| **Google Cloud** | 🔄 Partial support | Core services |
| **Azure**        | 🔄 Partial support | Core services |

---

## Quick Start

### Install

```bash
pipx install terravision   # or: pip install terravision if in a virtual env
```

You also need **Python 3.10+**, **Terraform 1.x**, **Graphviz**, and **Git**. See the [Installation Guide](https://patrickchugh.github.io/terravision/installation/) for platform-specific instructions, Docker, and Nix.

### Generate your first diagram

```bash
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# EKS cluster example
terravision draw --source tests/fixtures/aws_terraform/eks_automode --show

# Azure VM scale set
terravision draw --source tests/fixtures/azure_terraform/test_vm_vmss --show

# From a public Git repo (note the // for subfolder)
terravision draw --source https://github.com/patrickchugh/terraform-examples.git//aws/wordpress_fargate --show
```

That's it — your diagram is saved as `architecture.png` and opens automatically.

### Generate an interactive HTML diagram

```bash
terravision visualise --source ./path-to-your-terraform --show
```

Click any resource to see its Terraform metadata, search resources, pan/zoom, and watch animated data flow on edges. The HTML is a single self-contained file that works fully offline.

---

## Try the Interactive Demos

Click any of these to see the interactive HTML output TerraVision produces:

- 🟧 **[AWS demo](https://patrickchugh.github.io/terravision/demo-aws.html)** — Wordpress on ECS Fargate with CloudFront, RDS, EFS
- 🟦 **[Azure demo](https://patrickchugh.github.io/terravision/demo-azure.html)** — VM scale set with load balancer and VNet
- 🟩 **[GCP demo](https://patrickchugh.github.io/terravision/demo-gcp.html)** — Core GCP networking and compute

---

## Basic Usage

### Generate a diagram

```bash
# From a local directory
terravision draw --source ./path-to-your-terraform

# From a Git repository
terravision draw --source https://github.com/user/repo.git

# Custom format and filename
terravision draw --source ./path-to-your-terraform --format svg --outfile my-architecture

# Editable draw.io file
terravision draw --source ./path-to-your-terraform --format drawio --outfile my-architecture
```

### Use a pre-generated Terraform plan (no cloud credentials needed)

```bash
# Step 1: in your Terraform environment
terraform plan -out=tfplan.bin
terraform show -json tfplan.bin > plan.json
terraform graph > graph.dot

# Step 2: diagram generation, no Terraform or cloud access required
terravision draw --planfile plan.json --graphfile graph.dot --source ./path-to-your-terraform
```

### AI-powered annotations (optional)

```bash
terravision draw --source ./path-to-your-terraform --ai-annotate ollama   # local LLM
terravision draw --source ./path-to-your-terraform --ai-annotate bedrock  # AWS Bedrock
```

Only metadata and the summary graph are sent to the LLM — never your `.tf` source. See [Annotations Guide](https://patrickchugh.github.io/terravision/annotations/).

### Simplified view

```bash
terravision draw --source ./path-to-your-terraform --simplified
```

Strips VPCs, subnets, and networking plumbing. Great for executive presentations.

### Common options

``terravision --help`` shows full help text details. 

| Option          | Description                                                                | Example                             |
| --------------- | -------------------------------------------------------------------------- | ----------------------------------- |
| `--source`      | Terraform directory or Git URL                                             | `./path-to-your-terraform`                       |
| `--format`      | Output format: `png`, `svg`, `pdf`, `drawio`, [and more][formats]          | `svg`                               |
| `--outfile`     | Output filename                                                            | `my-architecture`                   |
| `--workspace`   | Terraform workspace                                                        | `production`                        |
| `--varfile`     | Variable file (repeatable)                                                 | `prod.tfvars`                       |
| `--planfile`    | Pre-generated plan JSON                                                    | `plan.json`                         |
| `--graphfile`   | Pre-generated graph DOT                                                    | `graph.dot`                         |
| `--ai-annotate` | AI annotation backend                                                      | `ollama`, `bedrock`                 |
| `--simplified`  | High-level view (no networking)                                            | (flag)                              |
| `--show`        | Open after generation                                                      | (flag)                              |

[formats]: https://patrickchugh.github.io/terravision/usage-guide/#output-formats

---

## Documentation

The complete documentation lives at **[patrickchugh.github.io/terravision](https://patrickchugh.github.io/terravision/)**.

**For users:**
- [Installation Guide](docs/installation.md)
- [Usage Guide](docs/usage-guide.md)
- [Annotations Guide](docs/annotations.md)
- [CI/CD Integration](docs/cicd-integration.md)
- [FAQ](docs/faq.md)
- [Troubleshooting](docs/troubleshooting.md)

**For contributors:**
- [Contributing Guide](docs/CONTRIBUTING.md)
- [Developer Guide](docs/developer-guide.md)
- [Resource Handler Guide](docs/resource-handler-guide.md)
- [Project Constitution](docs/constitution.md)

---

## FAQ

Common questions — cloud credentials, LLM data privacy, offline use, Terragrunt, output formats, and more — are answered in the **[FAQ on the documentation site](https://patrickchugh.github.io/terravision/faq/)**.

---

## Contributing

Contributions are very welcome. See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development setup, coding standards, and the PR process.

## Support

- **Issues**: [GitHub Issues](https://github.com/patrickchugh/terravision/issues)
- **Discussions**: [GitHub Discussions](https://github.com/patrickchugh/terravision/discussions)
- **Documentation**: [patrickchugh.github.io/terravision](https://patrickchugh.github.io/terravision/)

## License

See [LICENSE](LICENSE).

## Acknowledgments

- [Graphviz](https://graphviz.org/) — diagram rendering
- [Terraform](https://www.terraform.io/) — infrastructure parsing
- [Terragrunt](https://terragrunt.gruntwork.io/) — multi-module orchestration
- Cloud provider icons from official AWS, GCP, and Azure icon sets
