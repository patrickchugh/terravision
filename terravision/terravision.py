#!/usr/bin/env python
from typing import Any, Dict, List, Optional
import json
import sys
import click

import modules.annotations as annotations
import modules.drawing as drawing
import modules.graphmaker as graphmaker
import modules.html_renderer as html_renderer
import modules.helpers as helpers
import modules.interpreter as interpreter
import modules.tfwrapper as tfwrapper
import modules.tgwrapper as tgwrapper
import modules.resource_handlers as resource_handlers
import modules.llm as llm
import modules.validators as validators
import modules.fileparser as fileparser
from modules.config_loader import load_config
from modules.provider_detector import detect_providers
from importlib.metadata import version

__version__ = version("terravision")


class ColorHelpMixin:
    """Mixin to colorize Click help output."""

    def format_help(self, ctx, formatter):
        tmp_formatter = click.HelpFormatter()
        super().format_help(ctx, tmp_formatter)
        raw = tmp_formatter.getvalue()
        in_commands = False
        for line in raw.splitlines(True):
            if line.startswith("Usage:"):
                formatter.write(click.style(line, fg="cyan", bold=True))
                in_commands = False
            elif line.startswith("Commands:"):
                formatter.write(click.style(line, fg="yellow", bold=True))
                in_commands = True
            elif line.startswith("Options:"):
                formatter.write(click.style(line, fg="yellow", bold=True))
                in_commands = False
            elif line.strip().startswith("--") or (
                in_commands and line.startswith("  ") and line.strip()
            ):
                stripped = line.lstrip()
                indent = line[: len(line) - len(stripped)]
                parts = stripped.split("  ", 1)
                if len(parts) == 2:
                    formatter.write(
                        indent + click.style(parts[0], fg="green") + "  " + parts[1]
                    )
                else:
                    formatter.write(indent + click.style(stripped, fg="green"))
            else:
                formatter.write(line)


class ColorGroup(ColorHelpMixin, click.Group):
    """Click Group with colorized help."""

    pass


class ColorCommand(ColorHelpMixin, click.Command):
    pass


def my_excepthook(exc_type: type, exc_value: BaseException, exc_traceback: Any) -> None:
    """Quiet exception hook used when --debug is OFF.

    Prints a single-line error without a stack trace. With --debug ON we
    leave Python's default hook in place so users get a full traceback.
    """
    click.echo(click.style(f"\nERROR: {exc_value}", fg="red", bold=True), err=True)


def _install_excepthook(debug: bool) -> None:
    """Install the user-friendly excepthook unless --debug is set."""
    if not debug:
        sys.excepthook = my_excepthook


def _safe_compile_tfdata(
    debug: bool,
    source: str,
    varfile: tuple,
    workspace: str,
    annotate: str = "",
    planfile: str = "",
    graphfile: str = "",
    upgrade: bool = False,
    aibackend: str = "",
) -> Dict[str, Any]:
    """Run compile_tfdata with TerravisionError handling.

    On a TerravisionError, prints the message and (when --debug) writes
    whatever partial tfdata was built to tfdata.json so the failure can be
    diagnosed offline. Exits with status 1.
    """
    try:
        return compile_tfdata(
            source,
            varfile,
            workspace,
            debug,
            annotate,
            planfile,
            graphfile,
            upgrade,
            aibackend=aibackend,
        )
    except helpers.TerravisionError as e:
        click.echo(click.style(f"\nERROR: {e}", fg="red", bold=True), err=True)
        if debug and e.tfdata is not None:
            try:
                helpers.export_tfdata(e.tfdata)
            except Exception as dump_err:
                click.echo(
                    click.style(
                        f"\nWARNING: Could not write tfdata.json: {dump_err}",
                        fg="yellow",
                    ),
                    err=True,
                )
        sys.exit(1)


def _show_banner() -> None:
    """Display TerraVision ASCII banner."""
    banner = (
        " _____                          _     _             \n"
        "/__   \\___ _ __ _ __ __ ___   _(_)___(_) ___  _ __  \n"
        "  / /\\/ _ \\ '__| '__/ _` \\ \\ / / / __| |/ _ \\| '_ \\ \n"
        " / / |  __/ |  | | | (_| |\\ V /| \\__ \\ | (_) | | | |\n"
        " \\/   \\___|_|  |_|  \\__,_| \\_/ |_|___/_|\\___/|_| |_|\n"
    )
    click.echo("\n")
    click.echo(click.style(banner, fg="cyan", bold=True))
    click.echo()


