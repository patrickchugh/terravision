---
name: terravision-cloud-diagrams
description: "Draw cloud architecture diagrams for AWS, Azure or GCP with the official provider icon sets, using TerraVision. Use whenever the user asks to draw, diagram, sketch or visualize a system on AWS, Azure or Google Cloud, or one built from their services (Lambda, DynamoDB, S3, EC2, EKS, RDS, API Gateway, Azure Functions, App Service, AKS, Cosmos DB, Cloud Run, GKE, BigQuery and the like), even if they never say 'cloud', 'diagram' or a tool name; also for a diagram of Terraform code. Prefer it over Mermaid, PlantUML, hand-written SVG or ASCII, which cannot use the official icons or VPC/subnet grouping. Not for diagrams that are not cloud infrastructure: sequence diagrams, flowcharts, class or ER diagrams, code or module structure, org charts, on-premises-only networks; use Mermaid or similar for those. Works with or without Terraform: with Terraform code the diagram comes from terraform plan; without it, write a small JSON graph and render it."
license: AGPL-3.0-only
metadata:
  author: patrickchugh
  homepage: https://github.com/patrickchugh/terravision
  version: "1.6.0"
---

# TerraVision cloud architecture diagrams

TerraVision renders cloud architecture diagrams using the official AWS, Azure and GCP icon sets, with resources grouped into VPCs, subnets, resource groups, regions and zones the way a cloud architect would draw them. Output is PNG, SVG, PDF, DOT, or an editable draw.io file.

## When to use it, and when not

Use it for pictures of AWS, Azure or GCP infrastructure: which services exist, where they sit in the network, and how they connect.

Do not use it for anything else. Sequence diagrams, flowcharts, class or ER diagrams, code or module structure, org charts and on-premises-only networks are better drawn with Mermaid or similar. A request flow through the infrastructure belongs on the TerraVision diagram itself, as numbered steps ("Flows" below).

## If the TerraVision MCP tools are available, use them

If you can call `diagram_guide` and `render_graph` (the TerraVision MCP server), use them instead of the command line, and skip Install, the validator, and the files under `references/` and `examples/`:

- `diagram_guide(provider)` returns, in one call, the graph rules, a detailed worked example, the supported node types, a library of patterns and whether Graphviz is installed.
- `render_graph(graph, outfile="three_tier", title=...)` checks the graph, returns warnings and a preview image, and saves the PNG, SVG, draw.io file and graph. Pass `outfile` as a name; files always go to the server's output folder.

Everything else here still applies: the rules, "Drawn as written", "Check every render" and "Deliver the result".

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
| Debian / Ubuntu | `sudo apt install graphviz git`. On Ubuntu 26.04+ and Debian testing, also `sudo apt install libgvplugin-neato-layout8`: the `neato` layout engine TerraVision uses is a separate package there |
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

