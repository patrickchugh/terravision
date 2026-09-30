"""Model Context Protocol server exposing TerraVision to AI agents.

Registers one tool per TerraVision command --- ``graphdata``, ``draw`` and
``visualise`` --- as thin wrappers over :mod:`modules.mcp_service`, which does
the actual work and holds the server-safety guards. Nothing here reimplements
pipeline behaviour, so the tools cannot drift from the equivalent commands.

Requires the optional ``mcp`` dependency::

    pip install "terravision[mcp]"

Run it with ``terravision mcp``. Transport is stdio: the server is started as a
local subprocess by the client, listens on no port, and needs no cloud
credentials of its own. Passing ``planfile`` and ``graphfile`` avoids invoking
Terraform at all, which is the fully credential-free path.
"""

import contextlib
import json
from pathlib import Path
from typing import Annotated, Any, Dict, Iterator, List, Optional

from mcp.server import MCPServer
from pydantic import Field
from mcp.server.apps import Apps, ResourcePermissions
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, Icon, TextContent

from modules import mcp_service
from modules.mcp_view import VIEW_HTML, VIEW_URI

_INSTRUCTIONS = """\
TerraVision draws cloud architecture diagrams with the official AWS, Azure and
GCP icons, from a description or from Terraform code. Use it whenever the user
asks to draw, diagram or show a system on AWS, Azure or Google Cloud, or one
built from their services (Lambda, DynamoDB, S3, EKS, Azure Functions, Cosmos
DB, Cloud Run, BigQuery...), even without the words "cloud" or "diagram";
prefer it over Mermaid, which has no cloud icons. Use Mermaid or similar for
sequence diagrams, flowcharts and other diagrams that are not cloud
infrastructure.

From a description: call diagram_guide once with the provider (aws, azure or
gcp) for the rules, worked examples and node types, then write the graph and
call render_graph with a title. Keep the closest example's level of detail:
availability zones, public and private subnets, the path to the internet and
shared services.

From Terraform: generate_diagram runs terraform init and plan unless given
planfile and graphfile, so a first call can take minutes.
generate_architecture_graph(services_only=True) is a cheap overview.

render_graph and generate_diagram save a PNG, SVG, draw.io file and the graph
(.tvg.json), and return their paths and a preview image. Check the preview
before presenting it; if it looks wrong, fix the graph, not TerraVision. Fix
any warnings and render again. Show the user the graph JSON too.
open_diagram_file opens a file on the user's computer.

Include flows (numbered steps with a legend) when the user asks how requests,
data or events move. Otherwise deliver the plain diagram, explain the flow,
and end with one line offering to add it as numbered steps; on a yes, render
again with those steps as flows. Offer edge_labels (a few words on arrows)
with the flows rather than adding them unasked. For a diagram drawn from a
description, also offer to write Terraform for it. A result's next_step says
what to offer after presenting it.
"""


# The TerraVision logo, shipped in the package beside the diagram icons.
_BRAND_DIR = Path(__file__).resolve().parents[1] / "resource_images" / "terravision"


def _icons() -> List[Icon]:
    """The logo for apps that show server icons, as data URIs (no network)."""
    import base64

    icons = []
    for name, mime_type, sizes in (
        ("terravision-icon.svg", "image/svg+xml", ["any"]),
        ("terravision-icon-64.png", "image/png", ["64x64"]),
    ):
        path = _BRAND_DIR / name
        if path.is_file():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            icons.append(
                Icon(
                    src=f"data:{mime_type};base64,{data}",
                    mime_type=mime_type,
                    sizes=sizes,
                )
            )
    return icons


