"""Terraform wrapper for executing terraform commands and parsing output.

Handles terraform init, plan, graph generation, and conversion of terraform
output into internal data structures for diagram generation.
"""

from typing import Dict, List, Tuple, Any
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
import modules.config_loader as config_loader
import modules.provider_detector as provider_detector

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


def tf_initplan(
    source: Tuple[str, ...], varfile: List[str], workspace: str, debug: bool = True
) -> Dict[str, Any]:
    """Initialize Terraform and generate plan and graph data.

    Args:
        source: Tuple of source locations (directories or Git URLs)
        varfile: List of variable files to use
        workspace: Terraform workspace name
        debug: Show subprocess output to console

    Returns:
        Dictionary containing terraform plan and graph data
    """
    debug = True
    tfdata = dict()
    tfdata["codepath"] = list()
    tfdata["workdir"] = os.getcwd()
    # Process each source location
    for sourceloc in source:
        # Handle local directory source
        if os.path.isdir(sourceloc):
            codepath = os.path.abspath(sourceloc)
            # Copy override file to force local backend (ignores TFE remote state)
            ovpath = os.path.join(basedir, "override.tf")
            override_dest = os.path.join(codepath, "override.tf")
            if not os.path.exists(override_dest):
                shutil.copy(ovpath, override_dest)
            os.chdir(codepath)
        # Handle Git repository source
        else:
            githubURL, subfolder, git_tag = gitlibs.get_clone_url(sourceloc)
            codepath = gitlibs.clone_files(sourceloc, temp_dir.name)
            # Copy override file to cloned directory
            ovpath = os.path.join(basedir, "override.tf")
            override_dest = os.path.join(codepath, "override.tf")
            if not os.path.exists(override_dest):
                shutil.copy(ovpath, override_dest)
            os.chdir(codepath)
            codepath = [codepath]
            # Verify files were cloned
            if len(os.listdir()) == 0:
                click.echo(
                    click.style(
                        f"\n  ERROR: No files found to process.",
                        fg="red",
                        bold=True,
                    )
                )
                exit()
        click.echo(click.style("\nCalling Terraform..", fg="white", bold=True))
        click.echo("  (Forcing local backend to generate full infrastructure plan)")
        # Initialize terraform with providers
        result = subprocess.run(
            ["terraform", "init", "--upgrade", "-reconfigure"],
            capture_output=not debug,
            text=True,
        )
        if result.returncode != 0:
            click.echo(
                click.style(
                    f"\nERROR: Cannot perform terraform init using provided source. Check providers and backend config.",
                    fg="red",
                    bold=True,
                )
            )
            if not debug and result.stderr:
                click.echo(click.style(f"Details: {result.stderr}", fg="red"))
            exit(result.returncode)
        # Resolve variable file path
        if varfile:
            vfile = varfile[0]
            if not os.path.isabs(vfile):
                vfile = os.path.join(start_dir, vfile)

        click.echo(
            click.style(
                f"\nInitalising workspace: {workspace}\n", fg="white", bold=True
            )
        )
        # Select or create terraform workspace
        result = subprocess.run(
            ["terraform", "workspace", "select", "-or-create=True", workspace],
            capture_output=not debug,
            text=True,
        )
        if result.returncode != 0:
            click.echo(
                click.style(
                    f"\nERROR: Invalid output from 'terraform workspace select {workspace}' command.",
                    fg="red",
                    bold=True,
                )
            )
            if not debug and result.stderr:
                click.echo(click.style(f"Details: {result.stderr}", fg="red"))
            exit(result.returncode)

        click.echo(
            click.style(f"\nGenerating Terraform Plan..\n", fg="white", bold=True)
        )
        # Setup temporary file paths and clean up old files
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
        # Generate terraform plan with or without varfile
        if varfile:
            result = subprocess.run(
                [
                    "terraform",
                    "plan",
                    "-refresh=false",
                    "-var-file",
                    vfile,
                    "-out",
                    tfplan_path,
                ],
                capture_output=not debug,
                text=True,
            )
        else:
            result = subprocess.run(
                ["terraform", "plan", "-refresh=false", "-out", tfplan_path],
                capture_output=not debug,
                text=True,
            )
        if result.returncode != 0:
            click.echo(
                click.style(
                    f"\nERROR: Invalid output from 'terraform plan' command. Try using the terraform CLI first to check source files have no errors.",
                    fg="red",
                    bold=True,
                )
            )
            if not debug and result.stderr:
                click.echo(click.style(f"Details: {result.stderr}", fg="red"))
            exit(result.returncode)

        click.echo(click.style(f"\nDecoding plan..\n", fg="white", bold=True))
        # Convert binary plan to JSON format
        if os.path.exists(tfplan_path):
            with open(tfplan_json_path, "w") as f:
                result = subprocess.run(
                    ["terraform", "show", "-json", tfplan_path],
                    stdout=f,
                    stderr=None if debug else subprocess.PIPE,
                    text=True,
                )
            if result.returncode == 0:
                click.echo(click.style(f"\nAnalysing plan..\n", fg="white", bold=True))
                # Load plan data
                with open(tfplan_json_path) as f:
                    plandata = json.load(f)
                # Generate terraform graph
                with open(tfgraph_path, "w") as f:
                    result = subprocess.run(
                        ["terraform", "graph"],
                        stdout=f,
                        stderr=None if debug else subprocess.PIPE,
                        text=True,
                    )
                # Remove override.tf after all terraform commands complete
                if os.path.exists(override_dest):
                    os.remove(override_dest)
                tfdata["plandata"] = dict(plandata)
                click.echo(
                    click.style(
                        f"\nConverting TF Graph Connections..  (this may take a while)\n",
                        fg="white",
                        bold=True,
                    )
                )
                # Convert DOT graph to JSON using Graphviz
                if os.path.exists(tfgraph_path):
                    result = subprocess.run(
                        ["dot", "-Txdot_json", "-o", tfgraph_json_path, tfgraph_path],
                        capture_output=not debug,
                        text=True,
                    )
                    if result.returncode != 0:
                        click.echo(
                            click.style(
                                f"\nERROR: Failed to convert graph with Graphviz.",
                                fg="red",
                                bold=True,
                            )
                        )
                        if not debug and result.stderr:
                            click.echo(
                                click.style(f"Details: {result.stderr}", fg="red")
                            )
                        exit(result.returncode)
                    with open(tfgraph_json_path) as f:
                        graphdata = json.load(f)
                else:
                    click.echo(
                        click.style(
                            f"\nERROR: Invalid output from 'terraform graph' command. Check your TF source files can generate a valid plan and graph",
                            fg="red",
                            bold=True,
                        )
                    )
                    exit(1)
            else:
                click.echo(
                    click.style(
                        f"\nERROR: Invalid output from 'terraform show' command.",
                        fg="red",
                        bold=True,
                    )
                )
                if not debug and result.stderr:
                    click.echo(click.style(f"Details: {result.stderr}", fg="red"))
                exit(result.returncode)
        else:
            click.echo(
                click.style(
                    f"\nERROR: Terraform plan file not found at {tfplan_path}",
                    fg="red",
                    bold=True,
                )
            )
            exit(1)
        tfdata = make_tf_data(tfdata, plandata, graphdata, codepath)
    os.chdir(start_dir)
    return tfdata


