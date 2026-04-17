---
hide:
  - navigation
  - toc
---

# TerraVision

**Turn Terraform code into professional cloud architecture diagrams that stay in sync with your infrastructure — automatic, secure, living documents**

[![PyPI version](https://img.shields.io/pypi/v/terravision?style=flat-square)](https://pypi.org/project/terravision/)
[![PyPI downloads](https://img.shields.io/pypi/dm/terravision?style=flat-square)](https://pypi.org/project/terravision/)
[![Python version](https://img.shields.io/pypi/pyversions/terravision?style=flat-square)](https://pypi.org/project/terravision/)
[![License](https://img.shields.io/github/license/patrickchugh/terravision?style=flat-square)](https://github.com/patrickchugh/terravision/blob/main/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)

---

## Watch a 4-Minute Intro

<iframe
  src="https://www.youtube-nocookie.com/embed/bTrWHBI2mF4"
  style="width: 100%; max-width: 800px; aspect-ratio: 16 / 9; display: block; margin: 0 auto; border: 0;"
  title="TerraVision introduction"
  allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
</iframe>

---

## From Terraform Code → Architecture Diagram

=== "Input: Terraform"

    ![Terraform Code](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/code.png)

=== "Output: AWS"

    ![AWS architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/architecture.png)

=== "Output: Azure"

    ![Azure architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/architecture-azure.dot.png)

=== "Output: GCP"

    ![GCP architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/architecture-gcp.dot.png)

---

## Why TerraVision?

<div class="grid cards" markdown>

-   :material-sync-circle:{ .lg .middle } **Always up-to-date**

    ---

    Diagrams generated directly from your Terraform code — no more drift between docs and reality.

-   :material-shield-lock:{ .lg .middle } **100% client-side**

    ---

    No cloud access required. Runs locally. Your `.tf` code never leaves your machine.

-   :material-pipe:{ .lg .middle } **CI/CD ready**

    ---

    Automate diagram updates on every PR merge. Works with GitHub Actions, GitLab, Jenkins, Azure DevOps.

-   :material-cloud:{ .lg .middle } **Multi-cloud**

    ---

    AWS (full), GCP, and Azure (core services) — including multi-cloud architectures on a single diagram.

-   :material-cursor-default-click:{ .lg .middle } **Interactive HTML**

    ---

    `terravision visualise` produces a self-contained HTML with clickable nodes, search, and animated data flow.

-   :material-pencil:{ .lg .middle } **Editable draw.io**

    ---

    Export to `.drawio` and open in draw.io, Lucidchart, or any mxGraph editor.

-   :material-robot:{ .lg .middle } **Optional AI annotations**

    ---

    Auto-generate labels, titles, and flow sequences from Ollama (local) or AWS Bedrock.

-   :material-source-merge:{ .lg .middle } **Terragrunt compatible**

    ---

    Auto-detects single- and multi-module Terragrunt projects. No extra flags needed.

</div>

---

## Quick Start

Install with pip:

```bash
pip install terravision   # or: pipx install terravision
```

Generate your first diagram:

```bash
terravision draw --source ./path-to-your-terraform --show
```

Or try the interactive HTML output:

```bash
terravision visualise --source ./path-to-your-terraform--show
```

See the [Installation Guide](installation.md) for Docker, Nix, and platform-specific instructions, or jump straight into the [Usage Guide](usage-guide.md).

---

## Try the Interactive Demos

These are real outputs of `terravision visualise` — click any node to see its metadata, use the search box, and pan/zoom around.

<div class="grid cards" markdown>

-   🟧 **[AWS demo](demo-aws.html)**

    ---

    Wordpress on ECS Fargate with CloudFront, RDS, and EFS.

-   🟦 **[Azure demo](demo-azure.html)**

    ---

    VM scale set with load balancer and VNet topology.

-   🟩 **[GCP demo](demo-gcp.html)**

    ---

    Core GCP networking and compute.

</div>

---

## Documentation

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **[Installation](installation.md)**

    ---

    Install via pip, Docker, or Nix. Platform-specific instructions for all dependencies.

-   :material-book-open:{ .lg .middle } **[Usage Guide](usage-guide.md)**

    ---

    All commands, options, output formats, and advanced usage patterns.

-   :material-tag-text:{ .lg .middle } **[Annotations](annotations.md)**

    ---

    Customise your diagrams with YAML annotations, flows, and AI suggestions.

-   :material-source-branch:{ .lg .middle } **[CI/CD Integration](cicd-integration.md)**

    ---

    Automate diagrams in GitHub Actions, GitLab, Jenkins, Azure DevOps.

-   :material-help-circle:{ .lg .middle } **[FAQ](faq.md)**

    ---

    Cloud credentials, LLM data, offline use, Terragrunt — the most common questions.

-   :material-wrench:{ .lg .middle } **[Troubleshooting](troubleshooting.md)**

    ---

    Common errors and how to fix them.

</div>

---

## Support

- **Issues**: [GitHub Issues](https://github.com/patrickchugh/terravision/issues)
- **Discussions**: [GitHub Discussions](https://github.com/patrickchugh/terravision/discussions)
- **Source code**: [github.com/patrickchugh/terravision](https://github.com/patrickchugh/terravision)