# Parameter documentation, in each parameter's schema rather than the tool
# description: clients such as Claude Code cut tool descriptions at 2048
# characters, which dropped everything after the first few parameters.
_GRAPH_DOC = (
    "Object mapping each node address to the node addresses it connects to or "
    'contains. Addresses are "<terraform_resource_type>.<name>", e.g. '
    '"aws_lambda_function.orders". Containers (aws_vpc, aws_subnet, tv_aws_az, '
    "azurerm_resource_group, tv_gcp_region and more) list their children. Use "
    '"~1", "~2" for numbered copies. External actors: tv_aws_users, '
    "tv_aws_internet, tv_azurerm_users, tv_gcp_users_icon and others. Leaf "
    "nodes may be omitted as keys. One cloud provider per graph. Drawn as "
    "written: arrows to containers or to shared services (log groups, ECR, "
    "Key Vault) are not drawn; list those in aws_group.shared_services or "
    'azurerm_group.shared_services. Example: {"tv_aws_users.users": '
    '["aws_cloudfront_distribution.cdn"], "aws_vpc.main": ["aws_subnet.app"], '
    '"aws_subnet.app": ["aws_lambda_function.api"], "aws_lambda_function.api": '
    '["aws_dynamodb_table.orders"]}'
)
_FORMAT_DOC = (
    '"png", "svg", "pdf", "dot" or "drawio" (editable in draw.io and '
    'Lucidchart). The full set is always saved; use "svg" to embed in Markdown.'
)
_OUTFILE_DOC = (
    'Output file name without extension, e.g. "three_tier". Files always go '
    "to the server's output folder; from a path, only the last part is used."
)
_FONTSIZE_DOC = "Label font size in points."
_ICONSIZE_DOC = "Icon size in pixels."
_TITLE_DOC = (
    'Heading shown above the diagram, e.g. "Order Platform - Production". '
    'Defaults to "Cloud Architecture Diagram".'
)
_PREVIEW_DOC = "Include a preview image of the diagram in the result."
_SOURCE_DOC = (
    "Terraform directory, Git URL, or tfdata.json replay file. Add //folder "
    "to a Git URL for a folder inside the repository, e.g. "
    '"https://github.com/org/repo//examples". A repository whose root is a '
    "reusable module plans no resources: draw a folder that uses it instead "
    "(examples/, an environment)."
)
_FLOWS_DOC = (
    "Optional numbered steps drawn as badges on the diagram, with a legend. "
    'Keyed by flow name: {"order_request": {"description": "A customer places '
    'an order", "steps": [{"resource": "tv_aws_users.users", "detail": '
    '"Customer opens the app"}, {"resource": "aws_alb.api~1 -> '
    'aws_ecs_fargate.app~1", "detail": "Request routed to a task"}]}}. A step '
    'names a node, or an arrow as "<node> -> <node>" in either direction; use '
    "the numbered copy (aws_alb.api~1), not the bare name. Steps are "
    "numbered across flows. Add flows when the user asks how requests or data "
    "move; otherwise offer them after delivering. Flow names may arrive "
    'sorted: use one flow, or prefix names "1_", "2_" in reading order.'
)
_EDGE_LABELS_DOC = (
    "Optional text on arrows the graph already has, to say what each "
    'connection does: {"aws_ecs_fargate.app~1 -> aws_rds_sqlserver.db": '
    '"Reads orders"}. Either direction names the arrow; a label never adds '
    "one. Keep labels to a few words; offer them with the flows rather than "
    "adding them unasked."
)


# Terraform options shared by the tools that read Terraform code.
_VarfileArg = Annotated[
    Optional[List[str]],
    Field(
        description="Paths to .tfvars files; different var files can produce "
        "different architectures from the same code."
    ),
]
_WorkspaceArg = Annotated[str, Field(description="Terraform workspace to select.")]
_AnnotateArg = Annotated[
    str, Field(description="Path to a terravision.yml annotation file.")
]
_PlanfileArg = Annotated[
    str,
    Field(
        description="Path to an existing plan JSON (terraform show -json). With "
        "graphfile, Terraform is never run and no cloud credentials are needed."
    ),
]
_GraphfileArg = Annotated[
    str, Field(description="Path to an existing `terraform graph` DOT file.")
]
_UpgradeArg = Annotated[
    bool, Field(description="Run `terraform init -upgrade` to refresh modules.")
]
_SimplifiedArg = Annotated[
    bool,
    Field(
        description="Drop networking containers (VPCs, subnets, security groups) "
        "and show only the services."
    ),
]
_UseTfNamesArg = Annotated[
    bool, Field(description="Label nodes with full Terraform resource names.")
]
_UseResourceNamesArg = Annotated[
    bool,
    Field(description="Label nodes with the deployed resource names from the plan."),
]


