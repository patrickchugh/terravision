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
from typing import Any, Dict, Iterator, List, Optional

from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourcePermissions
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent

from modules import mcp_service
from modules.mcp_view import VIEW_HTML, VIEW_URI

_INSTRUCTIONS = """\
TerraVision draws cloud architecture diagrams with the official AWS, Azure and
GCP icons, from a description or from Terraform code. Use it for pictures of
cloud infrastructure only; use Mermaid or similar for sequence diagrams,
flowcharts and other diagrams that are not cloud infrastructure.

From a description (no Terraform): call diagram_guide once with the provider
(aws, azure or gcp) for the graph rules, worked examples and node types, then
write the graph and call render_graph with a title. Start from the closest
example and keep its level of detail: availability zones, public and private
subnets, the path to the internet and shared services.

From Terraform code: generate_diagram runs `terraform init` and `terraform plan`
against the source unless you supply planfile/graphfile, so a first call can
take minutes. generate_architecture_graph(services_only=True) is a cheap
overview of what a stack contains. Calls run one at a time.

render_graph and generate_diagram save a PNG, an SVG, an editable draw.io file
and the graph as .tvg.json, and return their paths plus a preview image. Look
at the preview to check the diagram before presenting it; if it looks wrong,
fix the graph, not TerraVision. If a render_graph result has warnings (an
unknown type with suggested replacements, arrows that will not be drawn), fix
the graph and render again. Apps that support MCP Apps also show it to the
user in an interactive view with buttons to open and edit the files.
open_diagram_file opens a file for the user on their own computer. Show the
user the graph JSON as well.
"""


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
        graph: Dict[str, List[str]],
        format: str = "png",
        outfile: str = "architecture",
        fontsize: Optional[int] = None,
        iconsize: Optional[int] = None,
        title: Optional[str] = None,
        preview: bool = True,
    ) -> CallToolResult:
        """Draw a professional cloud architecture diagram from a plain JSON graph.

        Use this whenever you need a cloud architecture diagram and do NOT have
        Terraform code. Call diagram_guide first for the rules, worked
        examples and node types. TerraVision renders the graph with the
        official AWS, Azure and GCP icon sets and draws each resource inside
        the VPC, subnet, zone or resource group you nest it in. Use the most
        specific types: aws_ecs_fargate (not aws_ecs_service), aws_rds_sqlserver,
        aws_rds_postgres, aws_rds_mysql or aws_rds_aurora (not
        aws_db_instance), aws_alb or aws_nlb (not aws_lb). Prefer this over
        Mermaid or hand-drawn SVG for any cloud architecture. Needs only
        Graphviz and Git; Terraform is not required.

        Args:
            graph: Object mapping each node address to the list of node
                addresses it connects to or contains. Node addresses are
                "<terraform_resource_type>.<name>", e.g.
                "aws_lambda_function.orders", "azurerm_key_vault.secrets",
                "google_cloud_run_service.api". Containers (aws_vpc,
                aws_subnet, azurerm_resource_group, tv_gcp_region and so on)
                list their children as connections. Use "~1", "~2" suffixes
                for numbered copies. External actors: tv_aws_users.<name>,
                tv_aws_internet.<name>, tv_aws_mobile_client.<name>,
                tv_aws_onprem.<name>, tv_azurerm_users.<name>,
                tv_azurerm_internet.<name>, tv_gcp_users_icon.<name>.
                Leaf nodes may be omitted as keys. Use one cloud provider
                per graph. The graph is drawn as written: arrows to
                containers, and to shared services such as CloudWatch log
                groups, ECR or Key Vault, are not drawn; list those services
                in aws_group.shared_services or azurerm_group.shared_services.
                Example: {"tv_aws_users.users": ["aws_cloudfront_distribution.cdn"],
                "aws_cloudfront_distribution.cdn": ["aws_s3_bucket.site"],
                "aws_vpc.main": ["aws_subnet.app"],
                "aws_subnet.app": ["aws_lambda_function.api"],
                "aws_lambda_function.api": ["aws_dynamodb_table.orders"]}
            format: "png", "svg", "pdf", "dot" or "drawio" (editable in
                draw.io and Lucidchart). Use "svg" to embed in Markdown.
            outfile: Output filename without extension. Plain name, not a
                path.
            fontsize: Label font size in points.
            iconsize: Icon size in pixels.
            title: Heading shown above the diagram, e.g. "Order Platform -
                Production". Defaults to "Cloud Architecture Diagram".
            preview: Include a preview image of the diagram in the result.

        Returns:
            {"path", "format", "provider", "title", "files", "graph_path",
            "node_count", "edge_count"}, plus a preview image. "files" holds
            the paths of the PNG, SVG, draw.io file and the graph (.tvg.json);
            "path" is the file in the requested format. "warnings" appears
            when parts of the graph will not draw as they read, such as an
            unknown type (with suggestions) or an arrow to a container: fix
            the graph and call render_graph again.
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
                )
            )

    @apps.tool(resource_uri=VIEW_URI)
    def generate_diagram(
        source: str,
        format: str = "png",
        outfile: str = "architecture",
        varfile: Optional[List[str]] = None,
        workspace: str = "default",
        annotate: str = "",
        planfile: str = "",
        graphfile: str = "",
        upgrade: bool = False,
        simplified: bool = False,
        use_tf_names: bool = False,
        use_resource_names: bool = False,
        fontsize: Optional[int] = None,
        iconsize: Optional[int] = None,
        title: Optional[str] = None,
        preview: bool = True,
    ) -> CallToolResult:
        """Render an architecture diagram from Terraform code to a file.

        Uses the official AWS, Azure and GCP icon sets. Because the diagram is
        derived from `terraform plan`, it reflects what the code actually
        deploys rather than an approximation.

        Args:
            source: Terraform directory, Git URL, or tfdata.json replay file.
            format: Output format. Use "drawio" for a file editable in
                draw.io, Lucidchart or any mxGraph editor; "svg" or "dot" for
                other text formats; "png" or "pdf" for images.
            outfile: Output filename without extension. Must be a plain name,
                not a path; the server decides the directory. The detected
                cloud provider is appended, so "architecture" becomes
                "architecture-aws".
            varfile: Paths to .tfvars files.
            workspace: Terraform workspace to select.
            annotate: Path to a terravision.yml annotation file.
            planfile: Path to an existing plan JSON. With graphfile, no
                Terraform run and no cloud credentials are needed.
            graphfile: Path to an existing `terraform graph` DOT file.
            upgrade: Run `terraform init -upgrade` to refresh modules.
            simplified: Show only services, omitting networking containers.
            use_tf_names: Label nodes with full Terraform resource names.
            use_resource_names: Label nodes with the deployed resource names
                from the plan.
            fontsize: Label font size in points.
            iconsize: Icon size in pixels.
            title: Heading shown above the diagram. Overrides any title in
                the annotation file.
            preview: Include a preview image of the diagram in the result.

        Returns:
            {"path", "format", "provider", "title", "files"}, plus a preview
            image. "files" holds the paths of the PNG, SVG, draw.io file and
            the graph as .tvg.json, which can be edited and rendered again
            with render_graph; "path" is the file in the requested format.
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
                )
            )

    # Extensions are read when the server is constructed, so the tools bound
    # to the diagram view must be registered on `apps` before this point.
    mcp = MCPServer(
        name="terravision",
        title="TerraVision",
        version=_version(),
        instructions=_INSTRUCTIONS,
        extensions=[apps],
    )

    @mcp.tool()
    def generate_architecture_graph(
        source: str,
        varfile: Optional[List[str]] = None,
        workspace: str = "default",
        annotate: str = "",
        planfile: str = "",
        graphfile: str = "",
        upgrade: bool = False,
        simplified: bool = False,
        services_only: bool = False,
    ) -> Dict[str, Any]:
        """Extract the cloud architecture of Terraform code as structured data.

        Runs Terraform, resolves variables, expands count/for_each, groups
        resources into their VPCs, subnets and availability zones, and infers
        the connections between them. This is the tool to use to reason about
        an architecture; the diagram tools render this same graph.

        Args:
            source: Terraform directory, a Git URL, or a TerraVision
                tfdata.json replay file. A .json source skips Terraform
                entirely and returns in seconds.
            varfile: Paths to .tfvars files. Different var files against the
                same code produce genuinely different architectures.
            workspace: Terraform workspace to select.
            annotate: Path to a terravision.yml annotation file that adds,
                removes or relabels nodes and connections.
            planfile: Path to an existing `terraform show -json` plan. With
                graphfile, Terraform is never invoked and no cloud
                credentials are needed.
            graphfile: Path to an existing `terraform graph` DOT file.
            upgrade: Run `terraform init -upgrade` to refresh modules.
            simplified: Drop networking containers (VPCs, subnets, security
                groups) and show only the services.
            services_only: Return just the deduplicated list of cloud service
                types instead of the full graph. Much smaller; use this first
                when you only need to know what a stack is built from.

        Returns:
            With services_only, {"services", "count", "provider"}. Otherwise
            {"graphdict", "node_count", "edge_count", "provider"}, where
            graphdict maps each Terraform resource address to the addresses it
            connects to or contains.
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
        source: str,
        outfile: str = "architecture",
        varfile: Optional[List[str]] = None,
        workspace: str = "default",
        annotate: str = "",
        planfile: str = "",
        graphfile: str = "",
        upgrade: bool = False,
        simplified: bool = False,
        use_tf_names: bool = False,
        use_resource_names: bool = False,
        fontsize: Optional[int] = None,
        iconsize: Optional[int] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Render a self-contained interactive HTML diagram for a human to open.

        The page embeds the diagram, every resource's metadata and its own
        JavaScript, so it works offline with no server. Nodes are clickable and
        searchable. Produce this when someone wants to explore an architecture
        themselves rather than read a static picture.

        Args:
            source: Terraform directory, Git URL, or tfdata.json replay file.
            outfile: Output filename without extension. Must be a plain name,
                not a path. The detected provider is appended.
            varfile: Paths to .tfvars files.
            workspace: Terraform workspace to select.
            annotate: Path to a terravision.yml annotation file.
            planfile: Path to an existing plan JSON.
            graphfile: Path to an existing `terraform graph` DOT file.
            upgrade: Run `terraform init -upgrade` to refresh modules.
            simplified: Show only services, omitting networking containers.
            use_tf_names: Label nodes with full Terraform resource names.
            use_resource_names: Label nodes with deployed resource names.
            fontsize: Label font size in points.
            iconsize: Icon size in pixels.
            title: Heading shown on the page. Overrides any title in the
                annotation file.

        Returns:
            {"path", "provider"} pointing at the generated .html file.
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
    def diagram_guide(provider: str, pattern: Optional[str] = None) -> Dict[str, Any]:
        """Read this once before calling render_graph.

        Returns the TerraVision graph rules (node types to prefer, which types
        are containers, what is drawn and what is hidden), worked example
        graphs and every node type for the provider. It also reports in
        "setup" whether Graphviz, Git and Terraform are installed: if
        Graphviz or Git is missing, tell the user what to install before
        drafting a diagram. Base your graph on the
        closest example and keep its level of detail: availability zones,
        public and private subnets, NAT gateways routed through an internet
        gateway to the internet, and shared services in their group.

        It also lists a library of patterns, such as EKS, SageMaker, Step
        Functions, GKE or AKS, drawn from TerraVision's output for real
        Terraform. Call again with pattern set to one of their names to get
        that graph when it matches the request.

        Args:
            provider: "aws", "azure" or "gcp". One provider per diagram.
            pattern: Name of a pattern from the "patterns" list, to fetch it.

        Returns:
            {"provider", "setup", "rules", "examples", "node_types",
            "patterns", "next_step"}; with pattern, {"provider", "pattern",
            "description", "graph"}.
        """
        with _tool_errors():
            return mcp_service.diagram_guide(provider, pattern)

    @mcp.tool()
    def open_diagram_file(path: str, reveal: bool = False) -> Dict[str, Any]:
        """Open a rendered diagram file for the user on their own computer.

        Opens the file in its default app: the image viewer for .png, draw.io
        for .drawio. With reveal, opens the folder that holds it instead. Only
        files returned by render_graph or generate_diagram in this session can
        be opened.

        Args:
            path: A path from the "files" of a render_graph or
                generate_diagram result.
            reveal: Show the file in its folder instead of opening it.

        Returns:
            {"opened", "reveal"}.
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
