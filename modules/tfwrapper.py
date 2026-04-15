"""Terraform wrapper for executing terraform commands and parsing output.

Handles terraform init, plan, graph generation, and conversion of terraform
output into internal data structures for diagram generation.
"""

from typing import Dict, List, Tuple, Any
import os
import re
import copy
import shutil
from pathlib import Path
import subprocess
import click
import modules.gitlibs as gitlibs
import modules.helpers as helpers
import modules.fileparser as fileparser
import modules.validators as validators
import tempfile
import json
import ipaddr
import modules.config_loader as config_loader
import modules.provider_detector as provider_detector

START_DIR = Path.cwd()
temp_dir = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
os.environ["TF_DATA_DIR"] = temp_dir.name
MODULE_DIR = str(Path(Path.home(), ".terravision", "module_cache"))


def _write_override(codepath):
    """Write terravision_override.tf to force local backend."""
    content = 'terraform {\n  backend "local" {\n\n  }\n}\n'
    dest = os.path.join(codepath, "terravision_override.tf")
    with open(dest, "w") as f:
        f.write(content)
    return dest


def _strip_cloud_block(content: str) -> str:
    """Remove any `cloud { ... }` block (brace-balanced) from a .tf file body.

    Terraform Cloud integration uses a `cloud` block inside `terraform { ... }`
    that is mutually exclusive with a `backend` block. The local-backend
    override file alone cannot disable it, so we physically strip the block
    from the source file (backed up and restored afterwards).
    """
    result = []
    i = 0
    n = len(content)
    pattern = re.compile(r"\bcloud\s*\{")
    while i < n:
        m = pattern.search(content, i)
        if not m:
            result.append(content[i:])
            break
        result.append(content[i : m.start()])
        depth = 0
        j = m.end() - 1  # position at '{'
        while j < n:
            ch = content[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        i = j
    return "".join(result)


def _neutralize_cloud_blocks(codepath: str) -> List[Tuple[str, str]]:
    """Back up and strip `cloud {}` blocks from .tf files under *codepath*.

    Returns a list of (backup_path, original_path) tuples for later restore.
    Skips the .terraform cache directory. Non-recursive into modules —
    Terraform Cloud configuration only lives in the root module.
    """
    backups: List[Tuple[str, str]] = []
    try:
        entries = os.listdir(codepath)
    except OSError:
        return backups
    for name in entries:
        if not name.endswith(".tf"):
            continue
        path = os.path.join(codepath, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r") as fh:
                original = fh.read()
        except OSError:
            continue
        if not re.search(r"\bcloud\s*\{", original):
            continue
        stripped = _strip_cloud_block(original)
        if stripped == original:
            continue
        backup = path + ".terravision.bak"
        shutil.copy2(path, backup)
        with open(path, "w") as fh:
            fh.write(stripped)
        backups.append((backup, path))
    return backups


def _restore_cloud_backups(backups: List[Tuple[str, str]]) -> None:
    """Restore files backed up by _neutralize_cloud_blocks."""
    for backup, original in backups:
        if os.path.exists(backup):
            shutil.move(backup, original)


def convert_dot_to_json(dot_file: str) -> dict:
    """Convert a Graphviz DOT file to a JSON dictionary.

    Uses the `dot` command-line tool to convert a DOT format graph file
    into xdot JSON format, then parses and returns the result.

    Args:
        dot_file: Path to the input DOT file.

    Returns:
        Parsed JSON dictionary of the graph data.
    """
    json_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    try:
        result = subprocess.run(
            ["dot", "-Txdot_json", "-o", json_file, dot_file],
            capture_output=True,
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
            if result.stderr:
                click.echo(click.style(f"Details: {result.stderr}", fg="red"))
            exit(result.returncode)
        with open(json_file) as f:
            graphdata = json.load(f)
        return graphdata
    finally:
        if os.path.exists(json_file):
            os.remove(json_file)


def _cleanup_override(override_dest):
    """Remove override.tf if it exists."""
    if override_dest and os.path.exists(override_dest):
        os.remove(override_dest)


def _tf_error(message, debug=True, result=None):
    """Print a terraform error message and exit."""
    click.echo(click.style(f"\nERROR: {message}", fg="red", bold=True))
    if not debug and result and result.stderr:
        click.echo(click.style(f"Details: {result.stderr}", fg="red"))
    exit(result.returncode if result and result.returncode else 1)


def _prepare_source(source):
    """Resolve source to a local codepath, write override.tf, and neutralize
    any Terraform Cloud `cloud {}` block so `terraform init` runs offline.

    Returns:
        Tuple of (codepath, override_dest, cloud_backups)
    """
    if os.path.isdir(source):
        codepath = os.path.abspath(source)
        override_dest = _write_override(codepath)
        cloud_backups = _neutralize_cloud_blocks(codepath)
        os.chdir(codepath)
    else:
        githubURL, subfolder, git_tag = gitlibs.get_clone_url(source)
        codepath = gitlibs.clone_files(source, temp_dir.name)
        override_dest = _write_override(codepath)
        cloud_backups = _neutralize_cloud_blocks(codepath)
        os.chdir(codepath)
        codepath = [codepath]
        if len(os.listdir()) == 0:
            _tf_error("No files found to process.")
    if cloud_backups:
        click.echo(
            click.style(
                "  Detected Terraform Cloud block; neutralized for local plan",
                fg="yellow",
            )
        )
    return codepath, override_dest, cloud_backups


def _run_terraform_init(debug, upgrade, skip_reconfigure: bool = False):
    """Run terraform init with optional -reconfigure and -upgrade.

    -reconfigure is only valid for state backends; Terraform Cloud rejects it,
    so callers that have stripped a cloud block must pass skip_reconfigure=True.
    """
    click.echo(click.style("\nCalling Terraform..", fg="white", bold=True))
    click.echo("  Forcing temporary local backend to generate full infrastructure plan")
    init_cmd = ["terraform", "init"]
    if not skip_reconfigure:
        init_cmd.append("-reconfigure")
    if upgrade:
        init_cmd.append("-upgrade")
    result = subprocess.run(init_cmd, capture_output=not debug, text=True)
    if result.returncode != 0:
        _tf_error(
            "Cannot perform terraform init using provided source. "
            "Check providers and backend config.",
            debug,
            result,
        )


def _select_workspace(workspace, debug):
    """Select or create terraform workspace."""
    click.echo(
        click.style(f"\nInitalising workspace: {workspace}\n", fg="white", bold=True)
    )
    result = subprocess.run(
        ["terraform", "workspace", "select", "-or-create=True", workspace],
        capture_output=not debug,
        text=True,
    )
    if result.returncode != 0:
        _tf_error(
            f"Invalid output from 'terraform workspace select {workspace}' command.",
            debug,
            result,
        )


def _run_terraform_plan(vfiles, tfplan_path, debug):
    """Generate terraform plan binary."""
    click.echo(click.style(f"\nGenerating Terraform Plan..\n", fg="white", bold=True))
    plan_cmd = ["terraform", "plan", "-refresh=false"]
    for vf in vfiles:
        plan_cmd.extend(["-var-file", vf])
    plan_cmd.extend(["-out", tfplan_path])
    result = subprocess.run(plan_cmd, capture_output=not debug, text=True)
    if result.returncode != 0:
        _tf_error(
            "Invalid output from 'terraform plan' command. "
            "Try using the terraform CLI first to check source files have no errors.",
            debug,
            result,
        )


def _decode_plan(tfplan_path, tfplan_json_path, tfgraph_path, debug):
    """Convert plan binary to JSON and generate terraform graph.

    Returns:
        Tuple of (plandata, graphdata)
    """
    click.echo(click.style(f"\nDecoding plan..\n", fg="white", bold=True))
    if not os.path.exists(tfplan_path):
        _tf_error(f"Terraform plan file not found at {tfplan_path}")
    # Convert binary plan to JSON
    with open(tfplan_json_path, "w") as f:
        result = subprocess.run(
            ["terraform", "show", "-json", tfplan_path],
            stdout=f,
            stderr=None if debug else subprocess.PIPE,
            text=True,
        )
    if result.returncode != 0:
        _tf_error("Invalid output from 'terraform show' command.", debug, result)
    click.echo(click.style(f"\nAnalysing plan..\n", fg="white", bold=True))
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
    if result.returncode != 0:
        _tf_error(
            "Invalid output from 'terraform graph' command. "
            "Check your TF source files can generate a valid plan and graph",
            debug,
            result,
        )
    click.echo(
        click.style(
            f"\nConverting TF Graph Connections..  (this may take a while)\n",
            fg="white",
            bold=True,
        )
    )
    graphdata = convert_dot_to_json(tfgraph_path)
    return plandata, graphdata


def tf_initplan(
    source: str,
    varfile: List[str],
    workspace: str,
    debug: bool = True,
    upgrade: bool = False,
) -> Dict[str, Any]:
    """Initialize Terraform and generate plan and graph data.

    Args:
        source: Source location (directory or Git URL)
        varfile: List of variable files to use
        workspace: Terraform workspace name
        debug: Show subprocess output to console
        upgrade: Pass -upgrade flag to terraform init

    Returns:
        Dictionary containing terraform plan and graph data
    """
    debug = True
    override_dest = None
    cloud_backups: List[Tuple[str, str]] = []
    try:
        # Clone repo (if git URL) or resolve local path then write override.tf for local backend
        codepath, override_dest, cloud_backups = _prepare_source(source)
        # Run terraform init (downloads providers/modules).
        # Skip -reconfigure when we stripped a cloud block — it's not
        # needed and we want init to succeed cleanly against the local backend.
        _run_terraform_init(debug, upgrade, skip_reconfigure=bool(cloud_backups))
        # Select or create the terraform workspace
        _select_workspace(workspace, debug)
        # Resolve variable file paths to absolute
        vfiles = [
            vf if os.path.isabs(vf) else os.path.join(START_DIR, vf) for vf in varfile
        ]
        # Setup temporary file paths
        tempdir = os.path.dirname(temp_dir.name)
        tfplan_path = os.path.join(tempdir, "tfplan.bin")
        tfplan_json_path = os.path.join(tempdir, "tfplan.json")
        tfgraph_path = os.path.join(tempdir, "tfgraph.dot")

        # Run terraform plan to generate the binary plan file
        _run_terraform_plan(vfiles, tfplan_path, debug)
        # Convert binary plan to JSON and generate the dependency graph
        plandata, graphdata = _decode_plan(
            tfplan_path, tfplan_json_path, tfgraph_path, debug
        )
        # Assemble tfdata dict with plan output and graph connections
        tfdata = dict()
        tfdata["codepath"] = list()
        tfdata["workdir"] = os.getcwd()
        # Store the TF_DATA_DIR so read_tfsource can find modules/modules.json.
        tfdata["terraform_init_dir"] = temp_dir.name
        tfdata["plandata"] = dict(plandata)
        tfdata = make_tf_data(tfdata, plandata, graphdata, codepath)
        os.chdir(START_DIR)
        return tfdata
    finally:
        # Always clean up override.tf and restore cloud-block backups,
        # even if an error occurred
        _cleanup_override(override_dest)
        _restore_cloud_backups(cloud_backups)


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
        raise helpers.TerravisionError(
            "Invalid output from 'terraform plan' command. Try using the terraform CLI "
            "first to check source actually generates resources and has no errors.",
            tfdata=tfdata,
        )
    tfdata["tfgraph"] = graphdata
    return tfdata


def _detect_provider(tfdata):
    """Detect cloud provider from terraform plan resources.

    Returns:
        Detected provider string (e.g. 'aws', 'azure', 'gcp')
    """
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
        raise provider_detector.ProviderDetectionError(
            "Could not detect cloud provider from Terraform plan. "
            "Ensure your Terraform code contains cloud resources (aws_, azurerm_, google_, etc.)"
        )
    return detected_provider


def setup_tfdata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize tfdata data structures from terraform plan.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with initialized graph structures
    """
    detected_provider = _detect_provider(tfdata)
    cloud_config = config_loader.load_config(detected_provider)
    hidden_nodes = getattr(cloud_config, f"{detected_provider.upper()}_HIDE_NODES", [])
    # Initialize graph data structures
    tfdata["graphdict"] = dict()
    tfdata["meta_data"] = dict()
    tfdata["all_output"] = dict()
    tfdata["node_list"] = list()
    tfdata["hidden"] = hidden_nodes
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
                # Mark fields that are "known after apply" without overwriting real values
                for k, v in object["change"]["after_unknown"].items():
                    if k not in details or details[k] is None:
                        details[k] = v
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


_TILDE_SUFFIX_RE = re.compile(r"~\d+$")


def _normalize_for_gvid_match(name: str) -> str:
    """Strip terravision's ~N suffix and any [...] index segments.

    `terraform graph` output (the source of gvid_table) never contains either
    of these, so this is the canonical match form for both sides.
    """
    return _TILDE_SUFFIX_RE.sub("", helpers.remove_brackets_and_numbers(name))


def find_node_in_gvid_table(node: str, gvid_table: List[str]) -> int:
    """Find node ID in gvid_table by trying name variations.

    Args:
        node: Resource node name to find
        gvid_table: List of node names from terraform graph

    Returns:
        Index of node in gvid_table

    Raises:
        TerravisionError: If the node cannot be matched to any gvid entry.
    """
    # Try exact match first
    if node in gvid_table:
        return gvid_table.index(node)

    # Strip both for_each / count brackets AND the ~N suffix that
    # setup_tfdata appends. Handles nested-module + count cases like
    # `module.foo["key"].module.bar.aws_thing.x[0]~1`.
    nodename = _normalize_for_gvid_match(node)
    if nodename in gvid_table:
        return gvid_table.index(nodename)

    # Last-resort: drop module prefix (legacy fallback for non-module resources
    # whose gvid_table entry is the bare `<type>.<name>` form).
    nodename = helpers.get_no_module_no_number_name(node)
    if nodename in gvid_table:
        return gvid_table.index(nodename)

    # No match found - raise with diagnostic context
    normalized = _normalize_for_gvid_match(node)
    base = node.split(".")[-1].split("[")[0].split("~")[0]
    near = [n for n in gvid_table if base and base in n][:5]
    near_str = "\n  ".join(near) if near else "(no near matches)"
    raise helpers.TerravisionError(
        f"Cannot map node {node} to graph connections.\n"
        f"  Normalized form tried: {normalized}\n"
        f"  gvid_table has {len(gvid_table)} entries; nearest matches:\n  {near_str}"
    )


def _build_gvid_table(tfdata):
    """Build lookup table mapping terraform graph IDs to resource names."""
    gvid_table = list()
    for item in tfdata["tfgraph"]["objects"]:
        gvid = item["_gvid"]
        gvid_table.append("")
        # Use name for modules, label for resources
        if item.get("name").startswith("module."):
            gvid_table[gvid] = str(item.get("name"))
        else:
            gvid_table[gvid] = str(item.get("label"))
    return gvid_table


def _process_edges(tfdata, gvid_table, reverse_arrow_list):
    """Walk terraform graph edges and populate graphdict connections."""
    for node in dict(tfdata["graphdict"]):
        try:
            node_id = find_node_in_gvid_table(node, gvid_table)
        except helpers.TerravisionError as e:
            e.tfdata = tfdata
            raise
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
                    # Handle reverse arrow resources (connection points to node).
                    # The reverse_arrow_list entries are prefixes (e.g.
                    # "aws_cloudfront") that must match against the full
                    # resource type (e.g. "aws_cloudfront_distribution").
                    if any(conn_type.startswith(r) for r in reverse_arrow_list):
                        if conn not in tfdata["graphdict"].keys():
                            tfdata["graphdict"][conn] = list()
                        # Skip multi-instance resources
                        if "[" not in conn:
                            if node not in tfdata["graphdict"][conn]:
                                tfdata["graphdict"][conn].append(node)
                    # Normal arrow (node points to connection)
                    else:
                        if "[" not in node:
                            if conn not in tfdata["graphdict"].get(node, []):
                                tfdata["graphdict"][node].append(conn)


def tf_makegraph(tfdata: Dict[str, Any], debug: bool) -> Dict[str, Any]:
    """Build resource dependency graph from terraform graph output.

    Args:
        tfdata: Terraform data dictionary with plan and graph data

    Returns:
        Updated tfdata with populated graphdict connections
    """
    # Detect cloud provider and load provider-specific config
    detected_provider = _detect_provider(tfdata)
    cloud_config = config_loader.load_config(detected_provider)
    reverse_arrow_list = getattr(
        cloud_config, f"{detected_provider.upper()}_REVERSE_ARROW_LIST", []
    )

    # Create graph nodes from terraform plan resources
    tfdata = setup_tfdata(tfdata)
    # Map terraform graph IDs to resource names
    gvid_table = _build_gvid_table(tfdata)
    # Walk graph edges and populate connections between nodes
    _process_edges(tfdata, gvid_table, reverse_arrow_list)
    # Add VPC-subnet relationships based on CIDR overlap
    tfdata = add_vpc_implied_relations(tfdata)

    # Save original graph and metadata for reference
    tfdata["original_graphdict"] = copy.deepcopy(tfdata["graphdict"])
    tfdata["original_metadata"] = copy.deepcopy(tfdata["meta_data"])

    # Verify cloud resources exist
    from modules.provider_detector import PROVIDER_PREFIXES

    has_cloud_resources = any(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], prefix)
        for prefix in PROVIDER_PREFIXES.keys()
    )
    if not has_cloud_resources:
        raise helpers.TerravisionError(
            "No AWS, Azure or Google resources will be created with current plan.",
            tfdata=tfdata,
        )
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
    # Link subnets to VPCs based on CIDR overlap (within same module only)
    if len(vpc_resources) > 0 and len(subnet_resources) > 0:
        for vpc in vpc_resources:
            try:
                vpc_cidr = ipaddr.IPNetwork(tfdata["meta_data"][vpc]["cidr_block"])
            except (ValueError, KeyError):
                continue
            # Extract module prefix (e.g., "module.gitlab_vpc." from "module.gitlab_vpc.aws_vpc.vpc")
            vpc_module = (
                ".".join(vpc.split(".")[:2]) + "." if vpc.startswith("module.") else ""
            )
            for subnet in subnet_resources:
                # Only connect subnets in the same module as the VPC
                subnet_module = (
                    ".".join(subnet.split(".")[:2]) + "."
                    if subnet.startswith("module.")
                    else ""
                )
                if vpc_module != subnet_module:
                    continue
                try:
                    subnet_cidr = ipaddr.IPNetwork(
                        tfdata["meta_data"][subnet]["cidr_block"]
                    )
                except (ValueError, KeyError):
                    continue
                # Add subnet to VPC if CIDR ranges overlap and not already present
                if (
                    subnet_cidr.overlaps(vpc_cidr)
                    and subnet not in tfdata["graphdict"][vpc]
                ):
                    tfdata["graphdict"][vpc].append(subnet)
    return tfdata


def load_json_source(source: str) -> Dict[str, Any]:
    """Load and parse JSON source file.

    Args:
        source: Path to JSON file

    Returns:
        Dictionary containing tfdata with graphdict and metadata
    """
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


def process_pregenerated_source(
    planfile: str,
    graphfile: str,
    source: str,
    annotate: str,
    debug: bool,
) -> Dict[str, Any]:
    """Process pre-generated Terraform plan and graph files with source directory.

    Loads plan JSON and graph DOT, builds tfdata using existing pipeline functions,
    then enriches with HCL parsing from source directory. No Terraform CLI execution.

    Args:
        planfile: Path to Terraform plan JSON file
        graphfile: Path to Terraform graph DOT file
        source: List of source directory paths
        annotate: Path to annotations file
        debug: Enable debug mode

    Returns:
        Dictionary containing parsed Terraform data
    """
    click.echo(
        click.style(
            "\nUsing pre-generated plan and graph files. "
            "No Terraform commands will be executed.\n",
            fg="cyan",
            bold=True,
        )
    )

    # Load and validate plan JSON
    plandata = validators.validate_planfile(planfile)

    # Convert DOT graph to JSON using Graphviz
    click.echo(
        click.style("Converting TF Graph Connections..\n", fg="white", bold=True)
    )
    graphdata = convert_dot_to_json(graphfile)

    # Build tfdata from plan and graph data
    tfdata = dict()
    tfdata["codepath"] = list()
    tfdata["workdir"] = os.getcwd()
    tfdata["plandata"] = dict(plandata)
    # Keep URLs as-is so read_tfsource can clone them; only resolve local paths
    codepath = (
        source
        if helpers.check_for_domain(source) or source.startswith("git::")
        else os.path.abspath(source)
    )
    tfdata = make_tf_data(tfdata, plandata, graphdata, codepath)

    # Build resource dependency graph
    tfdata = tf_makegraph(tfdata, debug)

    # Parse source directory for HCL metadata
    codepath_list = (
        [tfdata["codepath"]]
        if isinstance(tfdata["codepath"], str)
        else tfdata["codepath"]
    )
    tfdata = fileparser.read_tfsource(codepath_list, [], annotate, tfdata)

    # Validate consistency across inputs
    validators.validate_consistency(tfdata)

    if debug:
        helpers.export_tfdata(tfdata)

    return tfdata


def process_terraform_source(
    source: str,
    varfile: List[str],
    workspace: str,
    annotate: str,
    debug: bool,
    upgrade: bool = False,
) -> Dict[str, Any]:
    """Process Terraform source files and generate initial tfdata.

    Args:
        source: Source path (folder or git URL)
        varfile: List of variable file paths
        workspace: Terraform workspace name
        annotate: Path to annotations file
        debug: Enable debug mode
        upgrade: Pass -upgrade flag to terraform init

    Returns:
        Dictionary containing parsed Terraform data
    """
    tfdata = tf_initplan(source, varfile, workspace, debug, upgrade)
    tfdata = tf_makegraph(tfdata, debug)
    codepath = (
        [tfdata["codepath"]]
        if isinstance(tfdata["codepath"], str)
        else tfdata["codepath"]
    )
    tfdata = fileparser.read_tfsource(codepath, varfile, annotate, tfdata)
    if debug:
        helpers.export_tfdata(tfdata)
    return tfdata