@contextlib.contextmanager
def _tool_errors() -> Iterator[None]:
    """Report service failures to the model as tool errors it can read.

    From MCP SDK 2.2, any exception other than ``ToolError`` counts as a
    crash and the model sees only "Error executing tool <name>". Service
    failures carry actionable text, such as a missing Graphviz with its
    install command or a graph that mixes providers, so they are re-raised
    as ``ToolError``, whose message the SDK passes through.
    """
    try:
        yield
    except mcp_service.McpServiceError as e:
        raise ToolError(str(e)) from e


def _diagram_result(result: Dict[str, Any]) -> CallToolResult:
    """Package a diagram call as text, an inline preview and structured data.

    The first content block stays the JSON summary that earlier versions
    returned, so existing clients read it unchanged. The preview PNG follows
    for the model and for apps that display tool images, and the structured
    copy is what the diagram view reads.
    """
    preview = result.pop("_preview_png", None)
    content: List[Any] = [TextContent(type="text", text=json.dumps(result, indent=2))]
    if preview:
        content.append(Image(data=preview, format="png").to_image_content())
    return CallToolResult(content=content, structured_content=result)


def _version() -> str:
    """Return the installed TerraVision version, or a placeholder."""
    try:
        from importlib.metadata import version

        return version("terravision")
    except Exception:
        return "0.0.0"