def make_tf_data(
    tfdata: Dict[str, Any],
    plandata: Dict[str, Any],
    graphdata: Dict[str, Any],
    codepath: str,
) -> Dict[str, Any]:
    """Combine terraform plan and graph data into tfdata structure.

    Args:
        tfdata: Terraform data dictionary
        plandata: Parsed terraform plan JSON
        graphdata: Parsed terraform graph JSON
        codepath: Path to terraform source code

    Returns:
        Updated tfdata with plan and graph information
    """
    tfdata["codepath"] = codepath
    # Extract resource changes from plan
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


def setup_tfdata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize tfdata data structures from terraform plan.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with initialized graph structures
    """
    # Detect cloud provider from tf_resources_created (early detection before all_resource exists)
    detected_provider = None
    if "tf_resources_created" in tfdata:
        resource_addresses = [
            obj["address"]
            for obj in tfdata["tf_resources_created"]
            if obj.get("mode") == "managed"
        ]
        provider_counts = {}
        for resource_addr in resource_addresses:
            provider = provider_detector.get_provider_for_resource(resource_addr)
            if provider in provider_detector.SUPPORTED_PROVIDERS:
                provider_counts[provider] = provider_counts.get(provider, 0) + 1

        if provider_counts:
            detected_provider = max(provider_counts, key=provider_counts.get)

    if not detected_provider:
        # Cannot detect provider at this stage - this is fatal
        raise provider_detector.ProviderDetectionError(
            "Could not detect cloud provider from Terraform plan. "
            "Ensure your Terraform code contains cloud resources (aws_, azurerm_, google_, etc.)"
        )

    cloud_config = config_loader.load_config(detected_provider)
    HIDDEN_NODES = getattr(cloud_config, f"{detected_provider.upper()}_HIDE_NODES", [])
    # Initialize graph data structures
    tfdata["graphdict"] = dict()
    tfdata["meta_data"] = dict()
    tfdata["all_output"] = dict()
    tfdata["node_list"] = list()
    tfdata["hidden"] = HIDDEN_NODES
    tfdata["annotations"] = dict()
    # Create nodes from resources in plan
    for object in tfdata["tf_resources_created"]:
        # Only process managed resources (not data sources)
        if object["mode"] == "managed":
            node = str(object["address"])
            # Handle count/for_each indexed resources
            if "index" in object.keys():
                # String index uses brackets, numeric uses tilde
                if not isinstance(object["index"], int):
                    suffix = "[" + object["index"] + "]"
                else:
                    suffix = "~" + str(int(object.get("index")) + 1)
                node = node + suffix
            # Initialize node with empty connections
            tfdata["graphdict"][node] = list()
            tfdata["node_list"].append(node)
            # Collect resource metadata from plan
            details = object["change"]["after"]
            if details is not None:
                details.update(object["change"]["after_unknown"])
                details.update(object["change"]["after_sensitive"])
                # Add module name if resource is in a module
                if "module." in object["address"]:
                    modname = (
                        object["module_address"].split("module.")[-1].split(".")[0]
                    )
                    details["module"] = modname
                else:
                    details["module"] = "main"
                tfdata["meta_data"][node] = details
    # Remove duplicates from node list
    tfdata["node_list"] = list(dict.fromkeys(tfdata["node_list"]))
    return tfdata


def find_node_in_gvid_table(node: str, gvid_table: List[str]) -> int:
    """Find node ID in gvid_table by trying name variations.

    Args:
        node: Resource node name to find
        gvid_table: List of node names from terraform graph

    Returns:
        Index of node in gvid_table
    """
    # Try exact match first
    if node in gvid_table:
        return gvid_table.index(node)

    # Try without brackets and numbers
    nodename = helpers.remove_brackets_and_numbers(node)
    if nodename in gvid_table:
        return gvid_table.index(nodename)

    # Try base name without index suffix
    nodename = node.split("[")[0].split("~")[0]
    if nodename in gvid_table:
        return gvid_table.index(nodename)

    # Try without module prefix
    nodename = helpers.get_no_module_no_number_name(node)
    if nodename in gvid_table:
        return gvid_table.index(nodename)

    # No match found
    click.echo(
        click.style(
            f"\nERROR: Cannot map node {node} to graph connections. Exiting.",
            fg="red",
            bold=True,
        )
    )
    exit()


def tf_makegraph(tfdata: Dict[str, Any], debug: bool) -> Dict[str, Any]:
    """Build resource dependency graph from terraform graph output.

    Args:
        tfdata: Terraform data dictionary with plan and graph data

    Returns:
        Updated tfdata with populated graphdict connections
    """
    # Detect cloud provider from tf_resources_created (early detection before all_resource exists)
    # At this stage, all_resource hasn't been populated yet, so we detect from terraform plan resources
    detected_provider = None
    if "tf_resources_created" in tfdata:
        resource_addresses = [
            obj["address"]
            for obj in tfdata["tf_resources_created"]
            if obj.get("mode") == "managed"
        ]
        provider_counts = {}
        for resource_addr in resource_addresses:
            provider = provider_detector.get_provider_for_resource(resource_addr)
            if provider in provider_detector.SUPPORTED_PROVIDERS:
                provider_counts[provider] = provider_counts.get(provider, 0) + 1

        if provider_counts:
            detected_provider = max(provider_counts, key=provider_counts.get)

    if not detected_provider:
        # Cannot detect provider at this stage - this is fatal
        raise provider_detector.ProviderDetectionError(
            "Could not detect cloud provider from Terraform plan. "
            "Ensure your Terraform code contains cloud resources (aws_, azurerm_, google_, etc.)"
        )

    cloud_config = config_loader.load_config(detected_provider)
    REVERSE_ARROW_LIST = getattr(
        cloud_config, f"{detected_provider.upper()}_REVERSE_ARROW_LIST", []
    )

    # Initialize graph structures
    tfdata = setup_tfdata(tfdata)
    # Build lookup table mapping graph IDs to resource names
    gvid_table = list()
    # Build gvid lookup table from graph objects
    for item in tfdata["tfgraph"]["objects"]:
        gvid = item["_gvid"]
        gvid_table.append("")
        # Use name for modules, label for resources
        if item.get("name").startswith("module."):
            gvid_table[gvid] = str(item.get("name"))
        else:
            gvid_table[gvid] = str(item.get("label"))
    # Process graph edges to build connections
    for node in dict(tfdata["graphdict"]):
        # Find node ID in graph
        node_id = find_node_in_gvid_table(node, gvid_table)
        if tfdata["tfgraph"].get("edges"):
            for connection in tfdata["tfgraph"]["edges"]:
                head = connection["head"]
                tail = connection["tail"]
                # Check if this edge connects to our node
                if (
                    node_id == head
                    and len([k for k in tfdata["graphdict"] if gvid_table[tail] in k])
                    > 0
                ):
                    conn = gvid_table[tail]
                    conn_type = gvid_table[tail].split(".")[0]
                    # Find actual numbered nodes if connection is generic
                    matched_connections = [
                        k for k in tfdata["graphdict"] if k.startswith(gvid_table[tail])
                    ]
                    matched_nodes = [
                        k for k in tfdata["graphdict"] if k.startswith(gvid_table[head])
                    ]
                    # Use matched node if only one exists
                    if node not in tfdata["graphdict"] and len(matched_nodes) == 1:
                        node = matched_nodes[0]
                    if (
                        conn not in tfdata["graphdict"]
                        and len(matched_connections) == 1
                    ):
                        conn = matched_connections[0]
                    # Handle reverse arrow resources (connection points to node)
                    if conn_type in REVERSE_ARROW_LIST:
                        if conn not in tfdata["graphdict"].keys():
                            tfdata["graphdict"][conn] = list()
                        # Skip multi-instance resources
                        if "[" not in conn:
                            tfdata["graphdict"][conn].append(node)
                    # Normal arrow (node points to connection)
                    else:
                        if "[" not in node:
                            tfdata["graphdict"][node].append(conn)
    # Add VPC-subnet relationships based on CIDR overlap
    tfdata = add_vpc_implied_relations(tfdata)
    # Save original graph and metadata for reference
    tfdata["original_graphdict"] = copy.deepcopy(tfdata["graphdict"])
    tfdata["original_metadata"] = copy.deepcopy(tfdata["meta_data"])
    # Verify cloud resources exist (check all supported provider prefixes)
    from modules.provider_detector import PROVIDER_PREFIXES

    has_cloud_resources = any(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], prefix)
        for prefix in PROVIDER_PREFIXES.keys()
    )
    if not has_cloud_resources:
        click.echo(
            click.style(
                f"\nERROR: No AWS, Azure or Google resources will be created with current plan. Exiting.",
                fg="red",
                bold=True,
            )
        )
        exit()
    return tfdata


def add_vpc_implied_relations(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Add VPC to subnet relationships based on CIDR overlap.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VPC-subnet connections
    """
    # Find all VPC and subnet resources
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
    # Link subnets to VPCs based on CIDR overlap
    if len(vpc_resources) > 0 and len(subnet_resources) > 0:
        for vpc in vpc_resources:
            vpc_cidr = ipaddr.IPNetwork(tfdata["meta_data"][vpc]["cidr_block"])
            for subnet in subnet_resources:
                subnet_cidr = ipaddr.IPNetwork(
                    tfdata["meta_data"][subnet]["cidr_block"]
                )
                # Add subnet to VPC if CIDR ranges overlap and not already present
                if (
                    subnet_cidr.overlaps(vpc_cidr)
                    and subnet not in tfdata["graphdict"][vpc]
                ):
                    tfdata["graphdict"][vpc].append(subnet)
    return tfdata
