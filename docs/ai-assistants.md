# Use TerraVision with AI assistants

Ask your AI assistant for a cloud architecture diagram in plain English, and TerraVision draws it with the official AWS, Azure and GCP icons, grouped into VPCs, subnets, zones and resource groups the way a cloud architect would. It fits every stage of an architecture's life:

1. **A description → a diagram.** Describe the system, or let the assistant design one, and get a diagram in seconds. No Terraform needed.
2. **Terraform → a diagram.** Point the assistant at Terraform code and get a diagram of what that code actually deploys.
3. **A diagram → Terraform.** Once a design looks right, ask the assistant to write the Terraform for it.
4. **Terraform → an up-to-date diagram, automatically.** A CI workflow redraws the diagram whenever the Terraform changes.

TerraVision itself runs on your own computer: nothing is uploaded anywhere beyond the conversation you are already having with your assistant.

## Set up (once)

**First, the prerequisites.** TerraVision needs **Graphviz** (to draw) and **Git**. **uv** runs TerraVision for Claude Code, Codex, Gemini CLI and other MCP clients; Claude Desktop brings its own on Windows and macOS, so skip it there. **Terraform** (or OpenTofu) is only needed to draw from Terraform code.

=== "macOS"

    With [Homebrew](https://brew.sh):

    ```bash
    brew install graphviz git
    brew install uv                        # not needed for Claude Desktop
    brew install hashicorp/tap/terraform   # optional: to draw from Terraform code
    ```

=== "Windows"

    In PowerShell:

    ```powershell
    winget install --id Graphviz.Graphviz -e
    winget install --id Git.Git -e
    winget install --id astral-sh.uv -e    # not needed for Claude Desktop
    winget install --id Hashicorp.Terraform -e   # optional: to draw from Terraform code
    ```

    Then open a **new** terminal, and restart your AI app, so they see the new programs.

=== "Linux"

    On Debian and Ubuntu:

    ```bash
    sudo apt install graphviz git
    curl -LsSf https://astral.sh/uv/install.sh | sh   # Claude Desktop on Linux needs it too
    # optional, to draw from Terraform code: HashiCorp's apt repository
    wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    sudo apt update && sudo apt install terraform
    ```

    On Ubuntu 26.04+ and Debian testing, also `sudo apt install libgvplugin-neato-layout8`. Other distributions: [HashiCorp's install guide](https://developer.hashicorp.com/terraform/install).

If anything is still missing later, the assistant says what to install. To check at any time, ask it: *"Is TerraVision set up correctly?"*

**Then connect your assistant:**

=== "Claude Desktop"

    Download `terravision-<version>.mcpb` from the [latest release](https://github.com/patrickchugh/terravision/releases/latest) and double-click it (or drag it into **Settings → Extensions**). Diagrams appear right in the chat. Details: [MCP server](mcp-server.md#configure-your-client).

=== "Claude Code"

    Works in the terminal and in the Claude Code extension for VS Code and JetBrains:

    ```bash
    claude plugin marketplace add patrickchugh/terravision
    claude plugin install terravision-cloud-diagrams@terravision
    ```

    This installs the TerraVision skill and its MCP server together. Start a new Claude Code session afterwards. Diagrams are saved in a `diagrams` folder in your project.

    The very first start downloads and installs TerraVision, which can take longer than Claude Code waits. If `/mcp` shows TerraVision failed to connect, choose **Reconnect**. To avoid it, install it ahead of time: `uvx --from "terravision[mcp]" terravision --version`.

=== "Codex CLI"

    ```bash
    codex plugin marketplace add https://github.com/patrickchugh/terravision
    codex plugin add terravision-cloud-diagrams@terravision
    ```

=== "Gemini CLI"

    ```bash
    gemini extensions install https://github.com/patrickchugh/terravision
    ```

=== "VS Code (Copilot), Cursor, others"

    Add TerraVision as an MCP server. In VS Code run **MCP: Open User Configuration**; in Cursor edit its MCP config file:

    ```json
    {
      "servers": {
        "terravision": {
          "type": "stdio",
          "command": "uvx",
          "args": ["--from", "terravision[mcp]", "terravision", "mcp", "--output-dir", "/path/for/diagrams"]
        }
      }
    }
    ```

    Cursor and most other clients call the top-level key `mcpServers` instead of `servers`. See [MCP server](mcp-server.md) for more clients and options.

## 1. From a description to a diagram

Ask the way you would ask a colleague:

> Draw an AWS three-tier architecture: a React front end on CloudFront and S3, an ECS Fargate API behind an Application Load Balancer across two availability zones, SQL Server on RDS Multi-AZ, and images in ECR.

The assistant turns the description into a [TerraVision graph](graph-format.md), a short JSON file listing each resource and what it connects to or sits inside, and TerraVision draws it. The assistant checks the picture before showing it to you, and you get:

- the diagram as **PNG** and **SVG**;
- an editable **draw.io** file, to rearrange by hand;
- the **graph** (`.tvg.json`), which you or the assistant can change and draw again.

Then keep talking to it:

- *"Put the database in its own subnet."* / *"Add ElastiCache for sessions."* / *"Draw the same thing on Azure."*
- *"Show how a request moves through it."* The steps appear on the diagram as numbered circles, with a legend.
- *"Label the connections."* Short labels such as "Reads orders" go on the arrows.

After each diagram, the assistant offers the natural next step: adding the request flow, or writing the Terraform (see 3 below). It won't do either until you say yes.

## 2. From Terraform code to a diagram

> Draw the architecture of the Terraform in `./infra`.

> Show me a cloud architecture diagram of https://github.com/patrickchugh/testcase-bastion//examples

Local folders and Git repositories both work, including private ones you have access to. The `//examples` part points at a folder inside the repository. Many repositories keep a reusable module at their root, which describes nothing on its own; the diagram comes from a folder that uses it, like `examples/` or an environment folder. If you only give the repository, the assistant looks for that folder itself.

TerraVision runs `terraform init` and `terraform plan` on the code and draws what the plan says will be deployed, so conditionals, `count`, `for_each` and modules are all resolved. A diagram is only as good as its source, and this one comes from the code itself, not from the assistant's reading of it.

`terraform plan` needs the same cloud credentials you would use to run Terraform. Without them, generate the plan once where credentials exist and hand TerraVision the files; no credentials are needed after that:

```bash
terraform plan -out=tfplan.bin && terraform show -json tfplan.bin > plan.json
terraform graph > graph.dot
```

> Draw the diagram from `plan.json` and `graph.dot`.

You can add flows and labels to these diagrams too (*"Add the checkout flow as numbered steps"*). To change the architecture itself, change the Terraform and draw it again.

## 3. From a diagram to Terraform

When a design drawn from a description looks right, ask for the code:

> Write the Terraform for this architecture.

The assistant writes Terraform that creates the resources, zones and connections in the diagram. To see how close it is, draw the new code (workflow 2) and compare the two diagrams. That runs `terraform plan`, so it needs cloud credentials.

If the design has flows or labels, the assistant also writes a `terravision.yml` next to the Terraform. It carries the title, flows and labels over to the Terraform's own resource names, and adds the users and other external actors, which Terraform has no resources for. TerraVision reads that file whenever it draws the Terraform, so later diagrams keep the design's numbered steps and labels.

Treat generated Terraform as a first draft: review it, and run `terraform plan` yourself, before you apply anything.

## 4. Keep the diagram up to date in CI

Once the Terraform is in a repository, the diagram can redraw itself whenever the code changes, so it never goes stale. After writing Terraform, the assistant offers to set this up. You can also ask:

> Add a GitHub Actions workflow that redraws the architecture diagram when the Terraform changes.

On GitHub it uses the [TerraVision GitHub Action](cicd-integration.md#github-actions). GitLab, Jenkins, Azure DevOps and others are covered in [CI/CD Integration](cicd-integration.md), including a mode that keeps cloud credentials out of the diagram step. The `terravision.yml` from step 3 is picked up there too, so the flows and labels carry on into every new version of the diagram.

## What you see

- **Claude Desktop**, and other apps that support [MCP Apps](mcp-server.md#the-diagram-view-mcp-apps): the diagram appears in the chat with zoom, and buttons to **Open image** in your image viewer, **Edit in draw.io** (in the draw.io app, or on the web if it isn't installed), **Show in folder**, and **Source** (the graph JSON, and the flows once added).
- **Terminal assistants** (Claude Code, Codex CLI, Gemini CLI): the assistant looks at the diagram itself and lists the files. Ctrl-click (Cmd-click on macOS) a path to open it.

## Tips

- **One cloud per diagram.** A diagram uses one provider's icons and layout rules. For a multi-cloud system, ask for one diagram per cloud.
- **Busy is normal.** Real systems have many connections, and TerraVision draws them all rather than hiding some to look tidy. For a high-level picture, ask for a simpler version with fewer boxes, or rearrange the draw.io file by hand.
- **If something looks wrong, say what.** For example, "the NAT gateway should be in the public subnet". The assistant fixes the graph and draws it again.
- **Keep the graph.** The `.tvg.json` file is the source of the diagram. Commit it next to your docs, and anyone (or any assistant) can change it and redraw.

## Reference

- [Graph Format](graph-format.md): the JSON the assistant writes, including flows and edge labels
- [Node types](node-types.md): every supported resource type and icon
- [MCP server](mcp-server.md): the tools, client setup and trust boundary
- [Agent skill](https://github.com/patrickchugh/terravision/tree/main/skills/terravision-cloud-diagrams): the instructions the assistant follows
- [llms.txt](llms.txt): a plain-text index of these docs, for assistants reading the web
