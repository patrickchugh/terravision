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

from typing import Any, Dict, List, Optional

from mcp.server import MCPServer

from modules import mcp_service

_INSTRUCTIONS = """\
TerraVision turns Terraform code into cloud architecture diagrams.

Every tool runs `terraform init` and `terraform plan` against the source unless
you supply `planfile`/`graphfile`, so a first call against a real repository can
take minutes. Calls are executed one at a time.

Start with generate_architecture_graph(services_only=True) for a cheap overview
of what a stack contains, then request the full graph or a diagram if needed.

Diagram tools return the path to a generated file, not its contents. Read the
file yourself to inspect text formats such as drawio, svg or dot.
"""


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
    mcp = MCPServer(
        name="terravision",
        title="TerraVision",
        version=_version(),
        instructions=_INSTRUCTIONS,
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
    ) -> Dict[str, Any]:
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

        Returns:
            {"path", "format", "provider"}. The file's contents are not
            returned; read the path if you need them.
        """
        return mcp_service.run_diagram(
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

        Returns:
            {"path", "provider"} pointing at the generated .html file.
        """
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
        )

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
