import os
import copy
from pathlib import Path
import subprocess
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
# basedir =  os.path.dirname(os.path.isfile("terravision"))
basedir = Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
start_dir = Path.cwd()
temp_dir = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
os.environ["TF_DATA_DIR"] = temp_dir.name
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
MODULE_DIR = str(Path(Path.home(), ".terravision", "module_cache"))
REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST


def tf_initplan(source: tuple, varfile: list, workspace: str):
    tfdata = dict()
    tfdata["codepath"] = list()
    tfdata["workdir"] = os.getcwd()
    for sourceloc in source:
        if os.path.isdir(sourceloc):
            os.chdir(sourceloc)
            codepath = sourceloc
        else:
            githubURL, subfolder, git_tag = gitlibs.get_clone_url(sourceloc)
            codepath = gitlibs.clone_files(sourceloc, temp_dir.name)
            ovpath = os.path.join(basedir, "override.tf")
            shutil.copy(ovpath, codepath)
            os.chdir(codepath)
            codepath = [codepath]
            if len(os.listdir()) == 0:
                click.echo(
                    click.style(
                        f"\n  ERROR: No files found to process.",
                        fg="red",
                        bold=True,
                    )
                )
                exit()
        returncode = os.system(f"terraform init --upgrade -reconfigure")
        if returncode > 0:
            click.echo(
                click.style(
                    f"\nERROR: Cannot perform terraform init using provided source. Check providers and backend config.",
                    fg="red",
                    bold=True,
                )
            )
            exit()
        if varfile:
            vfile = varfile[0]
            if not os.path.isabs(vfile):
                vfile = os.path.join(start_dir, vfile)

        click.echo(
            click.style(
                f"\nInitalising workspace: {workspace}\n", fg="white", bold=True
            )
        )
        # init workspace
        returncode = os.system(
            f"terraform workspace select -or-create=True {workspace}"
        )
        if returncode:
            click.echo(
                click.style(
                    f"\nERROR: Invalid output from 'terraform workspace select {workspace}' command.",
                    fg="red",
                    bold=True,
                )
            )
            exit()

        click.echo(
            click.style(f"\nGenerating Terraform Plan..\n", fg="white", bold=True)
        )
        # Get Temporary directory paths for intermediary files
        tempdir = os.path.dirname(temp_dir.name)
        tfplan_path = os.path.join(tempdir, "tfplan.bin")
        if os.path.exists(tfplan_path):
            os.remove(tfplan_path)
        tfplan_json_path = os.path.join(tempdir, "tfplan.json")
        if os.path.exists(tfplan_json_path):
            os.remove(tfplan_json_path)
        tfgraph_path = os.path.join(tempdir, "tfgraph.dot")
        if os.path.exists(tfgraph_path):
            os.remove(tfgraph_path)
        tfgraph_json_path = os.path.join(tempdir, "tfgraph.json")
        if os.path.exists(tfgraph_json_path):
            os.remove(tfgraph_json_path)
        if varfile:
            returncode = os.system(
                f"terraform plan -refresh=false -var-file {vfile} -out {tfplan_path}"
            )
        else:
            returncode = os.system(f"terraform plan -refresh=false -out {tfplan_path}")
        click.echo(click.style(f"\nDecoding plan..\n", fg="white", bold=True))
        if (
            os.path.exists(tfplan_path)
            and os.system(f"terraform show -json {tfplan_path} > {tfplan_json_path}")
            == 0
        ):
            click.echo(click.style(f"\nAnalysing plan..\n", fg="white", bold=True))
            f = open(tfplan_json_path)
            plandata = json.load(f)
            returncode = os.system(f"terraform graph > {tfgraph_path}")
            tfdata["plandata"] = dict(plandata)
            click.echo(
                click.style(
                    f"\nConverting TF Graph Connections..  (this may take a while)\n",
                    fg="white",
                    bold=True,
                )
            )
            if os.path.exists(tfgraph_path):
                returncode = os.system(
                    f"dot -Txdot_json -o {tfgraph_json_path} {tfgraph_path}"
                )
                f = open(tfgraph_json_path)
                graphdata = json.load(f)
            else:
                click.echo(
                    click.style(
                        f"\nERROR: Invalid output from 'terraform graph' command. Check your TF source files can generate a valid plan and graph",
                        fg="red",
                        bold=True,
                    )
                )
                exit()
        else:
            click.echo(
                click.style(
                    f"\nERROR: Invalid output from 'terraform plan' command. Try using the terraform CLI first to check source files have no errors.",
                    fg="red",
                    bold=True,
                )
            )
            exit()
        tfdata = make_tf_data(tfdata, plandata, graphdata, codepath)
    os.chdir(start_dir)
    return tfdata