def _enrich_graph_data(
    tfdata: Dict[str, Any], debug: bool, already_processed: bool
) -> Dict[str, Any]:
    """Enrich graph data with relationships and transformations.

    Args:
        tfdata: Terraform data dictionary
        debug: Enable debug mode
        already_processed: Whether data was already processed

    Returns:
        Enriched tfdata dictionary
    """
    tfdata = interpreter.prefix_module_names(tfdata)
    tfdata = interpreter.resolve_all_variables(tfdata, debug, already_processed)
    tfdata = resource_handlers.handle_special_cases(tfdata)
    tfdata = graphmaker.inject_data_source_nodes(tfdata)
    tfdata = graphmaker.add_relations(tfdata)
    tfdata = graphmaker.consolidate_nodes(tfdata)
    tfdata = annotations.add_annotations(tfdata)
    tfdata = graphmaker.detect_and_set_counts(tfdata)
    tfdata = graphmaker.handle_special_resources(tfdata)
    tfdata = graphmaker.handle_variants(tfdata)
    tfdata = graphmaker.create_multiple_resources(tfdata)
    tfdata = graphmaker.cleanup_cross_subnet_connections(tfdata)
    tfdata = graphmaker.reverse_relations(tfdata)
    # Bidirectional links are now rendered as two-way arrows instead of being removed
    # tfdata = helpers.remove_recursive_links(tfdata)
    tfdata = helpers.find_bidirectional_links(tfdata)
    tfdata = resource_handlers.match_resources(tfdata)

    return tfdata


def _print_graph_debug(outputdict: Dict[str, Any], title: str) -> None:
    """Print formatted graph dictionary for debugging.

    Args:
        outputdict: Dictionary to print
        title: Title to display
    """
    click.echo(click.style(f"\n{title}:\n", fg="white", bold=True))
    click.echo(json.dumps(outputdict, indent=4, sort_keys=True))


