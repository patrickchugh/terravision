import os
import sys
from pathlib import Path
import click
import modules.gitlibs as gitlibs
import modules.helpers as helpers
import tempfile
import shutil
import json
import ipaddr
import modules.cloud_config as cloud_config

# Create Tempdir and Module Cache Directories
annotations = dict()
start_dir = Path.cwd()
temp_dir = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
MODULE_DIR = str(Path(Path.home(), ".terravision", "module_cache"))
REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST


def tf_initplan(source: tuple, varfile: list):
    for sourceloc in source:
        if os.path.isdir(sourceloc):
            os.chdir(sourceloc)
        else:
            githubURL, subfolder, git_tag = gitlibs.get_clone_url(sourceloc)
            codepath = gitlibs.clone_files(sourceloc, temp_dir.name)
            shutil.copy("override.tf", codepath)
            os.chdir(codepath)
        returncode = os.system(f"terraform init")
        if returncode > 0:
            click.echo("ERROR running terraform init command")
            exit()
        vfile = varfile[0]
        click.echo(
            click.style(f"\nGenerating Terraform Plan..\n", fg="white", bold=True)
        )
        returncode = os.system(f"terraform plan -var-file {vfile} -out tfplan.bin")
        click.echo(click.style(f"\nAnalysing Plan..\n", fg="white", bold=True))
        if (
            os.path.exists("tfplan.bin")
            and os.system(f"terraform show -json tfplan.bin > tfplan.json") == 0
        ):
            f = open("tfplan.json")
            plandata = json.load(f)
            returncode = os.system(f"terraform graph > tfgraph.dot")
            if os.path.exists("tfgraph.dot"):
                returncode = os.system(f"dot -Txdot_json -o tfgraph.json tfgraph.dot")
                f = open("tfgraph.json")
                graphdata = json.load(f)
            else:
                click.echo(
                    click.style(
                        f"\n  ERROR: Invalud output from 'terraform graph' command. Check your TF source files can generate a valid plan and graph",
                        fg="red",
                        bold=True,
                    )
                )
                exit()
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: Invalud output from 'terraform plan' command. Try using the terraform CLI first to check source files have no errors.",
                    fg="red",
                    bold=True,
                )
            )
            exit()
    os.chdir(start_dir)
    return make_tf_data(plandata, graphdata)


def make_tf_data(plandata: dict, graphdata: dict):
    tfdata = dict()
    tfdata["workdir"] = os.getcwd()
    tfdata["tf_resources_created"] = plandata["resource_changes"]
    tfdata["tfgraph"] = graphdata
    return tfdata


def setup_graph(tfdata: dict):
    tfdata["graphdict"] = dict()
    tfdata["meta_data"] = dict()
    tfdata["node_list"] = list()
    tfdata["hidden"] = dict()
    tfdata["annotations"] = dict()
    # Make an initial dict with resources created and empty connections
    for object in tfdata["tf_resources_created"]:
        # Replace multi count notation
        node = object["address"].replace("[", "-")
        node = node.replace("]", "")
        if "-" in node:
            number = node.split("-")[1]
            number = str(int(number) + 1)
            node = node.split("-")[0] + "-" + number
        no_module_name = helpers.get_no_module_name(node)
        tfdata["graphdict"][no_module_name] = list()
        tfdata["node_list"].append(no_module_name)
        # Add metadata
        details = object["change"]["after"]
        details.update(object["change"]["after_unknown"])
        details.update(object["change"]["after_sensitive"])
        if "module." in object["address"]:
            modname = object["address"].split(".")[1]
            details["module"] = modname
        if "-" in node:
            details["count"] = 3
        tfdata["meta_data"][no_module_name] = details
    tfdata["node_list"] = list(dict.fromkeys(tfdata["node_list"]))
    return tfdata


def tf_makegraph(tfdata: dict):
    # Setup Initial graphdict
    tfdata = setup_graph(tfdata)
    # Make a lookup table of gvids mapping resources to ids
    gvid_table = list()
    for item in tfdata["tfgraph"]["objects"]:
        gvid = item["_gvid"]
        gvid_table.append("")
        gvid_table[gvid] = helpers.get_no_module_name(item.get("label"))
    # Populate connections list for each node in graphdict
    for node in dict(tfdata["graphdict"]):
        node_id = gvid_table.index(node.split("-")[0])
        for connection in tfdata["tfgraph"]["edges"]:
            head = connection["head"]
            tail = connection["tail"]
            # Check that the connection is part of the nodes that will be created (exists in graphdict)
            if (
                node_id == head
                and len(
                    [k for k in tfdata["graphdict"] if k.startswith(gvid_table[tail])]
                )
                > 0
            ):
                conn = gvid_table[tail]
                conn_type = gvid_table[tail].split(".")[0]
                if conn_type in REVERSE_ARROW_LIST:
                    if not conn in tfdata["graphdict"].keys():
                        tfdata["graphdict"][conn] = list()
                    tfdata["graphdict"][conn].append(node)
                else:
                    tfdata["graphdict"][node].append(conn)
    tfdata = add_vpc_implied_relations(tfdata)
    tfdata["original_graphdict"] = dict(tfdata["graphdict"])
    tfdata["original_metadata"] = dict(tfdata["meta_data"])
    return tfdata


def add_vpc_implied_relations(tfdata: dict):
    # Handle VPC / Subnet relationships
    vpc_resources = [
        k for k, v in tfdata["graphdict"].items() if k.startswith("aws_vpc")
    ]
    subnet_resources = [
        k for k, v in tfdata["graphdict"].items() if k.startswith("aws_subnet")
    ]
    for vpc in vpc_resources:
        vpc_cidr = ipaddr.IPNetwork(tfdata["meta_data"][vpc]["cidr_block"])
        for subnet in subnet_resources:
            subnet_cidr = ipaddr.IPNetwork(tfdata["meta_data"][subnet]["cidr_block"])
            if subnet_cidr.overlaps(vpc_cidr):
                tfdata["graphdict"][vpc].append(subnet)
    return tfdata