def make_tf_data(tfdata: dict, plandata: dict, graphdata: dict, codepath: str) -> dict:
    tfdata["codepath"] = codepath
    if plandata.get("resource_changes"):
        tfdata["tf_resources_created"] = plandata["resource_changes"]
    else:
        click.echo(
            click.style(
                f"\nERROR: Invalid output from 'terraform plan' command. Try using the terraform CLI first to check source actually generates resources and has no errors.",
                fg="red",
                bold=True,
            )
        )
        exit()
    tfdata["tfgraph"] = graphdata
    return tfdata


def setup_graph(tfdata: dict):
    tfdata["graphdict"] = dict()
    tfdata["meta_data"] = dict()
    tfdata["all_output"] = dict()
    tfdata["node_list"] = list()
    tfdata["hidden"] = dict()
    tfdata["annotations"] = dict()
    # Make an initial dict with resources created and empty connections
    for object in tfdata["tf_resources_created"]:
        if object["mode"] == "managed":
            # Replace multi count notation
            # node = helpers.get_no_module_name(object["address"])
            node = str(object["address"])
            if "index" in object.keys():
                # node = object["type"] + "." + object["name"]
                if not isinstance(object["index"], int):
                    suffix = "[" + object["index"] + "]"
                else:
                    suffix = "~" + str(int(object.get("index")) + 1)
                node = node + suffix
            tfdata["graphdict"][node] = list()
            tfdata["node_list"].append(node)
            # Add metadata
            details = object["change"]["after"]
            details.update(object["change"]["after_unknown"])
            details.update(object["change"]["after_sensitive"])
            if "module." in object["address"]:
                modname = object["module_address"].split("module.")[1]
                details["module"] = modname
            tfdata["meta_data"][node] = details
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
        gvid_table[gvid] = str(item.get("label"))
    # Populate connections list for each node in graphdict
    for node in dict(tfdata["graphdict"]):
        if "module." in node:
            nodename = helpers.get_no_module_no_number_name(node)
        else:
            nodename = node.split("[")[0]
            nodename = nodename.split("~")[0]
        if nodename in gvid_table:
            node_id = gvid_table.index(nodename)
        else:
            nodename = helpers.remove_brackets_and_numbers(nodename)
            node_id = gvid_table.index(nodename)
        if tfdata["tfgraph"].get("edges"):
            for connection in tfdata["tfgraph"]["edges"]:
                head = connection["head"]
                tail = connection["tail"]
                # Check that the connection is part of the nodes that will be created (exists in graphdict)
                if (
                    node_id == head
                    and len(
                        [
                            k
                            for k in tfdata["graphdict"]
                            if k.startswith(gvid_table[tail])
                        ]
                    )
                    > 0
                ):
                    conn = gvid_table[tail]
                    conn_type = gvid_table[tail].split(".")[0]
                    # Find out the actual nodes with ~ suffix where link is not specific to a numbered node
                    matched_connections = [
                        k for k in tfdata["graphdict"] if k.startswith(gvid_table[tail])
                    ]
                    matched_nodes = [
                        k for k in tfdata["graphdict"] if k.startswith(gvid_table[head])
                    ]
                    if not node in tfdata["graphdict"] and len(matched_nodes) == 1:
                        node = matched_nodes[0]
                    if (
                        not conn in tfdata["graphdict"]
                        and len(matched_connections) == 1
                    ):
                        conn = matched_connections[0]
                    if conn_type in REVERSE_ARROW_LIST:
                        if not conn in tfdata["graphdict"].keys():
                            tfdata["graphdict"][conn] = list()
                        tfdata["graphdict"][conn].append(node)
                    else:
                        tfdata["graphdict"][node].append(conn)
    tfdata = add_vpc_implied_relations(tfdata)
    tfdata["original_graphdict"] = copy.deepcopy(tfdata["graphdict"])
    tfdata["original_metadata"] = copy.deepcopy(tfdata["meta_data"])
    # TODO: Add a helper function to detect _aws, azurerm and google provider prefixes on resource names
    if len(helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_")) == 0:
        click.echo(
            click.style(
                f"\nERROR: No AWS, Azure or Google resources will be created with current plan. Exiting.",
                fg="red",
                bold=True,
            )
        )
        exit()
    return tfdata


# Handle VPC / Subnet relationships
def add_vpc_implied_relations(tfdata: dict):
    vpc_resources = [
        k
        for k, v in tfdata["graphdict"].items()
        if helpers.get_no_module_name(k).startswith("aws_vpc.")
    ]
    subnet_resources = [
        k
        for k, v in tfdata["graphdict"].items()
        if helpers.get_no_module_name(k).startswith("aws_subnet.")
    ]
    if len(vpc_resources) > 0 and len(subnet_resources) > 0:
        for vpc in vpc_resources:
            vpc_cidr = ipaddr.IPNetwork(tfdata["meta_data"][vpc]["cidr_block"])
            for subnet in subnet_resources:
                subnet_cidr = ipaddr.IPNetwork(
                    tfdata["meta_data"][subnet]["cidr_block"]
                )
                if subnet_cidr.overlaps(vpc_cidr):
                    tfdata["graphdict"][vpc].append(subnet)
    return tfdata
