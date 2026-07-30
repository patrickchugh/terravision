# MCP Server

TerraVision can run as a [Model Context Protocol](https://modelcontextprotocol.io) server, letting AI
agents generate architecture diagrams from Terraform code themselves.

The useful property here is accuracy. An agent asked to draw an architecture will otherwise invent
the diagram from whatever it can infer. Through this server it gets a diagram derived from
`terraform plan` — the same output `terravision draw` produces, with conditionals, `count`,
`for_each` and module expansion already resolved.

## Install

The MCP server is an optional extra, so the default install is unchanged.

**pipx** (the recommended way to install TerraVision):

```bash
# New install
pipx install "terravision[mcp]"

# Already have TerraVision? Add the dependency to its environment
pipx inject terravision mcp
```

`pip install` will not work inside a pipx-managed environment — use `pipx inject`.

**pip**, if you are already in a virtualenv:

```bash
pip install "terravision[mcp]"
```

**Poetry**, for development:

```bash
poetry install --with test --extras mcp
```

Check it worked:

```bash
terravision mcp --help
```

## Configure your client

The server speaks stdio: your client launches it as a local subprocess. It listens on no port.

**Claude Code**

```bash
claude mcp add terravision -- terravision mcp
```

**Claude Desktop / Cursor** — add to the MCP config file:

```json
{
  "mcpServers": {
    "terravision": {
      "command": "terravision",
      "args": ["mcp", "--output-dir", "/path/for/generated/diagrams"]
    }
  }
}
```

`--output-dir` sets where generated files are written. It defaults to the directory the server was
started in.

### Other MCP clients

The server implements the protocol rather than targeting any one client, so anything that speaks
MCP over stdio can use it — Codex CLI, GitHub Copilot in VS Code, Cursor, Zed, Claude Desktop and
others. Protocol version is negotiated with the client and has been verified against `2024-11-05`
(the original spec), `2025-03-26` and `2025-06-18`; an unrecognised version negotiates to the
server's newest. Results are always returned as a `text` content block, the one response field
present in every version of the spec, so no client depends on newer optional fields.

What differs between clients is only where the configuration lives and what it is called. They all
need the same three things:

| | |
|---|---|
| command | `terravision` (or an absolute path to it) |
| args | `["mcp"]`, plus `--output-dir <dir>` if you want to control where files land |
| env | `PATH` including Terraform and Graphviz — see below |

Most clients use a JSON block of this shape, under a key such as `mcpServers` or `servers`:

```json
{
  "mcpServers": {
    "terravision": {
      "command": "terravision",
      "args": ["mcp", "--output-dir", "./diagrams"],
      "env": { "PATH": "/usr/local/bin:/usr/bin:/bin" }
    }
  }
}
```

Check your client's own documentation for the file location and exact key name, since those change
more often than the protocol does.

### If tools fail with "not found on PATH"

TerraVision needs `terraform` (or `tofu`), `dot`, `gvpr` and `git` on PATH. The MCP server is
spawned as a child process and inherits its environment from the client, which is a common source
of trouble:

- A client launched before PATH last changed passes down a stale copy. Restarting the client fixes
  it.
- GUI clients on macOS and Windows often don't inherit your shell's PATH at all, so tools installed
  via `brew`, `asdf` or an unzipped download may be invisible even though they work in a terminal.

The reliable fix is to pin PATH at registration rather than rely on inheritance:

```bash
claude mcp add terravision -e "PATH=$PATH" -- terravision mcp
```

Or in a client config file:

```json
{
  "mcpServers": {
    "terravision": {
      "command": "terravision",
      "args": ["mcp"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
      }
    }
  }
}
```

On Windows, include the directories holding `terraform.exe` and Graphviz's `bin` (typically
`C:\Program Files\Graphviz\bin`).

## Tools

One tool per TerraVision command. Every tool takes `source`, which may be a Terraform directory, a
Git URL, or a TerraVision `tfdata.json` replay file.

### `generate_architecture_graph`

Equivalent to `terravision graphdata`. Returns the architecture as structured data — the tool to use
for reasoning about a stack rather than looking at it.

Returns `{graphdict, node_count, edge_count, provider}`, where `graphdict` maps each Terraform
resource address to the addresses it connects to or contains. With `services_only: true` it instead
returns `{services, count, provider}` — a much smaller payload, worth calling first when you only
need to know what a stack is built from.

