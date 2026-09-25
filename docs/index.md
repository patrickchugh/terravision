---
hide:
  - navigation
  - toc
---

# TerraVision

**Turn Terraform or JSON files into professional cloud architecture diagrams with the official AWS, Azure and GCP icons**

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

## From JSON or Terraform → Architecture Diagram

=== "Input: JSON graph"

    No Terraform needed: each key is `<terraform_resource_type>.<name>`, each value is what it connects to or contains. See the [Graph Format](graph-format.md).

    ```json
    {
      "tv_aws_users.users": ["aws_cloudfront_distribution.cdn"],
      "aws_cloudfront_distribution.cdn": ["aws_s3_bucket.static_assets", "aws_alb.web_alb~1", "aws_alb.web_alb~2"],
      "aws_s3_bucket.static_assets": [],
      "aws_vpc.main": ["aws_az.us_east_1a", "aws_az.us_east_1b", "aws_internet_gateway.igw"],
      "aws_az.us_east_1a": ["aws_subnet.public~1", "aws_subnet.private~1", "aws_subnet.data~1"],
      "aws_az.us_east_1b": ["aws_subnet.public~2", "aws_subnet.private~2", "aws_subnet.data~2"],
      "aws_subnet.public~1": ["aws_alb.web_alb~1", "aws_nat_gateway.nat~1"],
      "aws_subnet.public~2": ["aws_alb.web_alb~2", "aws_nat_gateway.nat~2"],
      "aws_subnet.private~1": ["aws_instance.app~1"],
      "aws_subnet.private~2": ["aws_instance.app~2"],
      "aws_subnet.data~1": ["aws_db_instance.postgres~1"],
      "aws_subnet.data~2": ["aws_db_instance.postgres~2"],
      "aws_alb.web_alb~1": ["aws_instance.app~1"],
      "aws_alb.web_alb~2": ["aws_instance.app~2"],
      "aws_instance.app~1": ["aws_db_instance.postgres~1", "aws_elasticache_cluster.sessions"],
      "aws_instance.app~2": ["aws_db_instance.postgres~1", "aws_elasticache_cluster.sessions"],
      "aws_db_instance.postgres~1": ["aws_db_instance.postgres~2"],
      "aws_db_instance.postgres~2": [],
      "aws_elasticache_cluster.sessions": [],
      "aws_nat_gateway.nat~1": ["aws_internet_gateway.igw"],
      "aws_nat_gateway.nat~2": ["aws_internet_gateway.igw"],
      "aws_internet_gateway.igw": ["tv_aws_internet.internet"]
    }
    ```

=== "Output: from JSON"

    ![AWS three-tier web app diagram rendered from JSON](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/three-tier-web.png)

=== "Input: Terraform"

    ```hcl
    # Excerpt from WordPress on ECS Fargate (the AWS output tab)
    # Full source: https://github.com/patrickchugh/terraform-examples/tree/main/aws/wordpress_fargate

    module "vpc" {
      source                 = "terraform-aws-modules/vpc/aws"
      cidr                   = var.vpc_cidr
      azs                    = data.aws_availability_zones.this.names
      private_subnets        = var.private_subnet_cidrs
      public_subnets         = var.public_subnet_cidrs
      enable_nat_gateway     = true
      single_nat_gateway     = false
    }

    module "alb" {
      source             = "terraform-aws-modules/alb/aws"
      load_balancer_type = "application"
      vpc_id             = module.vpc.vpc_id
      subnets            = module.vpc.public_subnets
      security_groups    = [aws_security_group.alb.id]
    }

    resource "aws_cloudfront_distribution" "this" {
      origin {
        domain_name = module.alb.this_lb_dns_name
        origin_id   = "alb"
      }
      # ...
    }

    resource "aws_ecs_service" "this" {
      cluster         = aws_ecs_cluster.this.id
      task_definition = aws_ecs_task_definition.this.arn
      launch_type     = "FARGATE"
      network_configuration {
        security_groups = [aws_security_group.alb.id, aws_security_group.db.id, aws_security_group.efs.id]
        subnets         = module.vpc.private_subnets
      }
      load_balancer {
        target_group_arn = aws_lb_target_group.this.id
        container_name   = "wordpress"
        container_port   = 80
      }
    }

    resource "aws_rds_cluster" "this" {
      engine                 = "aurora-mysql"
      engine_mode            = "serverless"
      vpc_security_group_ids = [aws_security_group.db.id]
      db_subnet_group_name   = aws_db_subnet_group.this.name
    }

    resource "aws_efs_file_system" "this" {}

    resource "aws_efs_mount_target" "this" {
      count           = length(module.vpc.private_subnets)
      file_system_id  = aws_efs_file_system.this.id
      subnet_id       = module.vpc.private_subnets[count.index]
      security_groups = [aws_security_group.efs.id]
    }
    ```

=== "Output: AWS"

    ![AWS architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/architecture.png)

=== "Output: Azure"

    ![Azure architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/architecture-azure.dot.png)

=== "Output: GCP"

    ![GCP architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/images/architecture-gcp.dot.png)

---

## Why TerraVision?

<div class="grid cards" markdown>

-   :material-code-json:{ .lg .middle } **JSON graph input**

    ---

    Describe an architecture in a few lines of JSON and render it. Resources match Terraform names, so there's no custom DSL to learn. See the [Graph Format](graph-format.md).

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
