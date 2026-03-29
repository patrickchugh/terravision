"""Terragrunt wrapper for executing terragrunt commands and parsing output.

Handles detection of Terragrunt sources, execution of terragrunt init/plan/graph,
multi-module plan merging, and cross-module dependency linking via HCL parsing.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import click
import hcl2

import modules.tfwrapper as tfwrapper

MIN_TERRAGRUNT_VERSION = "0.50.0"


def _tg_env() -> dict:
    """Build environment for all terragrunt subprocess calls.

    Sets TF_CLI_ARGS_init=-reconfigure so that ANY terraform init
    triggered by Terragrunt (explicit or auto-init for dependencies)
    accepts the local backend override without prompting for migration.
    """
    env = dict(os.environ)
    env["TF_CLI_ARGS_init"] = "-reconfigure"
    return env


def _find_terragrunt_cache_dir(workdir: str) -> str:
    """Find the terraform working directory inside .terragrunt-cache.

    Terragrunt downloads sources into .terragrunt-cache/<hash>/<hash>/.
    For sources with a //subfolder (e.g., git::https://...//modules/vpc),
    terraform runs inside the subfolder, not the repo root.

    We locate the working directory by searching for Terragrunt-generated
    files (backend.tf or provider.tf with the Terragrunt signature).

    Args:
        workdir: The terragrunt module source directory.

    Returns:
        Absolute path to the terraform working directory in cache.

    Raises:
        RuntimeError: If cache structure not found.
    """
    cache_root = os.path.join(workdir, ".terragrunt-cache")
    if not os.path.isdir(cache_root):
        raise RuntimeError(
            f"No .terragrunt-cache found in {workdir}. "
            "Ensure terragrunt init ran successfully."
        )
    # Search for Terragrunt-generated files to find the actual working dir.
    # These are placed in the directory where terraform runs, which may be
    # a subfolder for sources like git::https://...//modules/db_subnet_group.
    for root, dirs, files in os.walk(cache_root):
        dirs[:] = [d for d in dirs if d != ".terraform"]
        for gen_file in ("backend.tf", "provider.tf"):
            if gen_file in files:
                filepath = os.path.join(root, gen_file)
                try:
                    with open(filepath) as f:
                        if "Terragrunt" in f.read(200):
                            return root
                except OSError:
                    continue
    # Fallback: return the first hash2 directory
    for hash1 in os.listdir(cache_root):
        hash1_path = os.path.join(cache_root, hash1)
        if not os.path.isdir(hash1_path):
            continue
        for hash2 in os.listdir(hash1_path):
            hash2_path = os.path.join(hash1_path, hash2)
            if os.path.isdir(hash2_path):
                return hash2_path
    raise RuntimeError(
        f"No cache subdirectory found in {cache_root}. "
        "Ensure terragrunt init ran successfully."
    )


def detect_terragrunt(source_path: str) -> dict:
    """Detect if a source directory is a Terragrunt project.

    Scans for terragrunt.hcl in the source directory and child directories.
    Skips .terragrunt-cache directories.

    Args:
        source_path: Absolute path to the source directory.

    Returns:
        Dict with keys: is_terragrunt, is_multi_module, child_modules.
    """
    result = {
        "is_terragrunt": False,
        "is_multi_module": False,
        "child_modules": [],
    }
    abs_source = os.path.abspath(source_path)
    # Check if source dir itself has terragrunt.hcl
    if os.path.isfile(os.path.join(abs_source, "terragrunt.hcl")):
        result["is_terragrunt"] = True

    # Scan child directories for terragrunt.hcl (recursive, skip cache dirs)
    child_modules = []
    for root, dirs, files in os.walk(abs_source):
        # Skip .terragrunt-cache directories
        dirs[:] = [d for d in dirs if d != ".terragrunt-cache"]
        # Skip the source dir itself (already checked)
        if os.path.abspath(root) == abs_source:
            continue
        if "terragrunt.hcl" in files:
            child_modules.append(os.path.abspath(root))

    if child_modules:
        result["is_terragrunt"] = True
        result["is_multi_module"] = True
        result["child_modules"] = sorted(child_modules)

    return result


def _parse_version(version_str: str) -> tuple:
    """Parse a version string into a comparable tuple."""
    parts = version_str.strip().split(".")
    return tuple(int(p) for p in parts[:3])


def check_terragrunt_version() -> str:
    """Check that terragrunt is installed and meets minimum version.

    Returns:
        Version string (e.g., "0.67.4").

    Raises:
        FileNotFoundError: If terragrunt binary is not in PATH.
        RuntimeError: If version is below minimum.
    """
    try:
        result = subprocess.run(
            ["terragrunt", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            "Terragrunt detected but 'terragrunt' command not found. "
            "Install from https://terragrunt.gruntwork.io/docs/getting-started/install/"
        )

    # Parse version from output like "terragrunt version v0.67.4"
    output = result.stdout + result.stderr
    match = re.search(r"v?(\d+\.\d+\.\d+)", output)
    if not match:
        raise RuntimeError(
            f"Could not parse Terragrunt version from output: {output.strip()}"
        )

    version = match.group(1)
    if _parse_version(version) < _parse_version(MIN_TERRAGRUNT_VERSION):
        raise RuntimeError(
            f"Terragrunt version {version} is not supported. "
            f"Please upgrade to v{MIN_TERRAGRUNT_VERSION} or later."
        )

    return version


def _prepare_tg_source(source: str) -> Tuple[str, str]:
    """Prepare a Terragrunt source directory for plan execution.

    Writes terravision_override.tf to the source directory to force a
    local backend. Terragrunt copies ALL files from the module directory
    (including .tf files) into .terragrunt-cache before running Terraform,
    even when terraform.source is a remote URL.  The override file uses
    Terraform's standard _override.tf naming convention to take precedence
    over any generated backend.tf.

    Args:
        source: Path to the source directory.

    Returns:
        Tuple of (codepath, override_dest).
    """
    codepath = os.path.abspath(source)
    override_path = os.path.join(codepath, "terravision_override.tf")
    if os.path.exists(override_path):
        # Already written by tg_run_all_plan — don't double-write or double-clean
        return codepath, None
    override_dest = tfwrapper._write_override(codepath)
    return codepath, override_dest


def _run_terragrunt_init(workdir: str, debug: bool) -> None:
    """Run terragrunt init in the working directory.

    Passes -reconfigure both as a CLI flag and via TF_CLI_ARGS_init
    (see _tg_env) so that Terraform accepts the local backend override
    (terravision_override.tf) without prompting for state migration.

    The override file must be written to the source directory BEFORE
    calling this function. Terragrunt copies all .tf files from the
    module directory into .terragrunt-cache, so the override reaches
    Terraform via the standard _override.tf naming convention.

    For multi-module runs, the env var also ensures that auto-init of
    dependency modules (to read outputs) uses -reconfigure, so their
    local backend override is accepted too.
    """
    click.echo(click.style("\nRunning Terragrunt Init..\n", fg="white", bold=True))
    init_cmd = ["terragrunt", "init", "-reconfigure"]
    result = subprocess.run(
        init_cmd, capture_output=not debug, text=True, cwd=workdir, env=_tg_env()
    )
    if result.returncode != 0:
        stderr = result.stderr or ""
        hint = ""
        if "find_in_parent_folders" in stderr:
            hint = (
                "\nHint: Terragrunt uses find_in_parent_folders() to locate config "
                "files (e.g., root.hcl, account.hcl) in parent directories. "
                "Make sure --source points to a path where parent directories "
                "are accessible. If using Docker, mount the entire infrastructure "
                "repo root (not just a subdirectory) so that parent HCL files "
                "are reachable."
            )
        elif "Could not download module" in stderr or "Module not found" in stderr:
            hint = "\nHint: Check that the module source URL is accessible and credentials are configured."
        elif "error downloading" in stderr or "unable to fork" in stderr:
            hint = (
                "\nHint: Failed to download a module source. If using Docker, "
                "ensure SSH keys and git are available inside the container "
                "(e.g., mount ~/.ssh). For HTTPS sources, ensure credentials "
                "are configured."
            )
        elif ".terragrunt-cache" in stderr:
            hint = "\nHint: Try clearing the cache with: rm -rf .terragrunt-cache"
        raise RuntimeError(f"Terragrunt init failed:\n{stderr}{hint}")


def _run_terragrunt_plan(
    workdir: str, varfiles: list, tfplan_path: str, debug: bool
) -> None:
    """Run terragrunt plan with -refresh=false."""
    click.echo(click.style("\nGenerating Terragrunt Plan..\n", fg="white", bold=True))
    plan_cmd = ["terragrunt", "plan", "-refresh=false"]
    for vf in varfiles:
        plan_cmd.extend(["-var-file", vf])
    plan_cmd.extend(["-out", tfplan_path])
    result = subprocess.run(
        plan_cmd, capture_output=not debug, text=True, cwd=workdir, env=_tg_env()
    )
    if result.returncode != 0:
        stderr = result.stderr or ""
        hint = ""
        if "mock_outputs" in stderr or "dependency" in stderr.lower():
            hint = (
                "\nHint: If this module has dependencies on undeployed modules, "
                "ensure mock_outputs are configured in the dependency blocks."
            )
        raise RuntimeError(f"Terragrunt plan failed:\n{stderr}{hint}")


def _decode_tg_plan(
    workdir: str,
    tfplan_path: str,
    tfplan_json_path: str,
    tfgraph_path: str,
    debug: bool,
) -> Tuple[dict, dict]:
    """Decode terragrunt plan and graph output into JSON.

    Runs terraform show -json and terraform graph directly in the
    .terragrunt-cache directory.  We avoid running these via terragrunt
    because Terragrunt's auto-init can re-process the cache (re-download
    source, re-run generate blocks) which disrupts the backend state
    between the plan and decode phases.

    Returns:
        Tuple of (plan_data, graph_data).
    """
    cache_dir = _find_terragrunt_cache_dir(workdir)

    # Generate plan JSON via terraform show directly in cache
    with open(tfplan_json_path, "w") as f:
        result = subprocess.run(
            ["terraform", "show", "-json", tfplan_path],
            stdout=f,
            stderr=None if debug else subprocess.PIPE,
            text=True,
            cwd=cache_dir,
        )
    if result.returncode != 0:
        raise RuntimeError(f"Terraform show failed:\n{result.stderr or ''}")

    with open(tfplan_json_path) as f:
        plan_data = json.load(f)

    # Generate graph DOT
    with open(tfgraph_path, "w") as f:
        result = subprocess.run(
            ["terraform", "graph"],
            stdout=f,
            stderr=None if debug else subprocess.PIPE,
            text=True,
            cwd=cache_dir,
        )
    if result.returncode != 0:
        raise RuntimeError(f"Terraform graph failed:\n{result.stderr or ''}")

    # Convert DOT to JSON
    graph_data = tfwrapper.convert_dot_to_json(tfgraph_path)

    return plan_data, graph_data


def tg_initplan(
    source: str,
    varfile: list,
    workspace: str,
    debug: bool,
    upgrade: bool,
) -> dict:
    """Execute terragrunt init, plan, show, and graph for a single module.

    Returns tfdata dict in the same format as tfwrapper.tf_initplan().
    Note: generate blocks (backend.tf, provider.tf) are handled automatically
    by the Terragrunt CLI delegation.
    """
    check_terragrunt_version()
    codepath, override_dest = _prepare_tg_source(source)

    tfplan_path = os.path.join(tempfile.gettempdir(), "tg_tfplan.bin")
    tfplan_json_path = os.path.join(tempfile.gettempdir(), "tg_tfplan.json")
    tfgraph_path = os.path.join(tempfile.gettempdir(), "tg_tfgraph.dot")

    try:
        _run_terragrunt_init(codepath, debug)
        _run_terragrunt_plan(codepath, varfile, tfplan_path, debug)
        plan_data, graph_data = _decode_tg_plan(
            codepath, tfplan_path, tfplan_json_path, tfgraph_path, debug
        )
    finally:
        tfwrapper._cleanup_override(override_dest)

    # Build tfdata matching tf_initplan output format
    tfdata = {
        "codepath": codepath,
        "workdir": str(Path.cwd()),
        "terraform_init_dir": os.environ.get("TF_DATA_DIR", ""),
        "plandata": plan_data,
        "tf_resources_created": plan_data.get("resource_changes", []),
        "tfgraph": graph_data,
        "graphdict": {},
        "meta_data": {},
        "node_list": [],
        "annotations": {},
        "all_output": {},
        "hidden": [],
        "is_terragrunt": True,
    }

    return tfdata


def _discover_child_modules(source: str) -> List[str]:
    """Discover child directories containing terragrunt.hcl.

    Walks the source directory recursively, skipping .terragrunt-cache.

    Args:
        source: Root directory to scan.

    Returns:
        List of absolute paths to child module directories.
    """
    result = detect_terragrunt(source)
    return result["child_modules"]


def _module_name_from_path(source_root: str, module_path: str) -> str:
    """Derive a module name from relative path, replacing separators with underscores."""
    rel = os.path.relpath(module_path, source_root)
    return rel.replace(os.sep, "_").replace("/", "_")


def _parse_tg_dependencies(module_path: str) -> dict:
    """Parse dependency blocks and inputs from a terragrunt.hcl file.

    Uses python-hcl2 to parse the HCL. Extracts dependency blocks and
    inputs that reference dependency.<name>.outputs.<key>.

    Args:
        module_path: Absolute path to directory containing terragrunt.hcl.

    Returns:
        Dict with keys:
          - "dependencies": {dep_name: config_path}
          - "dep_inputs": {input_key: {"dep_name": str, "output_key": str}}
    """
    hcl_path = os.path.join(module_path, "terragrunt.hcl")
    result = {"dependencies": {}, "dep_inputs": {}}

    if not os.path.isfile(hcl_path):
        return result

    try:
        with open(hcl_path) as f:
            parsed = hcl2.load(f)
    except Exception:
        return result

    # Extract dependency blocks: dependency "name" { config_path = "..." }
    for dep_block in parsed.get("dependency", []):
        if isinstance(dep_block, dict):
            for dep_name, dep_config in dep_block.items():
                if isinstance(dep_config, dict):
                    config_path = dep_config.get("config_path", "")
                    abs_config = os.path.normpath(
                        os.path.join(module_path, config_path)
                    )
                    result["dependencies"][dep_name] = abs_config

    # Extract inputs block and find dependency references
    raw_inputs = parsed.get("inputs", {})
    if isinstance(raw_inputs, list):
        inputs = raw_inputs[0] if raw_inputs and isinstance(raw_inputs[0], dict) else {}
    elif isinstance(raw_inputs, dict):
        inputs = raw_inputs
    else:
        inputs = {}

    dep_ref_pattern = re.compile(r"dependency\.(\w+)\.outputs\.(\w+)")
    for input_key, input_value in inputs.items():
        val_str = str(input_value)
        match = dep_ref_pattern.search(val_str)
        if match:
            result["dep_inputs"][input_key] = {
                "dep_name": match.group(1),
                "output_key": match.group(2),
            }

    return result


def _find_resource_by_type_hint(resource_changes: list, type_hint: str) -> str:
    """Find a resource address whose type matches an output key name hint.

    E.g., type_hint="vpc_id" -> look for resources starting with "aws_vpc",
    "google_compute_network", "azurerm_virtual_network".
    """
    # Build candidate type prefixes from the hint
    # vpc_id -> vpc, subnet_ids -> subnet, security_group_id -> security_group
    hint = re.sub(r"_?ids?$", "", type_hint)  # strip trailing _id/_ids

    for rc in resource_changes:
        if rc.get("mode") != "managed":
            continue
        rtype = rc.get("type", "")
        # Check if resource type contains the hint (e.g., "aws_vpc" contains "vpc")
        type_suffix = rtype.split("_", 1)[-1] if "_" in rtype else rtype
        if hint and hint in type_suffix:
            return rc.get("address", "")

    # Fallback: return first managed resource
    for rc in resource_changes:
        if rc.get("mode") == "managed":
            return rc.get("address", "")

    return ""


def _inject_dependency_refs(
    merged_tfdata: dict,
    per_module_deps: Dict[str, dict],
    per_module_resources: Dict[str, list],
    source_root: str,
) -> dict:
    """Inject cross-module edges into graphdict based on dependency blocks.

    For each consumer module's dependency, finds the matching producer resource
    and adds a direct edge in graphdict from consumer resources to the producer
    resource. This is more reliable than metadata injection because terraform
    plan already resolves variables to their final values (mock values), so
    there's no variable reference left in metadata to replace.
    """
    for consumer_name, deps in per_module_deps.items():
        for input_key, dep_info in deps.get("dep_inputs", {}).items():
            dep_name = dep_info["dep_name"]
            output_key = dep_info["output_key"]

            # Find the producer module's config path and its module name
            producer_path = deps["dependencies"].get(dep_name, "")
            if not producer_path:
                continue
            producer_name = _module_name_from_path(source_root, producer_path)

            # Find matching resource in producer's plan
            # Note: resource addresses in per_module_resources are already prefixed
            # with module.<name>. from the plan merging step
            producer_resources = per_module_resources.get(producer_name, [])
            matched_address = _find_resource_by_type_hint(
                producer_resources, output_key
            )
            if not matched_address:
                continue

            # matched_address is already prefixed (e.g., "module.vpc.aws_subnet.public")
            prefixed_producer = matched_address

            # Add edges from consumer resources to producer resource in graphdict
            consumer_prefix = f"module.{consumer_name}."
            for node in list(merged_tfdata.get("graphdict", {}).keys()):
                if node.startswith(consumer_prefix):
                    connections = merged_tfdata["graphdict"][node]
                    if prefixed_producer not in connections:
                        connections.append(prefixed_producer)

    return merged_tfdata


def tg_run_all_plan(
    source: str,
    varfile: list,
    workspace: str,
    debug: bool,
    upgrade: bool,
) -> dict:
    """Execute terragrunt plan for all child modules and merge results.

    Discovers child modules, runs tg_initplan() on each, merges plans
    with module.<relative_path>. prefixes, parses dependency blocks, and
    injects cross-module references into metadata.

    Returns unified tfdata dict.
    """
    check_terragrunt_version()
    source_root = os.path.abspath(source)
    child_modules = _discover_child_modules(source_root)

    if not child_modules:
        raise RuntimeError(
            f"No child modules found in {source_root}. "
            "Expected directories containing terragrunt.hcl."
        )

    # Write override files to ALL child modules before running any plans.
    # This ensures dependency resolution (terragrunt auto-inits dependency
    # modules to read outputs) also picks up the local backend override.
    override_files = []
    for module_path in child_modules:
        override_dest = tfwrapper._write_override(module_path)
        override_files.append(override_dest)

    try:
        return _run_all_modules(
            source_root, child_modules, varfile, workspace, debug, upgrade
        )
    finally:
        for f in override_files:
            tfwrapper._cleanup_override(f)


def _run_all_modules(
    source_root: str,
    child_modules: List[str],
    varfile: list,
    workspace: str,
    debug: bool,
    upgrade: bool,
) -> dict:
    """Run plans for all child modules and merge results."""
    # Collect per-module plans
    per_module_results = {}
    per_module_resources = {}
    all_resource_changes = []
    first_codepath = None

    for module_path in child_modules:
        mod_name = _module_name_from_path(source_root, module_path)
        click.echo(
            click.style(
                f"\nProcessing Terragrunt module: {mod_name}\n",
                fg="cyan",
            )
        )
        mod_tfdata = tg_initplan(module_path, varfile, workspace, debug, upgrade)
        per_module_results[mod_name] = mod_tfdata
        per_module_resources[mod_name] = mod_tfdata.get("tf_resources_created", [])
        if first_codepath is None:
            first_codepath = mod_tfdata["codepath"]

        # Prefix resource addresses with module.<name>.
        for rc in mod_tfdata.get("tf_resources_created", []):
            original_addr = rc.get("address", "")
            rc["address"] = f"module.{mod_name}.{original_addr}"
            if "module_address" in rc:
                rc["module_address"] = f"module.{mod_name}.{rc['module_address']}"
            else:
                rc["module_address"] = f"module.{mod_name}"
            all_resource_changes.append(rc)

    # Merge into unified tfdata
    merged_tfdata = {
        "codepath": first_codepath or source_root,
        "workdir": str(Path.cwd()),
        "terraform_init_dir": os.environ.get("TF_DATA_DIR", ""),
        "plandata": {"resource_changes": all_resource_changes},
        "tf_resources_created": all_resource_changes,
        "tfgraph": _merge_graphs(per_module_results, source_root),
        "graphdict": {},
        "meta_data": {},
        "node_list": [],
        "annotations": {},
        "all_output": {},
        "hidden": [],
        "is_terragrunt": True,
    }

    # Parse dependencies from each child's terragrunt.hcl
    per_module_deps = {}
    for module_path in child_modules:
        mod_name = _module_name_from_path(source_root, module_path)
        try:
            deps = _parse_tg_dependencies(module_path)
            per_module_deps[mod_name] = deps
        except Exception as e:
            click.echo(
                click.style(
                    f"Warning: Could not parse dependencies for {mod_name}: {e}",
                    fg="yellow",
                )
            )

    # Inject cross-module references (done after setup_tfdata populates meta_data)
    merged_tfdata["_tg_dependency_info"] = {
        "per_module_deps": per_module_deps,
        "per_module_resources": per_module_resources,
        "source_root": source_root,
    }

    return merged_tfdata


def _merge_graphs(per_module_results: Dict[str, dict], source_root: str) -> dict:
    """Merge per-module DOT graphs into one combined graph.

    Prefixes node IDs with module.<name>. and concatenates all edges.
    Returns a merged graph data dict.
    """
    merged = {"name": "merged", "objects": [], "edges": []}

    for mod_name, mod_tfdata in per_module_results.items():
        graph = mod_tfdata.get("tfgraph", {})
        if not graph:
            continue

        # Remap node IDs with offset to avoid collisions
        id_offset = len(merged["objects"])

        for obj in graph.get("objects", []):
            new_obj = dict(obj)
            new_obj["_gvid"] = obj.get("_gvid", 0) + id_offset
            # Prefix the node name
            name = obj.get("name", "")
            new_obj["name"] = f"module.{mod_name}.{name}"
            merged["objects"].append(new_obj)

        for edge in graph.get("edges", []):
            new_edge = dict(edge)
            new_edge["tail"] = edge.get("tail", 0) + id_offset
            new_edge["head"] = edge.get("head", 0) + id_offset
            merged["edges"].append(new_edge)

    return merged
