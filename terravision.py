#!/usr/bin/env python
import click
import sys
import json
import shutil
import os
import modules.fileparser as fileparser
import modules.interpreter as interpreter
import modules.helpers as helpers
import modules.drawing as drawing
from pprint import pprint
from pathlib import Path

# Process source files and return dictionaries with relevant data
def make_graph_dict(
    nodelist: list,
    all_resources: dict,
    all_locals: dict,
    all_outputs: dict,
    hidden: list,
):
    # Find and replace all local variables with resource references in their values
    find_replace = dict()
    for local_list in helpers.dict_generator(all_locals):
        for local_item in local_list:
            for nodecheck in nodelist:
                if type(local_item) == str:
                    if nodecheck in local_item:
                        print(f"    local.{local_list[1]} = {nodecheck}")
                        find_replace["local." + local_list[1]] = nodecheck
    # Start with a empty connections list for all nodes/resources we know about
    graphdict = dict.fromkeys(nodelist, [])
    num_resources = len(nodelist)
    click.echo(
        click.style(
            f"\nComputing Relations between {num_resources - len(hidden)} out of {num_resources} resources...",
            fg="white",
            bold=True,
        )
    )
    # Determine relationship between resources and append to graphdict when found
    for param_list in helpers.dict_generator(all_resources):
        for listitem in param_list:
            if isinstance(listitem, str):
                lisitem_tocheck = listitem
                # If resource refers to an output from another module, get the value from outputs dict
                if "module." in listitem:
                    cleantext = helpers.fix_lists(listitem)
                    splitlist = cleantext.split(".")
                    outputname = helpers.find_between(
                        cleantext, splitlist[1] + ".", " "
                    )
                    for file in all_outputs.keys():
                        for i in all_outputs[file]:
                            if outputname in i.keys():
                                outvalue = i[outputname]["value"]
                                lisitem_tocheck = outvalue
                matching_result = helpers.check_relationship(
                    lisitem_tocheck, param_list, nodelist, find_replace, hidden
                )
                if matching_result:
                    for i in range(0, len(matching_result), 2):
                        a_list = list(graphdict[matching_result[i]])
                        if not matching_result[i + 1] in a_list:
                            a_list.append(matching_result[i + 1])
                        graphdict[matching_result[i]] = a_list
            if isinstance(listitem, list):
                for i in listitem:
                    matching_result = helpers.check_relationship(
                        i, param_list, nodelist, find_replace, hidden
                    )
                    if matching_result:
                        a_list = list(graphdict[matching_result[0]])
                        if not matching_result[1] in a_list:
                            a_list.append(matching_result[1])
                        graphdict[matching_result[0]] = a_list
    return graphdict


def compile_tfdata(source: list, varfile: list, annotate=""):
    # Parse HCL files from Terraform
    tfdata = fileparser.parse_tf_files(source, varfile, annotate)
    # Load default variable values and user variable values
    tfdata = interpreter.get_variable_values(tfdata)
    # Create view of locals by module
    tfdata = interpreter.extract_locals(tfdata)
    # Create metadata view from nested TF file resource attributes
    tfdata = interpreter.get_metadata(tfdata)
    # Replace metadata (resource attributes) variables and locals with actual values
    tfdata = interpreter.handle_metadata_vars(tfdata)
    # Inject parent module variables that are referenced downstream in sub modules
    tfdata = interpreter.inject_module_variables(tfdata)
    # Handle conditionally created resources e.g. with count or foreach attribute
    tfdata = interpreter.handle_conditional_resources(tfdata)
    # Dump out findings after file scans are complete
    helpers.output_log(tfdata, tfdata["variable_map"])

    # Create Graph Data Structure in the format {node: [connected_node1,connected_node2]}
    relationship_dict = make_graph_dict(
        tfdata["node_list"],
        tfdata["all_resource"],
        tfdata.get("all_locals"),
        tfdata.get("all_output"),
        tfdata["hidden"],
    )
    # temp_dir.cleanup()
    # os.chdir(cwd)
    return {"graphdict": relationship_dict, "tfdata": tfdata}


def preflight_check():
    click.echo(click.style("\nPreflight check..", fg="white", bold=True))
    dependencies = ["dot", "gvpr", "git"]
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


def unique_services(nodelist: list) -> list:
    service_list = []
    for item in nodelist:
        service = str(item.split(".")[0]).strip()
        service_list.append(service)
    return sorted(set(service_list))


# Default help banner


@click.version_option(version=0.2, prog_name="terravision")
@click.group()
def cli():
    """
    Terravision 0.2 Alpha

    Copyright 2022 Patrick Chugh. All rights reserved.

    Terravision generates professional cloud architecture diagrams from Terraform scripts

    For help with a specific command type:

    terravision [COMMAND] --help

    """
    pass


# Draw Diagram Command
@cli.command()
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL or folder)",
)
@click.option(
    "--varfile", multiple=True, default=[], help="Path to .tfvars variables file"
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output diagram (default architecture.dot.png)",
)
@click.option("--format", default="png", help="File format (png/pdf/svg/json/bmp)")
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
def draw(source, varfile, outfile, format, show, simplified, annotate, avl_classes):
    """Draws Architecture Diagram"""
    preflight_check()
    parsed_data = compile_tfdata(source, varfile, annotate)
    drawing.render_diagram(
        parsed_data["tfdata"],
        parsed_data["graphdict"],
        show,
        simplified,
        outfile,
        format,
        source,
    )


# List Resources Command
@cli.command()
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL or folder)",
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
@click.option("--avl_classes", hidden=True)
def list(source, varfile, show_services, outfile, avl_classes):
    """List Cloud Resources and Relations"""
    preflight_check()
    parsed_data = make_graph(source, varfile)
    click.echo(click.style("\nJSON Dictionary :", fg="white", bold=True))
    unique = unique_services(parsed_data["tfdata"]["node_list"])
    click.echo(
        json.dumps(
            parsed_data["graphdict"] if not show_services else unique,
            indent=4,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    cli(default_map={"draw": {"avl_classes": dir()}, "list": {"avl_classes": dir()}})