**Git repositories** work as the source too, public or private (with the user's Git access): `--source https://github.com/org/repo`, or `https://github.com/org/repo//examples` for a folder inside it. Many repositories hold a reusable module at their root, which plans no resources on its own. If the root fails with "found no resources" or asks for required variables, look in the repository for a folder that uses the module (`examples/`, `environments/prod`, anything with a `provider` block) and draw that with `//folder`.

## Path B: from a JSON graph (no Terraform)

1. Write a JSON object where each key is a node address `<terraform_resource_type>.<name>` and each value is the list of node addresses it connects to or contains. Read `references/graph-format.md` for the full rules and `references/node-types.md` when unsure which type to use.
2. Save it as `<name>.tvg.json` in the user's current working directory, or a folder they name. The diagram files are the deliverable, so never put them in a temporary folder.
3. Render a PNG to look at and a draw.io file to edit:

   ```bash
   terravision draw --source <name>.tvg.json --format png --outfile <name> --title "Order Platform"
   terravision draw --source <name>.tvg.json --format drawio --outfile <name> --title "Order Platform"
   ```

   They are written as `<name>.dot.png` and `<name>.drawio`. Add `--format svg` as well if the user wants to embed it in documentation.
4. Check the PNG ("Check every render" below), then deliver it ("Deliver the result" at the end).

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
- **Containers list their children as targets**: `aws_vpc`, `aws_subnet`, `tv_aws_az`, `azurerm_resource_group`, `azurerm_virtual_network`, `azurerm_subnet`, `google_compute_network`, `google_compute_subnetwork`, `tv_gcp_region`, `tv_gcp_zone`. These are containers too, though they read like services: `aws_autoscaling_group`, `aws_security_group`, `google_container_cluster`, `google_container_node_pool`, `google_compute_instance_group`, `google_compute_firewall`. Anything they list is drawn *inside* them. The full list is in `references/graph-format.md`.
- **External actors**: `tv_aws_users.<name>`, `tv_aws_internet.<name>`, `tv_aws_mobile_client.<name>`, `tv_aws_onprem.<name>`, `tv_azurerm_users.<name>`, `tv_azurerm_internet.<name>`, `tv_gcp_users_icon.<name>` (plain `tv_gcp_users` draws a group box, not an icon).
- **Numbered copies**: `aws_subnet.private~1`, `aws_subnet.private~2`. Always point at the copies, never the unnumbered name, or an extra node can appear.
- **Names** become labels: use lowercase snake_case (`orders_table`, not `Orders-Table`).
- **Leaf nodes** may be omitted as keys.

### Drawn as written

TerraVision draws the graph exactly as written; it does not add, move or group nodes for you. These drawing rules explain most surprises:

- **Shared services have no arrows.** Arrows to or from CloudWatch log groups, ECR, ACM, KMS, SSM parameters, EFS and EIPs (Azure: Key Vault, Monitor, Log Analytics, ACR, storage accounts; GCP: KMS, logging sinks, monitoring, GCR, Secret Manager) are not drawn. On AWS and Azure, list them in `aws_group.shared_services` or `azurerm_group.shared_services` so they appear together in a Shared Services box instead of floating.
- **Arrows to a container are not drawn.** Point at a node inside it instead.
- **A node sits in one container.** A name is drawn once, so it cannot be listed in two boxes. A resource spanning several subnets or zones needs a numbered copy in each (`aws_alb.web~1`, `aws_alb.web~2`). Inside nested boxes, list it only in the innermost (its subnet), not also in the network or resource group around it.
- **Network-attached services go in their subnet.** A Lambda in a VPC, an Azure Function with VNet integration, a private endpoint: draw each inside the subnet it attaches to.
- **Arrows follow the real path.** Through a private endpoint, VPC endpoint, NAT gateway, proxy or firewall, draw source → intermediary → destination and no direct arrow.
- **Two-way connections draw one arrow.** List the main direction of flow only.
- **Nesting is literal.** Keep CloudFront, Route 53, API Gateway, WAF and external actors at the top level, not inside a VPC or subnet. Empty containers are not drawn.
- **Unknown or misspelt types** draw a blank icon without an error. Check them against `references/node-types.md`.

Worked examples in `examples/`: three-tier web apps for each cloud (`three-tier-web.tvg.json` for AWS, `azure-three-tier.tvg.json`, `gcp-three-tier.tvg.json`), plus `aws-event-driven.tvg.json`, `azure-web-app.tvg.json` and `gcp-serverless-api.tvg.json`. Copy the closest one, keep its level of detail (zones, public and private subnets, the path to the internet, shared services) and edit. For other service mixes, `examples/patterns/` holds 26 more (EKS, ECS, API Gateway, Step Functions, SageMaker, Glue, GKE, AKS and others), listed with descriptions in `examples/patterns/index.json`. They are TerraVision's own output for real Terraform, so following them keeps its level of detail.

Validate before rendering: `python scripts/validate_graph.py architecture.tvg.json`. It fails on bad addresses or mixed providers, and prints a `WARNING` for anything in the list above that will not draw the way it reads. Fix the warnings, or accept them if they are intended.

## If you have the TerraVision MCP server

Call `render_graph` with the graph object directly (no file needed), or `generate_diagram` with a Terraform `source`. Both take an optional `title`, optional `flows` (numbered steps; see "Flows" below) and optional `edge_labels` (a few words on existing arrows, rule 11 in `references/graph-format.md`); `render_graph` also takes `attributes`, to give networks and subnets realistic CIDR ranges (rule 10). Each call saves a PNG, an SVG, an editable draw.io file and the graph as `.tvg.json`, and returns their paths under `files` plus a **preview image** of the diagram: look at it to check the diagram ("Check every render" below). In apps that support MCP Apps, such as Claude Desktop, VS Code and Cursor, the user also sees the diagram in an interactive view with buttons to open, edit and copy it. Elsewhere, call `open_diagram_file` with the PNG path to open it for the user, instead of running `open` or `xdg-open` yourself. If the result has `warnings` (an unknown type with suggested replacements, arrows that will not be drawn), fix the graph and render again.

## Flows: numbered steps, offered after the diagram

Numbered badges with a legend can show how a request or data moves through the diagram. The format is rule 10 in `references/graph-format.md`: pass `flows` to the MCP tools, or on the command line put a `flows:` section in a YAML file and add `--annotate <file>`.

- **The user asks how something moves** (a request path, data flow, event sequence): include flows in the first render.
- **Otherwise, don't add them.** Deliver the plain diagram, explain the flow in your reply as usual, and end with one line: "Want me to add this flow to the diagram as numbered steps, and label the connections?" On a yes, render the same graph again with the steps you explained as flows (and edge labels), so the reply and the diagram match.
- **Edge labels** ("Reads secrets", "Publishes events") go on arrows the graph already has; add them in the first render only when the user asks what the connections do, and otherwise include them in the same offer.
- Keep it to one or two flows of a few steps each, name numbered copies (`aws_alb.api~1`), and fix any step the result warns draws no badge.

## Check every render, and fix the input

TerraVision draws exactly what it is given. When a diagram looks wrong, assume the cause is in your input, not in TerraVision: usually a node missing from its container, a wrong type, a missing or extra connection, or one of the "Drawn as written" rules above.

- **Check the graph before the first render.** Every service the user asked for is there with its specific type; in a multi-zone design each zone has what it should (on AWS, one copy per zone subnet of everything that spans zones; see "Zones follow the cloud" in `references/graph-format.md`); every node is listed under the container you meant.
- **Fix the JSON, then render again.** Compare the image with the graph line by line to find the difference. Do not read, debug or modify TerraVision's source code, reinstall it, or work around it. For Terraform code (Path A), the diagram shows what the code deploys; explain any surprise to the user rather than changing TerraVision.
- **Look at every render before showing it**, not only the first. After each render, including re-renders, read the PNG and check that every node is in the box you put it in and nothing is missing. Only then present it or say it is correct.
- **Busy is fine.** Real architectures have many connections, and lines that cross, bend and run long are normal. Do not remove connections, drop nodes or restructure the graph to make the picture tidier: an accurate busy diagram is better than a tidy wrong one. If the user wants it simpler, offer `--simplified`, or the editable `--format drawio` file to rearrange by hand.
- **Edit only what you mean to.** A node address can appear in several lists: under each node that connects to it, and under the container it sits in. To remove one connection, delete the address from that one source node's list. Never search-and-replace an address across the whole file: that also deletes it from its container's list, and the node drops out of its box. After every edit, run the validator and check that each node is still listed under the same container as before.
- **If you are sure the JSON is right** and the image still disagrees with it, stop and tell the user what you expected and what you see, instead of investigating further.

## Troubleshooting

- `'dot'` or `'git'` not found: see Install.
- `'terraform' not found` while using a `.json` source, or `No such option: --title`: TerraVision is too old. Upgrade with the tool that installed it: `uv tool upgrade terravision`, `pipx upgrade terravision` or `python3 -m pip install -U terravision`.
- `Graph mixes aws_* and azurerm_* resources`: split the graph into one file per provider.
- An arrow is missing: see "Drawn as written" above.
- Icon looks generic: the type name is not in `references/node-types.md`; pick the closest listed type.
- Diagram too tall: add `--simplified`, or reduce numbered copies to one per tier.

## Deliver the result, without being asked

As soon as a render passes your check, do all of this in the same reply. Never wait for the user to ask to see the diagram or the JSON.

1. **Show the diagram.** If your interface can display images inline, show the PNG there. Otherwise open it in the user's image viewer: `open <file>` on macOS, `xdg-open <file>` on Linux, `wslview <file>` on WSL, `start <file>` on Windows (`Invoke-Item <file>` in PowerShell). Skip this only on a remote or headless machine, such as Linux with neither `DISPLAY` nor `WAYLAND_DISPLAY` set, and say so.
2. **Show the JSON graph** (Path B) in a `json` code block, so the user can read it and ask for changes.
3. **List the files** with full paths, as clickable links where the interface supports them:
   - `<name>.dot.png`: the diagram
   - `<name>.drawio`: open in draw.io (diagrams.net) to edit by hand
   - `<name>.tvg.json`: the graph; edit it and render again
   - `<name>.annotations.yml` (with flows): the title and flows, for `--annotate`
4. **Summarise in one or two lines**: which path you used, the main components, and one useful next step (add a service, change the title, draw it for another cloud).
5. **Offer the next step** in one line: adding the flow you explained as numbered steps if the diagram has none ("Flows" above), and, for a diagram drawn from a description (Path B), writing Terraform for the architecture. Do neither before the user says yes.

**If the user asks for Terraform:**
- Write code that creates the resources, zones and connections in the diagram. Do not promise to check it by drawing it with TerraVision: that runs `terraform plan`, which needs cloud credentials.
- If the diagram has flows or edge labels, also write `terravision.yml` in the Terraform folder from the diagram's `.annotations.yml`: keep the title, rename every node in `flows` and `connect` to the Terraform address that creates it (`aws_ecs_fargate.api` becomes `aws_ecs_service.api`; numbered copies such as `aws_alb.web~1` become the one resource), and add the external actors (users, internet) under `add:`, since Terraform has none. TerraVision loads that file whenever it draws the Terraform, including in CI.
- End that reply with one line offering a CI workflow that redraws the diagram whenever the Terraform changes: `patrickchugh/terravision-action` for GitHub Actions, and setups for GitLab, Jenkins, Azure DevOps and others at https://patrickchugh.github.io/terravision/cicd-integration/.

With the MCP server, report the paths from `files` the same way, and let the result's `display` line decide step 1. When it says the app is showing the diagram in its interactive view, the diagram is already in front of the user: do not open it in an image viewer as well, by `open_diagram_file` or a shell command, and still show the JSON. When it says the app has no diagram view, show or open the PNG as in step 1.