def compile_tfdata(
    source: str,
    varfile: List[str],
    workspace: str,
    debug: bool,
    annotate: str = "",
    planfile: str = "",
    graphfile: str = "",
    upgrade: bool = False,
    aibackend: str = "",
) -> Dict[str, Any]:
    """Compile Terraform data from source files into enriched graph dictionary.

    Args:
        source: Source path (folder, git URL, or JSON file)
        varfile: List of paths to .tfvars files
        workspace: Terraform workspace name
        debug: Enable debug output and export tracedata
        annotate: Path to custom annotations YAML file
        planfile: Path to pre-generated Terraform plan JSON file
        graphfile: Path to pre-generated Terraform graph DOT file
        aibackend: Optional AI backend ("ollama" / "bedrock") for AI
            annotation generation. Empty string disables AI.

    Returns:
        Enriched tfdata dictionary with graphdict and metadata
    """
    already_processed = False
    if planfile:
        validators.validate_pregenerated_inputs(planfile, graphfile, source)
        tfdata = tfwrapper.process_pregenerated_source(
            planfile, graphfile, source, annotate, debug
        )
    elif source.endswith(".json"):
        validators.validate_source(source)
        tfdata = tfwrapper.load_json_source(source)
        already_processed = True
        if "all_resource" not in tfdata:
            _print_graph_debug(tfdata["graphdict"], "Loaded JSON graphviz dictionary")
    else:
        validators.validate_source(source)
        # Check for Terragrunt source before falling back to Terraform
        tg_detection = validators.is_terragrunt_source(source)
        if tg_detection["is_terragrunt"]:
            is_multi = tg_detection["is_multi_module"]
            n = len(tg_detection["child_modules"])
            mode = f"multi-module, {n} child modules" if is_multi else "single-module"
            click.echo(
                click.style(
                    f"\nTerragrunt detected ({mode})\n",
                    fg="cyan",
                    bold=True,
                )
            )
            if is_multi:
                tfdata = tgwrapper.tg_run_all_plan(
                    source, varfile, workspace, debug, upgrade
                )
            else:
                tfdata = tgwrapper.tg_initplan(
                    source, varfile, workspace, debug, upgrade
                )
            # Continue with standard pipeline: graph building + source parsing
            tfdata = tfwrapper.tf_makegraph(tfdata, debug)
            # For multi-module: inject cross-module refs now that meta_data is populated
            dep_info = tfdata.pop("_tg_dependency_info", None)
            if dep_info:
                tfdata = tgwrapper._inject_dependency_refs(
                    tfdata,
                    dep_info["per_module_deps"],
                    dep_info["per_module_resources"],
                    dep_info["source_root"],
                )
            codepath = (
                [tfdata["codepath"]]
                if isinstance(tfdata["codepath"], str)
                else tfdata["codepath"]
            )
            tfdata = fileparser.read_tfsource(codepath, varfile, annotate, tfdata)
            if debug:
                helpers.export_tfdata(tfdata)
        else:
            tfdata = tfwrapper.process_terraform_source(
                source, varfile, workspace, annotate, debug, upgrade
            )

    # Detect cloud provider and store in tfdata (multi-cloud support)
    if "all_resource" in tfdata and "provider_detection" not in tfdata:
        try:
            provider_detection = detect_providers(tfdata)
            tfdata["provider_detection"] = provider_detection
            click.echo(
                click.style(
                    f"\nDetected cloud provider: {provider_detection['primary_provider'].upper()} "
                    f"({provider_detection['resource_counts'][provider_detection['primary_provider']]} resources)\n",
                    fg="cyan",
                    bold=True,
                )
            )
        except Exception as e:
            raise helpers.TerravisionError(
                f"Failed to detect cloud provider: {e}", tfdata=tfdata
            )

    if "all_resource" in tfdata:
        _print_graph_debug(tfdata["graphdict"], "Terraform JSON graph dictionary")
        tfdata = _enrich_graph_data(tfdata, debug, already_processed)
        tfdata["graphdict"] = helpers.sort_graphdict(tfdata["graphdict"])
        _print_graph_debug(tfdata["graphdict"], "Enriched graphviz dictionary")

        # AI annotations run AFTER full enrichment so the LLM sees the
        # final graphdict that the renderer will actually iterate. If
        # the AI ran earlier, downstream transformations
        # (handle_special_resources, create_multiple_resources, etc.)
        # would rename or expand the nodes the AI labelled, and the
        # labels would never reach the renderer because they were
        # keyed on intermediate names. Running AI last also means the
        # AI sees auto-annotation nodes (tv_aws_users.users etc.)
        # already in the inventory and connects to them directly
        # instead of trying to add them again. Failures inside the AI
        # path return None and fall through to the default pipeline.
        if aibackend and "all_resource" in tfdata:
            ai_dict = llm.generate_ai_annotations(
                tfdata,
                aibackend,
                source_dir=source if isinstance(source, str) else None,
                output_dir=None,
            )
            if ai_dict:
                tfdata = annotations.apply_ai_annotations(tfdata, ai_dict)
    return tfdata


def preflight_check(ai_backend: Optional[str] = None) -> None:
    """Check required dependencies and Terraform version compatibility.

    Args:
        ai_backend: AI backend to validate ('ollama' or 'bedrock')
    """
    click.echo(click.style("\nPreflight check..", fg="white", bold=True))
    helpers.check_dependencies()
    helpers.check_terraform_version()

    if ai_backend:
        # Load default AWS config for preflight (endpoints are the same across providers)
        default_config = load_config("aws")

        if ai_backend.lower() == "ollama":
            llm.check_ollama_server(default_config.OLLAMA_HOST)
        elif ai_backend.lower() == "bedrock":
            llm.check_bedrock_endpoint(default_config.BEDROCK_API_ENDPOINT)

    click.echo("\n")


@click.version_option(version=__version__, prog_name="terravision")
@click.group(cls=ColorGroup, invoke_without_command=True)
@click.pass_context
def cli(ctx) -> None:
    """TerraVision generates professional cloud architecture diagrams from Terraform HCL code.

    For help with a specific command type:
    terravision [COMMAND] --help
    """
    if not ctx.invoked_subcommand:
        _show_banner()
        click.echo(ctx.get_help())