### `generate_diagram`

Equivalent to `terravision draw`. Renders to a file and returns `{path, format, provider}`.

`format` accepts anything Graphviz supports (`png`, `svg`, `pdf`, `dot`, …) plus `drawio` for a file
editable in draw.io, Lucidchart or any mxGraph editor.

### `generate_interactive_html`

Equivalent to `terravision visualise`. Produces a self-contained HTML page with clickable,
searchable nodes and all resource metadata embedded, so it opens offline. Returns `{path, provider}`.

### Common parameters

| Parameter | Purpose |
|---|---|
| `varfile` | `.tfvars` files. Different var files against the same code give genuinely different architectures |
| `workspace` | Terraform workspace to select |
| `planfile` / `graphfile` | Consume Terraform output generated elsewhere; see below |
| `simplified` | Drop networking containers and show only services |
| `annotate` | Path to a `terravision.yml` [annotation file](annotations.md) |
| `upgrade` | Run `terraform init -upgrade` to refresh modules |

`generate_diagram` and `generate_interactive_html` also take `outfile`, `use_tf_names`,
`use_resource_names`, `fontsize` and `iconsize`.

## Things worth knowing

**Tools return paths, not file contents.** This matches the CLI. To inspect a generated `.drawio` or
`.svg`, read the returned path.

**Calls can take minutes.** Every tool runs `terraform init` and `terraform plan` against the source
unless you supply `planfile`/`graphfile`. Calls are executed one at a time.

**A `tfdata.json` source skips Terraform entirely** and returns in seconds. Generate one with
`terravision draw --source <path> --debug`. Useful for iterating without repeated plan runs.

**AI annotation is not exposed.** `--ai-annotate` has TerraVision call out to Bedrock or Ollama.
Doing that from a server that is itself being driven by a model is confused layering, and it would
pull credential handling into a component whose main property is not needing any. Run the CLI
directly if you want it.

## Credentials

TerraVision needs no cloud credentials of its own, and the MCP server changes nothing about that.

When `source` is raw Terraform, TerraVision invokes Terraform, and *Terraform* authenticates to your
cloud provider to produce a plan. To avoid that entirely, pass `planfile` and `graphfile` pointing at
output generated upstream — typically by a CI pipeline that already runs `terraform plan`:

```bash
terraform plan -out=tfplan.bin
terraform show -json tfplan.bin > plan.json
terraform graph > graph.dot
```

The agent then calls a tool with `planfile: "plan.json"`, `graphfile: "graph.dot"` and the original
`source` path. No Terraform run, no credentials.

## Trust boundary

Worth being explicit, since the arguments come from a model:

- **Reads** are unrestricted. A tool can read any Terraform the user running the server can read —
  the same reach as the CLI.
- **Writes** are confined. `outfile` must be a plain filename; separators and `..` are rejected, so
  generated files always land in `--output-dir`.
- **Terraform still executes.** `terraform init` downloads modules and providers from the sources the
  code names, and `plan` reaches your cloud provider. Point the server at code you trust, exactly as
  you would with the CLI. The `planfile`/`graphfile` path avoids this.

## Troubleshooting

**`The MCP server needs the optional 'mcp' dependency`** — run `pipx inject terravision mcp` for a
pipx install, or `pip install "terravision[mcp]"` otherwise. `pip install` on its own does nothing
useful inside a pipx environment, which is the usual reason this message persists after a
reinstall attempt.

**The client reports the server failed to start** — run `terravision mcp` by hand. It should sit
silently waiting for JSON-RPC on stdin; anything printed to your terminal is stderr and safe.
Ctrl-C to exit. If it exits immediately, the error is on stderr.

**A tool call fails but the server stays up** — that is intended. Errors are reported per call. The
underlying message goes to stderr, which your client usually surfaces as server logs.

**"TerraVision cannot run: … not found on PATH"** — see
[If tools fail with "not found on PATH"](#if-tools-fail-with-not-found-on-path) above. Note that an
agent investigating this on its own will often run `where terraform` in a shell that has the *same*
stale environment, conclude the tool is not installed, and go looking for a workaround. Check the
binary's real location before believing that.
