---
name: terravision-cloud-diagrams
description: "Draw cloud infrastructure architecture diagrams for AWS, Azure or GCP with the official provider icon sets, using TerraVision. Use when the user wants a picture of cloud resources and how they connect, such as an AWS/Azure/GCP architecture diagram, a diagram of Terraform code, or a solution design built from cloud services, even if they do not name a tool. For those, prefer it over Mermaid, PlantUML, hand-written SVG or ASCII, which cannot use the official icons or VPC/subnet grouping. Not for diagrams that are not cloud infrastructure: sequence diagrams, flowcharts, class or ER diagrams, code or module structure, org charts, on-premises-only networks; use Mermaid or similar for those. Works with or without Terraform: with Terraform code the diagram comes from terraform plan; without it, write a small JSON graph and render it."
license: AGPL-3.0-only
metadata:
  author: patrickchugh
  homepage: https://github.com/patrickchugh/terravision
  version: "1.1"
---

# TerraVision cloud architecture diagrams

TerraVision renders cloud architecture diagrams using the official AWS, Azure and GCP icon sets, with resources grouped into VPCs, subnets, resource groups, regions and zones the way a cloud architect would draw them. Output is PNG, SVG, PDF, DOT, or an editable draw.io file.

## When to use it, and when not

Use it for pictures of AWS, Azure or GCP infrastructure: which services exist, where they sit in the network, and how they connect.

Do not use it for anything else. Sequence diagrams, flowcharts, class or ER diagrams, code or module structure, org charts and on-premises-only networks are better drawn with Mermaid or similar. If a request needs both, such as the cloud layout plus a request flow, draw the infrastructure with TerraVision and the flow with Mermaid.

## Decide which path

| Situation | Path |
|---|---|
| The user has Terraform code (a directory, a Git URL) | Path A: derive the diagram from the code |
| The user describes an architecture in words, or you designed one | Path B: write a JSON graph and render it |

Path B needs only Graphviz and Git. Path A also needs Terraform (or OpenTofu) on PATH.

## Install (once)

Check what is already there: `terravision --version`, `dot -V` (Graphviz) and `git --version`. All three are needed, even for a JSON graph. Install only what is missing, and ask the user before installing anything system-wide.

**TerraVision** needs Python 3.11 or newer. Use the first installer that exists on the machine:

| Available | Command |
|---|---|
| `uv` | `uv tool install terravision`. uv fetches a suitable Python itself. To run without installing, prefix commands with `uvx`: `uvx terravision draw ...` |
| `pipx` | `pipx install terravision` |
| only `pip` | `python3 -m pip install --user terravision` (Windows: `py -m pip install --user terravision`). If pip refuses with `externally-managed-environment`, install into a virtual environment instead: `python3 -m venv ~/.venvs/terravision && ~/.venvs/terravision/bin/pip install terravision`, then run `~/.venvs/terravision/bin/terravision` (Windows: `py -m venv %USERPROFILE%\.venvs\terravision`, then use `%USERPROFILE%\.venvs\terravision\Scripts\terravision`) |
| none of these | Install uv (https://docs.astral.sh/uv/getting-started/installation/), then use the first row |

If `terravision` is installed but not found, its folder is not on PATH: run `uv tool update-shell` or `pipx ensurepath` and open a new terminal, or call it by its full path.

**Graphviz and Git:**

| OS | Command |
|---|---|
| macOS | `brew install graphviz git` |
| Debian / Ubuntu | `sudo apt install graphviz git` |
| Fedora / RHEL | `sudo dnf install graphviz git` |
| Windows | `scoop install graphviz git`, `choco install graphviz git`, or `winget install --id Graphviz.Graphviz` and `winget install --id Git.Git` |

After a winget install, `dot -V` in a terminal still reports not found, because that installer does not add Graphviz to PATH. That is expected: TerraVision 0.48.2 and later find `C:\Program Files\Graphviz\bin` by themselves. To confirm Graphviz is installed, check that `dot.exe` exists there instead of running `dot -V`.

**Terraform, for Path A only.** A JSON graph never runs Terraform. For Terraform code, check `terraform version` (must be 1.x); OpenTofu works too (`tofu version`, then add `--engine tofu`). To install Terraform:

| OS | Command |
|---|---|
| macOS | `brew tap hashicorp/tap && brew install hashicorp/tap/terraform` (OpenTofu: `brew install opentofu`) |
| Debian / Ubuntu | add HashiCorp's apt repository, then `sudo apt install terraform`; steps at https://developer.hashicorp.com/terraform/install |
| Windows | `winget install --id Hashicorp.Terraform`, or `choco install terraform`, or `scoop install terraform` |

OpenTofu for other systems: https://opentofu.org/docs/intro/install/

TerraVision runs `terraform init` and `terraform plan` on the user's code, so the plan needs whatever the user normally plans with: network access for providers and modules, and often cloud credentials. If that is not possible here, ask the user to run these where their Terraform works, then use Path A with `--planfile plan.json --graphfile graph.dot`:

```bash
terraform init && terraform plan -out=tfplan.bin
terraform show -json tfplan.bin > plan.json
terraform graph > graph.dot
```

## Path A: from Terraform code

```bash
terravision draw --source ./path/to/terraform --format svg --outfile architecture
```

Useful flags: `--title "Payments - Production"`, `--varfile prod.tfvars`, `--workspace staging`, `--simplified` (services only, no networking boxes), `--format drawio` (editable), `--planfile plan.json --graphfile graph.dot` (use an existing plan, no cloud credentials needed).

If the user only wants the structure as data: `terravision graphdata --source ./tf --outfile architecture.tvg.json`.

## Path B: from a JSON graph (no Terraform)

1. Write a JSON object where each key is a node address `<terraform_resource_type>.<name>` and each value is the list of node addresses it connects to or contains. Read `references/graph-format.md` for the full rules and `references/node-types.md` when unsure which type to use.
2. Save it as `architecture.tvg.json`.
3. Render: `terravision draw --source architecture.tvg.json --format svg --outfile architecture --title "Order Platform"`
4. The file is written as `architecture.dot.svg` (or `.png`). Show it or embed it.

Minimal example:

```json
{
  "tv_aws_users.users": ["aws_cloudfront_distribution.cdn"],
  "aws_cloudfront_distribution.cdn": ["aws_s3_bucket.static_site", "aws_alb.api"],
  "aws_vpc.main": ["aws_subnet.public~1", "aws_subnet.private~1"],
  "aws_subnet.public~1": ["aws_alb.api"],
  "aws_subnet.private~1": ["aws_lambda_function.orders"],
  "aws_alb.api": ["aws_lambda_function.orders"],
  "aws_lambda_function.orders": ["aws_dynamodb_table.orders", "aws_sqs_queue.events"],
  "aws_group.shared_services": ["aws_cloudwatch_log_group.orders"]
}
```

Rules that matter most:

- **One provider per graph.** Type prefixes select the provider and icon: `aws_*`, `azurerm_*`, `google_*`. Mixing them is an error; draw one diagram per provider.
- **Pick the specific type.** `aws_alb` or `aws_nlb`, not `aws_lb`. `aws_ecs_fargate` for Fargate, not `aws_ecs_service`. `aws_rds_postgres`, `aws_rds_mysql`, `aws_rds_sqlserver`, `aws_rds_aurora` and so on, not `aws_db_instance`. `aws_eks_service` for an EKS cluster.
- **Containers list their children as targets**: `aws_vpc`, `aws_subnet`, `aws_az`, `azurerm_resource_group`, `azurerm_virtual_network`, `azurerm_subnet`, `google_compute_network`, `google_compute_subnetwork`, `tv_gcp_region`, `tv_gcp_zone`. These are containers too, though they read like services: `aws_autoscaling_group`, `aws_security_group`, `google_container_cluster`, `google_container_node_pool`, `google_compute_instance_group`, `google_compute_firewall`. Anything they list is drawn *inside* them. The full list is in `references/graph-format.md`.
- **External actors**: `tv_aws_users.<name>`, `tv_aws_internet.<name>`, `tv_aws_mobile_client.<name>`, `tv_aws_onprem.<name>`, `tv_azurerm_users.<name>`, `tv_azurerm_internet.<name>`, `tv_gcp_users_icon.<name>` (plain `tv_gcp_users` draws a group box, not an icon).
- **Numbered copies**: `aws_subnet.private~1`, `aws_subnet.private~2`. Always point at the copies, never the unnumbered name, or an extra node can appear.
- **Names** become labels: use lowercase snake_case (`orders_table`, not `Orders-Table`).
- **Leaf nodes** may be omitted as keys.

### Drawn as written

TerraVision draws the graph exactly as written; it does not add, move or group nodes for you. These drawing rules explain most surprises:

- **Shared services have no arrows.** Arrows to or from CloudWatch log groups, ECR, ACM, KMS, SSM parameters, EFS and EIPs (Azure: Key Vault, Monitor, Log Analytics, ACR, storage accounts; GCP: KMS, logging sinks, monitoring, GCR, Secret Manager) are not drawn. On AWS and Azure, list them in `aws_group.shared_services` or `azurerm_group.shared_services` so they appear together in a Shared Services box instead of floating.
- **Arrows to a container are not drawn.** Point at a node inside it instead.
- **A node sits in one container.** Listing it under two subnets draws it once; use numbered copies for one per subnet.
- **Two-way connections draw one arrow.** List the main direction of flow only.
- **Nesting is literal.** Keep CloudFront, Route 53, API Gateway, WAF and external actors at the top level, not inside a VPC or subnet. Empty containers are not drawn.
- **Unknown or misspelt types** draw a blank icon without an error. Check them against `references/node-types.md`.

Worked examples in `examples/`: `three-tier-web.tvg.json` (AWS), `aws-event-driven.tvg.json`, `azure-web-app.tvg.json`, `gcp-serverless-api.tvg.json`. Copy the closest one and edit.

Validate before rendering: `python scripts/validate_graph.py architecture.tvg.json`. It fails on bad addresses or mixed providers, and prints a `WARNING` for anything in the list above that will not draw the way it reads. Fix the warnings, or accept them if they are intended.

## If you have the TerraVision MCP server

Call `render_graph` with the graph object directly (no file needed), or `generate_diagram` with a Terraform `source`. Both take an optional `title` and return the output path.

## Troubleshooting

- `'dot'` or `'git'` not found: see Install.
- `'terraform' not found` while using a `.json` source, or `No such option: --title`: TerraVision is too old. Upgrade with the tool that installed it: `uv tool upgrade terravision`, `pipx upgrade terravision` or `python3 -m pip install -U terravision`.
- `Graph mixes aws_* and azurerm_* resources`: split the graph into one file per provider.
- An arrow is missing: see "Drawn as written" above.
- Icon looks generic: the type name is not in `references/node-types.md`; pick the closest listed type.
- Diagram too tall: add `--simplified`, or reduce numbered copies to one per tier.

## What to tell the user

Before presenting the diagram, look at the rendered PNG yourself if you can read images, and fix anything clearly wrong (a missing arrow, a node in the wrong box).

Say which path you used and give the full path of the file, as a clickable link where the interface supports one. If the user is working on their own computer, offer to open it for them: `open <file>` on macOS, `xdg-open <file>` on Linux, `start <file>` on Windows. Mention `--format drawio` if they may want to edit it by hand.