@cli.command(cls=ColorCommand)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Dump exception tracebacks, creates tfdata.json replay file",
)
@click.option(
    "--source",
    default=".",
    help="Source files location (Git URL, Folder or .JSON file)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    "--varfile",
    multiple=True,
    default=[],
    help="Path to .tfvars variables file (can be specified multiple times)",
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output diagram (default architecture.dot.png)",
)
@click.option(
    "--format", default="png", help="Output format(png, svg, pdf, jpg, drawio etc.)"
)
@click.option(
    "--show", is_flag=True, default=False, help="Show diagram after generation"
)
@click.option(
    "--simplified",
    is_flag=True,
    default=False,
    help="Simplified high level services shown only",
)
@click.option("--annotate", default="", help="Path to custom annotations file (YAML)")
@click.option(
    "--ai-annotate",
    default="",
    type=click.Choice(["", "bedrock", "ollama"], case_sensitive=False),
    help="Generate AI annotations file using the named backend (bedrock or ollama)",
)
@click.option("--avl_classes", hidden=True)
@click.option(
    "--planfile",
    default="",
    type=click.Path(),
    help="Path to Terraform plan JSON (terraform show -json)",
)
@click.option(
    "--graphfile",
    default="",
    type=click.Path(),
    help="Path to Terraform graph DOT (terraform graph)",
)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Run terraform init with -upgrade to update modules/providers",
)
def draw(
    debug: bool,
    source: str,
    workspace: str,
    varfile: tuple,
    outfile: str,
    format: str,
    show: bool,
    simplified: bool,
    annotate: str,
    ai_annotate: str,
    avl_classes: Any,
    planfile: str,
    graphfile: str,
    upgrade: bool,
) -> None:
    """Draw architecture diagram from Terraform code."""
    _install_excepthook(debug)
    _show_banner()

    if planfile and (workspace != "default" or varfile):
        click.echo(
            click.style(
                "WARNING: --workspace and --varfile are ignored when --planfile is provided.",
                fg="yellow",
            )
        )
    preflight_check(ai_annotate if not planfile else None)
    tfdata = _safe_compile_tfdata(
        debug,
        source,
        varfile,
        workspace,
        annotate,
        planfile,
        graphfile,
        upgrade,
        aibackend=ai_annotate,
    )

    # Strip networking groups for simplified diagrams, bridging connections
    if simplified:
        graphmaker.simplify_graphdict(tfdata)
        _print_graph_debug(tfdata["graphdict"], "Simplified graphviz dictionary")

    # Add provider suffix to output filename for non-AWS providers
    final_outfile = outfile
    if tfdata.get("provider_detection"):
        provider = tfdata["provider_detection"].get("primary_provider", "aws")
        if provider != "aws" and not outfile.endswith(f"-{provider}"):
            final_outfile = f"{outfile}-{provider}"

    drawing.render_diagram(tfdata, show, final_outfile, format, source)


@cli.command(cls=ColorCommand)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Dump exception tracebacks, creates tfdata.json replay file",
)
@click.option(
    "--source",
    default=".",
    help="Source files location (Git URL or folder)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    "--varfile",
    multiple=True,
    default=[],
    help="Path to .tfvars variables file (can be specified multiple times)",
)
@click.option(
    "--show_services",
    is_flag=True,
    default=False,
    help="Only show unique list of cloud services actually used",
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output list (default architecture.json)",
)
@click.option("--annotate", default="", help="Path to custom annotations file (YAML)")
@click.option(
    "--simplified",
    is_flag=True,
    default=False,
    help="Simplified high level services shown only",
)
@click.option(
    "--ai-annotate",
    default="",
    type=click.Choice(["", "bedrock", "ollama"], case_sensitive=False),
    help="Generate AI annotations file using the named backend (bedrock or ollama)",
)
@click.option("--avl_classes", hidden=True)
@click.option(
    "--planfile",
    default="",
    type=click.Path(),
    help="Path to Terraform plan JSON (terraform show -json)",
)
@click.option(
    "--graphfile",
    default="",
    type=click.Path(),
    help="Path to Terraform graph DOT (terraform graph)",
)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Run terraform init with -upgrade to update modules/providers",
)
def graphdata(
    debug: bool,
    source: str,
    varfile: tuple,
    workspace: str,
    show_services: bool,
    simplified: bool,
    annotate: str,
    ai_annotate: str,
    avl_classes: Any,
    outfile: str = "graphdata.json",
    planfile: str = "",
    graphfile: str = "",
    upgrade: bool = False,
) -> None:
    """List cloud resources and relations as drawable JSON."""
    _install_excepthook(debug)
    _show_banner()

    if planfile and (workspace != "default" or varfile):
        click.echo(
            click.style(
                "WARNING: --workspace and --varfile are ignored when --planfile is provided.",
                fg="yellow",
            )
        )
    preflight_check(ai_annotate if not planfile else None)
    tfdata = _safe_compile_tfdata(
        debug,
        source,
        varfile,
        workspace,
        annotate,
        planfile,
        graphfile,
        upgrade,
        aibackend=ai_annotate if not show_services else "",
    )
    if simplified:
        graphmaker.simplify_graphdict(tfdata)
    click.echo(click.style("\nFinal Output JSON Dictionary :", fg="white", bold=True))
    unique = helpers.unique_services(tfdata["graphdict"])
    click.echo(
        json.dumps(
            tfdata["graphdict"] if not show_services else unique,
            indent=4,
            sort_keys=True,
        )
    )
    if not outfile.endswith(".json"):
        outfile += ".json"
    click.echo(f"\nExporting graph object into file {outfile}")
    with open(outfile, "w") as f:
        json.dump(
            tfdata["graphdict"] if not show_services else unique,
            f,
            indent=4,
            sort_keys=True,
        )
    click.echo("\nCompleted!")


