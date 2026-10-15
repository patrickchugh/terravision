# Security Policy

## Supported versions

Security fixes go into the next release of TerraVision. Only the latest release is supported: the newest `terravision` package on PyPI and the `patrickchugh/terravision:latest` Docker image. Fixes are not backported to older versions, so upgrade to receive them.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security problem.** Report it privately instead:

- **Preferred:** [GitHub private vulnerability reporting](https://github.com/patrickchugh/terravision/security/advisories/new)
- **Email:** terravisionapp@gmail.com, with "TerraVision security" in the subject

Please include:

- the TerraVision version (`terravision --version`), operating system and Python version
- how TerraVision was run: CLI command, MCP server, or Docker image
- steps to reproduce, ideally with a minimal Terraform folder, plan file or `.tvg.json` graph
- what an attacker gains

## What to expect

- An acknowledgement within 5 business days.
- An assessment within 14 days: whether the report is accepted, and the planned fix.
- For an accepted report, a fixed release and a GitHub Security Advisory, with a CVE where the issue warrants one. You are credited in the advisory unless you ask not to be.

Please allow 60 days from your report, or until a fix is released if sooner, before disclosing publicly.

## Security model

Knowing what TerraVision does helps decide what counts as a vulnerability.

- **Runs locally.** Terraform source, variable values and plan output are parsed on your machine and never sent anywhere by TerraVision. The one exception is `--ai-annotate`, which sends a summary of the resource graph to the AI backend you choose; see the [FAQ](faq.md#what-data-is-sent-to-the-llm-when-i-use-ai-annotate).
- **Downloads what your code references.** Remote modules referenced by your Terraform (Git repositories, the Terraform Registry, HTTP archives) are downloaded to `~/.terravision/module_cache`. When TerraVision runs `terraform init`, Terraform downloads providers.
- **Runs local tools.** TerraVision runs `terraform`, `terragrunt`, `git` and Graphviz `dot` as subprocesses. When asked to open a diagram, it uses the operating system's default application.
- **Needs no cloud credentials itself.** It does not read, store or send cloud credentials. When it runs `terraform plan`, Terraform uses whatever credentials your environment provides. With pre-generated plan input (`--planfile` and `--graphfile`) no credentials are needed at all.
- **MCP server has no network port.** `terravision mcp` serves over stdio only, as a subprocess of the AI app that started it, and writes diagrams to its output directory.

### Terraform you did not write is untrusted code

Drawing a Terraform folder without `--planfile` runs `terraform init` and `terraform plan` on it. That downloads and executes provider plugins, and Terraform can run arbitrary programs during a plan (for example, the `external` data source). Drawing untrusted Terraform this way is the same as running it.

For Terraform you do not trust, generate the plan in an isolated environment and pass it with `--planfile` and `--graphfile`, or run TerraVision in a container with no credentials. See [Pre-Generated Plan Input](usage-guide.md#pre-generated-plan-input).

### In scope

- Code execution, or files written outside the intended folder, caused by a crafted `.tf` file, plan JSON, graph file, `.tvg.json` graph, annotation file or module archive, other than by Terraform itself as described above
- Script injection in generated HTML, SVG or draw.io output
- MCP tools reading or writing files outside the paths they are meant to use
- Data sent anywhere beyond what this page and the FAQ describe

### Out of scope

- Behaviour of Terraform, providers, Terragrunt, Git or Graphviz; report those to their maintainers
- Code that Terraform runs when planning untrusted Terraform, as described above
- Attacks that require control of the machine, the user account or the AI app running TerraVision
- Scanner output with no demonstrated impact; please describe how the issue can be exploited
