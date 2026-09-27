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

**uv**:

```bash
# New install, or add the extra to an existing uv install
uv tool install "terravision[mcp]"

# Or run it without installing, which is how the Claude Code, Codex and
# Gemini CLI plugins and the MCP Registry entry launch it
uvx --from "terravision[mcp]" terravision mcp
```

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

**Claude Desktop** — install the extension: download `terravision-<version>.mcpb` from the
[latest release](https://github.com/patrickchugh/terravision/releases/latest) and double-click it,
or drag it into Claude Desktop's **Settings → Extensions**. It asks where to save diagrams (by
default `Documents/TerraVision`) and installs TerraVision itself; your computer needs Graphviz and
Git, and on Linux also [uv](https://docs.astral.sh/uv/getting-started/installation/), which Claude
Desktop uses there to run the extension.

If extensions are turned off on your machine, add the server by hand instead (**Settings →
Developer → Edit Config**). On macOS, give the full path to `uvx` (from `which uvx`), because
Claude Desktop does not see your terminal's PATH:

```json
{
  "mcpServers": {
    "terravision": {
      "command": "uvx",
      "args": ["--from", "terravision[mcp]", "terravision", "mcp", "--output-dir", "/path/for/diagrams"]
    }
  }
}
```

**Cursor** — add to the MCP config file:

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
server's newest. Every result starts with a `text` content block, the one response field present in
every version of the spec, so no client depends on newer optional fields. Diagram results add a
preview image and structured content for clients that use them.

What differs between clients is only where the configuration lives and what it is called. They all
need the same three things:

| | |
|---|---|
| command | `terravision` (or an absolute path to it) |
| args | `["mcp"]`, plus `--output-dir <dir>` if you want to control where files land |
| env | `PATH` including Graphviz and, for the `source` tools, Terraform — see below |

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

### Running the server from the Docker image

The [Docker image](installation.md) includes the MCP server with Graphviz, Git and Terraform, so a
client can run it with nothing else installed. Keep `-i` (the protocol runs over stdin) and mount the
folder where diagrams should land:

```json
{
  "mcpServers": {
    "terravision": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "/path/to/diagrams:/project",
               "patrickchugh/terravision", "mcp", "--output-dir", "/project"]
    }
  }
}
```

Paths in results are paths inside the container (`/project/...`), and `open_diagram_file` cannot
open files there, since a container has no desktop: open them from the mounted folder instead. To
draw Terraform code, mount it too and pass its container path as `source`.

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

`render_graph` takes a graph inline and never runs Terraform. The other three tools mirror
TerraVision commands and take `source`, which may be a Terraform directory, a Git URL, a
`.tvg.json` graph file or a TerraVision `tfdata.json` replay file.

### `diagram_guide`

Returns what an agent needs to write a good graph for one provider (`aws`, `azure` or `gcp`): the
[Graph Format](graph-format.md) rules, worked example graphs and every node type for that provider.
It gives apps that have the MCP server but not the [agent skill](https://github.com/patrickchugh/terravision/tree/main/skills/terravision-cloud-diagrams),
such as Claude Desktop, the same guidance, so their diagrams use the specific icons (Fargate, RDS by
engine) and the level of detail of the examples: availability zones, public and private subnets,
the internet path and shared services. The server's instructions tell agents to call it once before
`render_graph`. It also reports in `setup` whether Graphviz, Git and Terraform (or OpenTofu) are
installed, with the install commands for anything missing, so the agent can tell the user before
drafting a diagram. Claude Desktop's "requirements met" check covers only the operating system
and Python, not these programs.

It also lists a library of patterns for that provider (EKS, ECS, Step Functions, SageMaker, Glue,
GKE, AKS and others), each TerraVision's own output for real Terraform with the addresses written
plainly. Pass `pattern: "<name>"` to fetch one. `scripts/gen_example_patterns.py` rebuilds the
library from `tests/json` and refuses any pattern that would draw differently from the original.

### `render_graph`

Renders a diagram from a graph passed directly as JSON, so an agent never has to write a file.
`graph` maps each node address (`<terraform_resource_type>.<name>`) to the list of addresses it
connects to or contains; the [Graph Format](graph-format.md) page has the rules and the
[node types](node-types.md) page the icons. The graph is saved as `<outfile>.tvg.json` in the
output directory and rendered exactly as `terravision draw --source <that file>` would, so the two
paths cannot drift. Returns the same result as `generate_diagram` plus `graph_path`, `node_count`
and `edge_count`.

When parts of the graph will not draw as they read, the result also has `warnings`: an unknown type
(with the closest supported types suggested), an arrow to a container or a shared service, a node
listed in two boxes. They come from the skill's validator, so the command-line check gives the same
advice. The diagram is still drawn, and the view lists the warnings under it.

Takes `format`, `outfile`, `fontsize`, `iconsize`, `title`, `preview` and `flows`: numbered steps drawn
as badges with a legend (rule 10 of the [graph format](graph-format.md)). With `flows`, `files` also
has `annotations`, a YAML file holding the title and flows, so
`terravision draw --source <name>.tvg.json --annotate <name>.annotations.yml` draws the same
diagram, and a step that draws no badge (a missing node or arrow, a container) is listed in
`warnings`. `edge_labels` puts a few words on arrows the graph already has, keyed by arrow:
`{"aws_ecs_fargate.app -> aws_rds_sqlserver.db": "Reads orders"}` (rule 11); a label never adds an
arrow, and one that is not drawn is listed in `warnings`. Labels are saved in the same
`.annotations.yml`, under `connect`. Needs only Graphviz and Git: no
Terraform, no credentials, no `source`. A graph that mixes providers (`aws_*` with `azurerm_*` or
`google_*`) is rejected; draw one diagram per provider.

### `generate_architecture_graph`

Equivalent to `terravision graphdata`. Returns the architecture as structured data — the tool to use
for reasoning about a stack rather than looking at it.

Returns `{graphdict, node_count, edge_count, provider}`, where `graphdict` maps each Terraform
resource address to the addresses it connects to or contains. With `services_only: true` it instead
returns `{services, count, provider}` — a much smaller payload, worth calling first when you only
need to know what a stack is built from.

### `generate_diagram`

Equivalent to `terravision draw`, but always saves the full set: the requested format plus a PNG, an
SVG, an editable draw.io file and the graph as `.tvg.json` (exported from Terraform too, so it can be
changed and rendered again with `render_graph`). Returns `{path, format, provider, title, files}`,
where `files` maps `png`, `svg`, `drawio` and `graph` to paths and `path` is the requested format,
followed by a **preview image** of the diagram (at most 1568 pixels on the long edge, usually well
under 300 KB) so the model can check what it drew. `preview: false` leaves the image out.

`format` accepts anything Graphviz supports (`png`, `svg`, `pdf`, `dot`, …) plus `drawio` for a file
editable in draw.io, Lucidchart or any mxGraph editor.

### `generate_interactive_html`

Equivalent to `terravision visualise`. Produces a self-contained HTML page with clickable,
searchable nodes and all resource metadata embedded, so it opens offline. Returns `{path, provider}`.
It refuses a graph file (`.tvg.json`), which has no resource metadata to show; use `render_graph`
or `generate_diagram` for those, which also write a self-contained SVG that works in any browser. A `tfdata.json` replay works.

### `open_diagram_file`

Opens a file from a diagram result in the user's default app (the image viewer for `.png`, draw.io
for `.drawio`), or with `reveal: true` shows it in its folder. It works because the server runs on
the user's own computer. Only files this server rendered can be opened; any other path is refused.

### `diagram_file`

Returns a rendered file's contents to the diagram view. It is marked as app-only
(`_meta.ui.visibility: ["app"]`) and, like `open_diagram_file`, refuses any file the server did not
render.

### The diagram view (MCP Apps)

`render_graph` and `generate_diagram` link to an [MCP Apps](https://modelcontextprotocol.io/extensions/apps/overview)
view, `ui://terravision/diagram-<hash>.html` (the hash changes whenever the view does, because
hosts cache views by address). In apps that support MCP Apps, such as Claude Desktop, VS
Code with GitHub Copilot and Cursor, the diagram appears in the chat as soon as it is drawn, with
zoom and pan, and four buttons: **Open image** (in your image viewer), **Edit in draw.io**, **Show in
folder**, and **Source**, which shows and copies the graph JSON and, once flows or edge labels are
added, the annotations YAML. Apps without MCP Apps still get the preview image and the file paths;
apps whose views cannot call tools show the diagram without buttons, with the file paths listed.

The view is a single self-contained HTML page: it loads nothing from the internet and needs no
permissions beyond writing to the clipboard.

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
`use_resource_names`, `fontsize`, `iconsize` and `title` (overrides a title in the annotation file);
`generate_diagram` also takes `preview`, `flows` and `edge_labels`, which name nodes as they appear in the `.tvg.json`
of an earlier render and replace any flow of the same name from the annotation file.

## Things worth knowing

**Tools return paths, not file contents.** This matches the CLI. To inspect a generated `.drawio` or
`.svg`, read the returned path.

**Calls can take minutes.** Every `source` tool runs `terraform init` and `terraform plan` against the
source unless you supply `planfile`/`graphfile` or a JSON source; `render_graph` never does. Calls are
executed one at a time.

**A `.tvg.json` graph or `tfdata.json` source skips Terraform entirely** and returns in seconds.
Export a graph with `terravision graphdata`, or a replay file with `terravision draw --source <path> --debug`.
Useful for iterating without repeated plan runs.

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
