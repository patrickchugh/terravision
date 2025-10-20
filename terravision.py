#!/usr/bin/env python
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import requests

import click

import modules.annotations as annotations
import modules.drawing as drawing
import modules.fileparser as fileparser
import modules.graphmaker as graphmaker
import modules.helpers as helpers
import modules.interpreter as interpreter
import modules.tfwrapper as tfwrapper
import modules.cloud_config as cloud_config


__version__ = "0.8"


def my_excepthook(exc_type, exc_value, exc_traceback):
    print(f"Unhandled error: {exc_type}, {exc_value}, {exc_traceback}")


def _show_banner():
    banner = (
        "\n\n\n"
        " _____                          _     _             \n"
        "/__   \\___ _ __ _ __ __ ___   _(_)___(_) ___  _ __  \n"
        "  / /\\/ _ \\ '__| '__/ _` \\ \\ / / / __| |/ _ \\| '_ \\ \n"
        " / / |  __/ |  | | | (_| |\\ V /| \\__ \\ | (_) | | | |\n"
        " \\/   \\___|_|  |_|  \\__,_| \\_/ |_|___/_|\\___/|_| |_|\n"
        "                                                    \n"
        "\n"
    )
    print(banner)


def _validate_source(source: list):
    if source[0].endswith(".tf"):
        click.echo(
            click.style(
                "\nERROR: You have passed a .tf file as source. Please pass a folder containing .tf files or a git URL.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def _load_json_source(source: str):
    with open(source, "r") as file:
        jsondata = json.load(file)
    tfdata = {"annotations": {}, "meta_data": {}}
    if "all_resource" in jsondata:
        click.echo(
            "Source appears to be a JSON of previous debug output. Will not call terraform binary."
        )
        tfdata = jsondata
        tfdata["graphdict"] = dict(tfdata["original_graphdict"])
        tfdata["metadata"] = dict(tfdata["original_metadata"])
    else:
        click.echo(
            "Source is a pre-generated JSON tfgraph file. Will not call terraform binary or AI model."
        )
        tfdata["graphdict"] = jsondata
    return tfdata


def _process_terraform_source(
    source: list, varfile: list, workspace: str, annotate: str, debug: bool
):
    tfdata = tfwrapper.tf_initplan(source, varfile, workspace)
    tfdata = tfwrapper.tf_makegraph(tfdata)
    codepath = (
        [tfdata["codepath"]]
        if isinstance(tfdata["codepath"], str)
        else tfdata["codepath"]
    )
    tfdata = fileparser.read_tfsource(codepath, varfile, annotate, tfdata)
    if debug:
        helpers.export_tfdata(tfdata)
    return tfdata


def _enrich_graph_data(tfdata: dict, debug: bool, already_processed: bool) -> dict:
    tfdata = interpreter.prefix_module_names(tfdata)
    tfdata = interpreter.resolve_all_variables(tfdata, debug, already_processed)
    tfdata = graphmaker.add_relations(tfdata)
    tfdata = graphmaker.consolidate_nodes(tfdata)
    tfdata = annotations.add_annotations(tfdata)
    tfdata = graphmaker.handle_special_resources(tfdata)
    tfdata = graphmaker.handle_variants(tfdata)
    tfdata = graphmaker.create_multiple_resources(tfdata)
    tfdata = graphmaker.reverse_relations(tfdata)
    tfdata = helpers.remove_recursive_links(tfdata)
    tfdata = graphmaker.match_resources(tfdata)
    return tfdata


def _print_graph_debug(outputdict: dict, title: str):
    click.echo(click.style(f"\n{title}:\n", fg="white", bold=True))
    click.echo(json.dumps(outputdict, indent=4, sort_keys=True))


def compile_tfdata(
    source: list, varfile: list, workspace: str, debug: bool, annotate=""
):
    """Compile Terraform data from source files into enriched graph dictionary.

    Args:
        source: List of source paths (folders, git URLs, or JSON files)
        varfile: List of paths to .tfvars files
        workspace: Terraform workspace name
        debug: Enable debug output and export tracedata
        annotate: Path to custom annotations YAML file

    Returns:
        dict: Enriched tfdata dictionary with graphdict and metadata
    """
    _validate_source(source)
    already_processed = False
    if source[0].endswith(".json"):
        tfdata = _load_json_source(source[0])
        already_processed = True
        if "all_resource" not in tfdata:
            _print_graph_debug(tfdata["graphdict"], "Loaded JSON graphviz dictionary")
    else:
        tfdata = _process_terraform_source(source, varfile, workspace, annotate, debug)
    if "all_resource" in tfdata:
        _print_graph_debug(tfdata["graphdict"], "Terraform JSON graph dictionary")
        tfdata = _enrich_graph_data(tfdata, debug, already_processed)
        tfdata["graphdict"] = helpers.sort_graphdict(tfdata["graphdict"])
        _print_graph_debug(tfdata["graphdict"], "Enriched graphviz dictionary")
    return tfdata


def _check_dependencies() -> None:
    """Check if required command-line tools are available."""
    dependencies = ["dot", "gvpr", "git", "terraform"]
    bundle_dir = Path(__file__).parent
    sys.path.append(str(bundle_dir))
    for exe in dependencies:
        location = shutil.which(exe) or os.path.isfile(exe)
        if location:
            click.echo(f"  {exe} command detected: {location}")
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: {exe} command executable not detected in path. Please ensure you have installed all required dependencies first",
                    fg="red",
                    # amazonq-ignore-next-line
                    bold=True,
                )
                # amazonq-ignore-next-line
            )
            sys.exit()