@cli.command(cls=ColorCommand)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Dump exception tracebacks, creates tfdata.json replay file",
)
@click.option(
    "--source",
    default=".",
    help="Source files location (Git URL, Folder or .JSON file)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    "--varfile",
    multiple=True,
    default=[],
    help="Path to .tfvars variables file (can be specified multiple times)",
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output HTML diagram (default architecture.html)",
)
@click.option(
    "--show", is_flag=True, default=False, help="Open HTML in browser after generation"
)
@click.option(
    "--simplified",
    is_flag=True,
    default=False,
    help="Simplified high level services shown only",
)
@click.option("--annotate", default="", help="Path to custom annotations file (YAML)")
@click.option(
    "--planfile",
    default="",
    type=click.Path(),
    help="Path to Terraform plan JSON (terraform show -json)",
)
@click.option(
    "--graphfile",
    default="",
    type=click.Path(),
    help="Path to Terraform graph DOT (terraform graph)",
)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Run terraform init with -upgrade to update modules/providers",
)
@click.option("--format", default="", hidden=True)
@click.option("--ai-annotate", default="", hidden=True)
@click.option("--avl_classes", hidden=True)
def visualise(
    debug: bool,
    source: str,
    workspace: str,
    varfile: tuple,
    outfile: str,
    show: bool,
    simplified: bool,
    annotate: str,
    planfile: str,
    graphfile: str,
    upgrade: bool,
    format: str,
    ai_annotate: str,
    avl_classes: Any,
) -> None:
    """Generate interactive HTML architecture diagram"""
    _install_excepthook(debug)
    _show_banner()

    # Warn about inapplicable flags
    if format:
        click.echo(
            click.style(
                "WARNING: --format is not applicable to the visualise command. HTML is the only output format.",
                fg="yellow",
            )
        )
    if ai_annotate:
        click.echo(
            click.style(
                "WARNING: --ai-annotate is not applicable to the visualise command.",
                fg="yellow",
            )
        )

    if planfile and (workspace != "default" or varfile):
        click.echo(
            click.style(
                "WARNING: --workspace and --varfile are ignored when --planfile is provided.",
                fg="yellow",
            )
        )

    preflight_check(None)
    tfdata = _safe_compile_tfdata(
        debug, source, varfile, workspace, annotate, planfile, graphfile, upgrade
    )

    # Strip networking groups for simplified diagrams
    if simplified:
        graphmaker.simplify_graphdict(tfdata)

    # Add provider suffix to output filename for non-AWS providers
    final_outfile = outfile
    if tfdata.get("provider_detection"):
        provider = tfdata["provider_detection"].get("primary_provider", "aws")
        if provider != "aws" and not outfile.endswith(f"-{provider}"):
            final_outfile = f"{outfile}-{provider}"

    html_renderer.render_html(tfdata, show, final_outfile, source)


def main():
    cli(
        default_map={
            "draw": {"avl_classes": dir()},
            "graphdata": {"avl_classes": dir()},
            "visualise": {"avl_classes": dir()},
        }
    )


if __name__ == "__main__":
    main()
