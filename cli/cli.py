#!/usr/bin/env python
import json
import os
import shutil
import sys
import click
import modules.drawing as drawing
import modules.fileparser as fileparser
import modules.graphmaker as graphmaker
import modules.helpers as helpers
import modules.interpreter as interpreter
import modules.tfwrapper as tfwrapper
import modules.annotations as annotations
from pathlib import Path
from pprint import pprint


def my_excepthook(type, value, traceback):
    print(f"Unhandled error: {type}, {value}, {traceback}")


def show_banner():
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


def compile_tfdata(source: list, varfile: list, workspace: str, debug: bool, annotate=""):
    if source[0].endswith(".json"):
        file = open(source[0], "r")
        tfdata = dict()
        tfdata["annotations"] = dict()
        tfdata["meta_data"] = dict()
        tfdata["graphdict"] = json.load(file)
        return tfdata
    # Call terraform binary to extract a graph and plan info from output
    tfdata = tfwrapper.tf_initplan(source, varfile, workspace)
    # tfdata["workdir"] = source[0]
    # Make initial graphdict from Terraform graph in the format {node: [connected_node1,connected_node2]}
    tfdata = tfwrapper.tf_makegraph(tfdata)
    # Show original dict
    click.echo(click.style(f"\nUnprocessed terraform graph dictionary:\n", fg="white", bold=True))
    click.echo(json.dumps(tfdata["graphdict"], indent=4, sort_keys=True))
    # Parse HCL files from Terraform cache to gather resource info
    codepath = [tfdata["codepath"]] if isinstance(tfdata["codepath"], str) else tfdata["codepath"]
    tfdata = fileparser.read_tfsource(codepath, varfile, annotate, tfdata)
    # Handle all variables found in metadata
    tfdata = interpreter.resolve_all_variables(tfdata, debug)
    # Supplement graphdict with relationships from HCL files
    tfdata = graphmaker.add_relations(tfdata)
    # Handle consolidated nodes where multiple resources are grouped into one node
    tfdata = graphmaker.consolidate_nodes(tfdata)
    # Handle automatic and user annotations
    tfdata = annotations.add_annotations(tfdata)
    # Handle special relationships that require post-processing
    tfdata = graphmaker.handle_special_resources(tfdata)
    # Handle variant of services
    tfdata = graphmaker.handle_variants(tfdata)
    # Duplicate resources across AZs and Subnets where necessary
    tfdata = graphmaker.create_multiple_resources(tfdata)
    # Reverse relationship directions for certain original tfgraph connections
    tfdata = graphmaker.reverse_relations(tfdata)
    # Dump final graphdict
    click.echo(click.style(f"\nEnriched graphviz dictionary:\n", fg="white", bold=True))
    tfdata["graphdict"] = helpers.sort_graphdict(tfdata["graphdict"])
    click.echo(json.dumps(tfdata["graphdict"], indent=4, sort_keys=True))
    return tfdata


def preflight_check():
    click.echo(click.style("\nPreflight check..", fg="white", bold=True))
    dependencies = ["dot", "gvpr", "git", "terraform"]
    bundle_dir = Path(__file__).parent
    sys.path.append(bundle_dir)
    for exe in dependencies:
        binary = Path.cwd() / bundle_dir / exe
        location = shutil.which(exe) or os.path.isfile(exe)
        if location:
            click.echo(f"  {exe} command detected: {location}")
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: {exe} command executable not detected in path. Please ensure you have installed all required dependencies first",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    # check the terraform version is suitable for terravision
    click.echo(click.style("\nChecking Terraform Version...", fg="white", bold=True))
    returncode = os.system("terraform -v >> terraform_version.txt")
    # read the file and ensure the version is correct
    with open("terraform_version.txt", "r") as fh:
        data = fh.read().split("\n")

    os.remove("terraform_version.txt")

    # take just the first line
    version_line = data[0]
    print(f"\n{version_line}")
    version = version_line.split(" ")[1].replace("v", "")

    # break up version numbers
    version_major = version.split(".")[0]

    # if version major != 1
    if version_major != "1":
        click.echo(
            click.style(
                f"\n  ERROR: Terraform Version '{version}' is not supported. Please upgrade to >= v1.0.0",
                fg="red",
                bold=True,
            )
        )
        sys.exit()
    return


# Default help banner
@click.version_option(version=0.5, prog_name="terravision")
@click.group()
def cli():
    """
    Terravision generates professional cloud architecture diagrams from Terraform scripts

    For help with a specific command type:

    terravision [COMMAND] --help

    """
    pass


# Draw Diagram Command
@cli.command()
@click.option("--debug", is_flag=True, default=False, help="Dump exception tracebacks")
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL, Folder or .JSON file)",
)
@click.option(
    "--workspace", multiple=False, default="default", help="The Terraform workspace to initialise"
)
@click.option("--varfile", multiple=True, default=[], help="Path to .tfvars variables file")
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output diagram (default architecture.dot.png)",
)
@click.option("--format", default="png", help="File format (png/pdf/svg/bmp)")
@click.option("--show", is_flag=True, default=False, help="Show diagram after generation")
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

    show_banner()
    preflight_check()
    tfdata = compile_tfdata(source, varfile, workspace, debug, annotate)
    drawing.render_diagram(
        tfdata,
        show,
        simplified,
        outfile,
        format,
        source,
    )


# List Resources Command
@cli.command()
@click.option("--debug", is_flag=True, default=False, help="Dump exception tracebacks")
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL or folder)",
)
@click.option(
    "--workspace", multiple=False, default="default", help="The Terraform workspace to initialise"
)
@click.option("--varfile", multiple=True, default=[], help="Path to .tfvars variables file")
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

    show_banner()
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
    click.echo(f"\nCompleted!")

def main():
    cli(
        default_map={
            "draw": {"avl_classes": dir()},
            "graphlist": {"avl_classes": dir()},
        }
    )

if __name__ == "__main__":
    main()