def _check_terraform_version() -> None:
    """Validate Terraform version is compatible."""
    version_file = "terraform_version.txt"

    try:
        result = subprocess.run(
            ["terraform", "-v"], capture_output=True, text=True, check=True
        )
        version_output = result.stdout

        version_line = version_output.split("\n")[0]
        print(f"  terraform version detected: {version_line}")
        version = version_line.split(" ")[1].replace("v", "")
        version_major = version.split(".")[0]

        if version_major != "1":
            click.echo(
                click.style(
                    f"\n  ERROR: Terraform Version '{version}' is not supported. Please upgrade to >= v1.0.0",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    except (subprocess.CalledProcessError, IndexError, FileNotFoundError) as e:
        click.echo(
            click.style(
                f"\n  ERROR: Failed to check Terraform version: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def preflight_check() -> None:
    """Check required dependencies and Terraform version compatibility."""
    click.echo(click.style("\nPreflight check..", fg="white", bold=True))
    _check_dependencies()
    _check_terraform_version()
    click.echo("\n")


@click.version_option(version=__version__, prog_name="terravision")
@click.group()
def cli():
    """
    TerraVision generates cloud architecture diagrams and documentation from Terraform scripts

    For help with a specific command type:

    terravision [COMMAND] --help

    """
    pass


@cli.command()
@click.option("--debug", is_flag=True, default=False, help="Dump exception tracebacks")
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL, Folder or .JSON file)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    # amazonq-ignore-next-line
    "--varfile",
    multiple=True,
    default=[],
    help="Path to .tfvars variables file",
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output diagram (default architecture.dot.png)",
)
@click.option("--format", default="png", help="File format (png/pdf/svg/bmp)")
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
@click.option("--avl_classes", hidden=True)
def draw(
    debug,
    source,
    workspace,
    varfile,
    outfile,
    format,
    show,
    simplified,
    annotate,
    avl_classes,
):
    """Draws Architecture Diagram"""
    if not debug:
        sys.excepthook = my_excepthook
    _show_banner()
    preflight_check()
    tfdata = compile_tfdata(source, varfile, workspace, debug, annotate)
    drawing.render_diagram(tfdata, show, simplified, outfile, format, source)


@cli.command()
@click.option("--debug", is_flag=True, default=False, help="Dump exception tracebacks")
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL or folder)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    "--varfile", multiple=True, default=[], help="Path to .tfvars variables file"
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
@click.option("--avl_classes", hidden=True)
def graphdata(
    debug,
    source,
    varfile,
    workspace,
    show_services,
    annotate,
    avl_classes,
    outfile="graphdata.json",
):
    """List Cloud Resources and Relations as JSON"""
    if not debug:
        sys.excepthook = my_excepthook
    _show_banner()
    preflight_check()
    tfdata = compile_tfdata(source, varfile, workspace, debug, annotate)
    click.echo(click.style("\nOutput JSON Dictionary :", fg="white", bold=True))
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


if __name__ == "__main__":
    cli(
        default_map={
            "draw": {"avl_classes": dir()},
            "graphlist": {"avl_classes": dir()},
        }
    )