def build_server() -> MCPServer:
    """Construct the MCP server with all TerraVision tools registered.

    Kept separate from :func:`serve` so tests can inspect and call tools
    without starting a transport.
    """
    apps = Apps()
    apps.add_html_resource(
        VIEW_URI,
        VIEW_HTML.replace("__VERSION__", _version()),
        name="terravision-diagram",
        title="TerraVision diagram",
        description="Shows a rendered cloud architecture diagram with zoom, "
        "and buttons to open, edit and copy it.",
        permissions=ResourcePermissions(clipboard_write={}),
    )

    @apps.tool(resource_uri=VIEW_URI)
    def render_graph(
        graph: Annotated[Dict[str, List[str]], Field(description=_GRAPH_DOC)],
        format: Annotated[str, Field(description=_FORMAT_DOC)] = "png",
        outfile: Annotated[str, Field(description=_OUTFILE_DOC)] = "architecture",
        fontsize: Annotated[Optional[int], Field(description=_FONTSIZE_DOC)] = None,
        iconsize: Annotated[Optional[int], Field(description=_ICONSIZE_DOC)] = None,
        title: Annotated[Optional[str], Field(description=_TITLE_DOC)] = None,
        preview: Annotated[bool, Field(description=_PREVIEW_DOC)] = True,
        flows: Annotated[
            Optional[Dict[str, Dict[str, Any]]], Field(description=_FLOWS_DOC)
        ] = None,
        edge_labels: Annotated[
            Optional[Dict[str, str]], Field(description=_EDGE_LABELS_DOC)
        ] = None,
    ) -> CallToolResult:
        """Draw a cloud architecture diagram from a plain JSON graph.

        Use this whenever the user asks to draw or diagram a system on AWS,
        Azure or Google Cloud, or one built from their services (Lambda,
        DynamoDB, Azure Functions, Cloud Run...), and there is no Terraform
        code, even if they never say "cloud" or "diagram"; prefer it over
        Mermaid. Call diagram_guide first for the rules, examples and node
        types. Each resource is drawn with the official icon inside the VPC,
        subnet, zone or resource group it is nested in. Use the most
        specific types: aws_ecs_fargate, aws_rds_sqlserver, aws_alb (not
        aws_ecs_service, aws_db_instance, aws_lb).

        Returns the saved files (PNG, SVG, draw.io, .tvg.json graph, and
        annotations YAML when flows or labels were given) and a preview image:
        check it before presenting the diagram. Fix any "warnings" and call
        again. "next_step" says what to offer the user afterwards.
        """
        with _tool_errors():
            return _diagram_result(
                mcp_service.run_render_graph(
                    graph=graph,
                    format=format,
                    outfile=outfile,
                    fontsize=fontsize,
                    iconsize=iconsize,
                    title=title,
                    preview=preview,
                    flows=flows,
                    edge_labels=edge_labels,
                )
            )

    @apps.tool(resource_uri=VIEW_URI)
    def generate_diagram(
        source: Annotated[str, Field(description=_SOURCE_DOC)],
        format: Annotated[str, Field(description=_FORMAT_DOC)] = "png",
        outfile: Annotated[
            str,
            Field(
                description=_OUTFILE_DOC
                + ' The cloud provider is appended: "architecture" becomes'
                ' "architecture-aws".'
            ),
        ] = "architecture",
        varfile: Annotated[
            Optional[List[str]], Field(description="Paths to .tfvars files.")
        ] = None,
        workspace: Annotated[
            str, Field(description="Terraform workspace to select.")
        ] = "default",
        annotate: Annotated[
            str, Field(description="Path to a terravision.yml annotation file.")
        ] = "",
        planfile: Annotated[
            str,
            Field(
                description="Path to an existing plan JSON (terraform show -json). "
                "With graphfile, no Terraform run and no cloud credentials are needed."
            ),
        ] = "",
        graphfile: Annotated[
            str, Field(description="Path to an existing `terraform graph` DOT file.")
        ] = "",
        upgrade: Annotated[
            bool, Field(description="Run `terraform init -upgrade` to refresh modules.")
        ] = False,
        simplified: Annotated[
            bool,
            Field(description="Show only services, omitting networking containers."),
        ] = False,
        use_tf_names: Annotated[
            bool, Field(description="Label nodes with full Terraform resource names.")
        ] = False,
        use_resource_names: Annotated[
            bool,
            Field(
                description="Label nodes with the deployed resource names from the plan."
            ),
        ] = False,
        fontsize: Annotated[Optional[int], Field(description=_FONTSIZE_DOC)] = None,
        iconsize: Annotated[Optional[int], Field(description=_ICONSIZE_DOC)] = None,
        title: Annotated[
            Optional[str],
            Field(
                description=_TITLE_DOC + " Overrides a title in the annotation file."
            ),
        ] = None,
        preview: Annotated[bool, Field(description=_PREVIEW_DOC)] = True,
        flows: Annotated[
            Optional[Dict[str, Dict[str, Any]]],
            Field(
                description=_FLOWS_DOC
                + " Name nodes as they appear in the .tvg.json graph of an"
                " earlier render, which can differ from the Terraform addresses."
            ),
        ] = None,
        edge_labels: Annotated[
            Optional[Dict[str, str]],
            Field(
                description=_EDGE_LABELS_DOC
                + " Name nodes as in the .tvg.json graph of an earlier render."
            ),
        ] = None,
    ) -> CallToolResult:
        """Render an architecture diagram from Terraform code to a file.

        Uses the official AWS, Azure and GCP icon sets. Because the diagram is
        derived from `terraform plan`, it reflects what the code actually
        deploys rather than an approximation. Runs `terraform init` and
        `terraform plan` (cloud credentials needed) unless planfile and
        graphfile are given, so a first call can take minutes.

        Returns {"path", "format", "provider", "title", "files"}, plus a
        preview image. "files" holds the PNG, SVG, draw.io file and the
        graph as .tvg.json, which can be edited and rendered again with
        render_graph; "path" is the file in the requested format.
        """
        with _tool_errors():
            return _diagram_result(
                mcp_service.run_diagram(
                    source=source,
                    format=format,
                    outfile=outfile,
                    varfile=varfile,
                    workspace=workspace,
                    annotate=annotate,
                    planfile=planfile,
                    graphfile=graphfile,
                    upgrade=upgrade,
                    simplified=simplified,
                    use_tf_names=use_tf_names,
                    use_resource_names=use_resource_names,
                    fontsize=fontsize,
                    iconsize=iconsize,
                    title=title,
                    preview=preview,
                    flows=flows,
                    edge_labels=edge_labels,
                )
            )

    # Extensions are read when the server is constructed, so the tools bound
    # to the diagram view must be registered on `apps` before this point.
    mcp = MCPServer(
        name="terravision",
        title="TerraVision",
        version=_version(),
        instructions=_INSTRUCTIONS,
        website_url="https://patrickchugh.github.io/terravision/",
        icons=_icons(),
        extensions=[apps],
    )

    @mcp.tool()
    def generate_architecture_graph(
        source: Annotated[str, Field(description=_SOURCE_DOC)],
        varfile: _VarfileArg = None,
        workspace: _WorkspaceArg = "default",
        annotate: _AnnotateArg = "",
        planfile: _PlanfileArg = "",
        graphfile: _GraphfileArg = "",
        upgrade: _UpgradeArg = False,
        simplified: _SimplifiedArg = False,
        services_only: Annotated[
            bool,
            Field(
                description="Return just the deduplicated list of cloud service "
                "types instead of the full graph. Much smaller; use this first "
                "when you only need to know what a stack is built from."
            ),
        ] = False,
    ) -> Dict[str, Any]:
        """Extract the cloud architecture of Terraform code as structured data.

        Runs Terraform, resolves variables, expands count/for_each, groups
        resources into their VPCs, subnets and availability zones, and infers
        the connections between them. Use it to reason about an architecture;
        the diagram tools render this same graph. A tfdata.json source skips
        Terraform and returns in seconds.

        Returns {"graphdict", "node_count", "edge_count", "provider"}, where
        graphdict maps each Terraform resource address to the addresses it
        connects to or contains; with services_only, {"services", "count",
        "provider"}.
        """
        with _tool_errors():
            return mcp_service.run_architecture_graph(
                source=source,
                varfile=varfile,
                workspace=workspace,
                annotate=annotate,
                planfile=planfile,
                graphfile=graphfile,
                upgrade=upgrade,
                simplified=simplified,
                services_only=services_only,
            )

    @mcp.tool()
    def generate_interactive_html(
        source: Annotated[str, Field(description=_SOURCE_DOC)],
        outfile: Annotated[
            str,
            Field(description=_OUTFILE_DOC + " The cloud provider is appended."),
        ] = "architecture",
        varfile: _VarfileArg = None,
        workspace: _WorkspaceArg = "default",
        annotate: _AnnotateArg = "",
        planfile: _PlanfileArg = "",
        graphfile: _GraphfileArg = "",
        upgrade: _UpgradeArg = False,
        simplified: _SimplifiedArg = False,
        use_tf_names: _UseTfNamesArg = False,
        use_resource_names: _UseResourceNamesArg = False,
        fontsize: Annotated[Optional[int], Field(description=_FONTSIZE_DOC)] = None,
        iconsize: Annotated[Optional[int], Field(description=_ICONSIZE_DOC)] = None,
        title: Annotated[
            Optional[str],
            Field(
                description="Heading shown on the page. Overrides a title in the "
                "annotation file."
            ),
        ] = None,
    ) -> Dict[str, Any]:
        """Render a self-contained interactive HTML diagram for a human to open.

        The page embeds the diagram, every resource's metadata and its own
        JavaScript, so it works offline with no server. Nodes are clickable
        and searchable. Produce this when someone wants to explore an
        architecture themselves rather than read a static picture. Needs
        Terraform code; for a JSON graph use render_graph with format "svg".

        Returns {"path", "provider"} pointing at the generated .html file.
        """
        with _tool_errors():
            return mcp_service.run_interactive_html(
                source=source,
                outfile=outfile,
                varfile=varfile,
                workspace=workspace,
                annotate=annotate,
                planfile=planfile,
                graphfile=graphfile,
                upgrade=upgrade,
                simplified=simplified,
                use_tf_names=use_tf_names,
                use_resource_names=use_resource_names,
                fontsize=fontsize,
                iconsize=iconsize,
                title=title,
            )

    @mcp.tool()
    def diagram_guide(
        provider: Annotated[
            str,
            Field(description='"aws", "azure" or "gcp". One provider per diagram.'),
        ],
        pattern: Annotated[
            Optional[str],
            Field(
                description='Name of a pattern from the "patterns" list, to fetch '
                "that graph."
            ),
        ] = None,
    ) -> Dict[str, Any]:
        """Read this once before calling render_graph.

        Returns the TerraVision graph rules (types to prefer, containers,
        what is drawn and what is hidden), worked example graphs, every node
        type for the provider, and in "setup" whether Graphviz, Git and
        Terraform are installed: if Graphviz or Git is missing, tell the user
        what to install before drafting a diagram. Base your graph on the
        closest example and keep its level of detail: availability zones,
        public and private subnets, NAT gateways routed to the internet, and
        shared services in their group. It also lists patterns (EKS,
        SageMaker, Step Functions, GKE, AKS and more) drawn from TerraVision's
        output for real Terraform; call again with pattern to get one.
        """
        with _tool_errors():
            return mcp_service.diagram_guide(provider, pattern)

    @mcp.tool()
    def open_diagram_file(path: str, reveal: bool = False) -> Dict[str, Any]:
        """Open a rendered diagram file for the user on their own computer.

        Opens the file in its default app: the image viewer for .png, draw.io
        for .drawio (draw.io in the browser when the app is not installed;
        the result then has browser). With reveal, opens the folder that
        holds it instead. Only
        files returned by render_graph or generate_diagram in this session can
        be opened.

        Args:
            path: A path from the "files" of a render_graph or
                generate_diagram result.
            reveal: Show the file in its folder instead of opening it.

        Returns:
            {"opened", "reveal"}, and "browser" when a .drawio file opened
            in draw.io's web app.
        """
        with _tool_errors():
            return mcp_service.open_output_file(path, reveal=reveal)

    @mcp.tool(meta={"ui": {"visibility": ["app"]}})
    def diagram_file(path: str) -> Dict[str, Any]:
        """Return a rendered diagram file's contents to the TerraVision view.

        Used by the diagram view in chat apps to load the SVG and the graph
        JSON. Agents do not need it: read the paths in the result yourself.

        Args:
            path: A path from the "files" of a diagram result.

        Returns:
            {"name", "mimeType", "text"} for text files, or
            {"name", "mimeType", "blob"} with base64 content.
        """
        with _tool_errors():
            return mcp_service.read_output_file(path)

    return mcp


def serve(transport: str = "stdio", output_dir: Optional[str] = None) -> None:
    """Start the MCP server and block until the client disconnects.

    Args:
        transport: MCP transport to serve on. Only "stdio" is supported.
        output_dir: Directory generated files are written to. Defaults to the
            current working directory.

    Raises:
        McpServiceError: If output_dir is not usable.
        ValueError: If an unsupported transport is requested.
    """
    if transport != "stdio":
        raise ValueError(
            f"Unsupported transport {transport!r}. Only 'stdio' is supported."
        )
    mcp_service.set_output_dir(output_dir)
    build_server().run(transport="stdio")
