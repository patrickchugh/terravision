"""File parser module for TerraVision.

This module handles parsing of Terraform files (.tf), variable files (.tfvars),
and annotation files (YAML). It discovers files from local directories or Git
repositories, parses HCL2 syntax, and extracts resources, modules, and variables.
"""

import fileinput
import io
import json
import os
import re
import tempfile
from pathlib import Path
from sys import exit
from typing import Dict, List, Tuple, Any, Optional

import click
import yaml
import hcl2

import modules.gitlibs as gitlibs

# Global module-level variables
annotations: Dict[str, Any] = dict()
ai_annotations: Dict[str, Any] = dict()
# Comments harvested from raw .tf files. Keyed by "<type>.<name>" when a
# comment block sits directly above a resource declaration; bare module
# /file-level intent is parked in tf_unattached_comments. Both buckets
# accumulate across iterative_parse() calls so a project with multiple
# nested modules collects everything.
tf_comments: Dict[str, str] = dict()
tf_unattached_comments: List[str] = list()
start_dir: Path = Path.cwd()
temp_dir: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory(
    dir=tempfile.gettempdir()
)
abspath: str = os.path.abspath(__file__)
dname: str = os.path.dirname(abspath)
MODULE_DIR: str = str(Path(Path.home(), ".terravision", "module_cache"))

# Create module cache directory if it doesn't exist
if not os.path.exists(MODULE_DIR):
    os.makedirs(MODULE_DIR)

# Terraform sections to extract during parsing
EXTRACT: List[str] = [
    "module",
    "output",
    "variable",
    "locals",
    "resource",
    "data",
    "provider",
]


# Match a `resource "<type>" "<name>" {` declaration. We deliberately do
# not try to handle every HCL edge case — quoted braces inside attribute
# values etc. Comment harvesting is best-effort context for the LLM, not
# a parser.
_HCL_RESOURCE_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
# A line that is purely a comment (allowing leading whitespace). Supports
# `#` and `//` line comments — block /* ... */ comments are rare in HCL
# and are skipped on purpose.
_HCL_COMMENT_LINE_RE = re.compile(r"^\s*(?://|#)\s?(.*)$")


def _extract_comments_from_tf(
    content: str,
    max_chars_per_resource: int = 500,
) -> "tuple[Dict[str, str], List[str]]":
    """Pull human-authored comments out of raw HCL source.

    Returns ``(per_resource, unattached)``:

      * ``per_resource`` maps a graphdict-style key (``aws_lambda_function.api``)
        to a single joined comment string. The mapped comment is the
        consecutive comment block that sits immediately above the
        ``resource "<type>" "<name>" {`` declaration. A blank line
        between the comment and the resource is tolerated — humans
        naturally space out documentation.
      * ``unattached`` collects comment lines that are not directly above
        a resource (file headers, comments inside locals/module blocks,
        explanatory paragraphs). These are still useful project-intent
        signal for the LLM, just not bound to a specific node.

    The function is regex-only and does not understand HCL syntax. False
    positives (e.g. ``#`` inside a quoted string) are accepted as the
    cost of keeping this scanner cheap. Output is hard-capped per
    resource so a giant doc-block above one node cannot starve the
    rest of the prompt budget.
    """
    per_resource: Dict[str, str] = {}
    unattached: List[str] = []
    pending: List[str] = []

    for line in content.splitlines():
        comment_match = _HCL_COMMENT_LINE_RE.match(line)
        if comment_match:
            text = comment_match.group(1).strip()
            if text:
                pending.append(text)
            continue

        # Blank line — keep the pending block alive; it might still
        # belong to the resource declared two lines down.
        if not line.strip():
            continue

        resource_match = _HCL_RESOURCE_RE.match(line)
        if resource_match and pending:
            type_name, local_name = resource_match.group(1), resource_match.group(2)
            key = f"{type_name}.{local_name}"
            joined = " ".join(pending)
            if len(joined) > max_chars_per_resource:
                joined = joined[:max_chars_per_resource] + "..."
            # Only the FIRST comment block wins for a given resource —
            # if the same key shows up twice (e.g. count expansions in
            # different files) we keep the earliest documentation.
            per_resource.setdefault(key, joined)
            pending = []
            continue

        # Some other code line (locals, variable, module, attribute,
        # closing brace). Anything pending is therefore not directly
        # above a resource declaration — drain it to the unattached
        # bucket so it still reaches the LLM.
        if pending:
            unattached.extend(pending)
            pending = []

    if pending:
        unattached.extend(pending)

    return per_resource, unattached


def _load_terraform_modules_json(source_dir: str) -> Dict[str, str]:
    """Load Terraform's modules.json and return module key to directory mapping.

    Terraform writes .terraform/modules/modules.json during 'terraform init' with
    a mapping of each module's key (name) to its local directory path. This allows
    terravision to use already-downloaded modules instead of re-cloning them.

    When TF_DATA_DIR is set, terraform stores modules at <TF_DATA_DIR>/modules/
    instead of <source_dir>/.terraform/modules/.

    Args:
        source_dir: Root directory of the Terraform source (where .terraform/ lives),
                    or the TF_DATA_DIR path directly

    Returns:
        Dictionary mapping module key to absolute directory path
    """
    # Check both the standard path and the TF_DATA_DIR path
    using_tf_data_dir = False
    tf_data_dir = os.environ.get("TF_DATA_DIR", "")
    if tf_data_dir:
        # TF_DATA_DIR replaces .terraform/, so modules.json is at <dir>/modules/
        if not os.path.isabs(tf_data_dir):
            tf_data_dir = os.path.join(source_dir, tf_data_dir)
        modules_json_path = os.path.join(tf_data_dir, "modules", "modules.json")
        using_tf_data_dir = True
    else:
        modules_json_path = os.path.join(
            source_dir, ".terraform", "modules", "modules.json"
        )
    if not os.path.exists(modules_json_path) and not tf_data_dir:
        # Fallback: check if source_dir itself is a TF_DATA_DIR-style path
        modules_json_path = os.path.join(source_dir, "modules", "modules.json")
        using_tf_data_dir = True
    if not os.path.exists(modules_json_path):
        return {}
    try:
        with open(modules_json_path, "r") as f:
            data = json.load(f)
        result: Dict[str, str] = {}
        for mod in data.get("Modules", []):
            key = mod.get("Key", "")
            dir_path = mod.get("Dir", "")
            if key and dir_path:
                if os.path.isabs(dir_path):
                    result[key] = dir_path
                else:
                    # When TF_DATA_DIR is used, Dir paths like ".terraform/modules/X"
                    # need ".terraform/" stripped since TF_DATA_DIR replaces it
                    if using_tf_data_dir and dir_path.startswith(".terraform/"):
                        dir_path = dir_path[len(".terraform/") :]
                    result[key] = os.path.normpath(os.path.join(source_dir, dir_path))
        return result
    except (json.JSONDecodeError, KeyError):
        return {}


def find_tf_files(
    source: str,
    paths: Optional[List[str]] = None,
    mod: str = "main",
    recursive: bool = False,
    version: str = "",
    terraform_modules: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Discover Terraform files in local directory or Git repository.

    Searches for .tf files, .tfvars files, and annotation YAML files in the
    specified source location. Handles both local directories and Git URLs.

    Args:
        source: Local directory path or Git repository URL
        paths: Existing list of file paths to append to (default: empty list)
        mod: Module name for organizing cloned repositories (default: 'main')
        recursive: Whether to recursively search subdirectories (default: False)
        version: Terraform version constraint (e.g., "~> 5.0")
        terraform_modules: Dict mapping module name to local directory from
            terraform's .terraform/modules/modules.json (optional)

    Returns:
        List of absolute paths to discovered Terraform files
    """
    global annotations
    global ai_annotations

    if paths is None:
        paths = list()

    yaml_detected = False

    # Clone Git repository or use local directory
    if not os.path.isdir(source):
        source_location = gitlibs.clone_files(
            source, temp_dir.name, mod, version, terraform_modules
        )
    else:
        source_location = source.strip()

    files = [f for f in os.listdir(source_location)]
    click.echo(f"  Added Source Location: {source}")

    # Scan for Terraform and annotation files
    for file in files:
        # Collect Terraform and variable files
        if (
            file.lower().endswith(".tf")
            or file.lower().endswith("auto.tfvars")
            or "terraform.tfvars" in file
        ):
            paths.append(os.path.join(source_location, file))

        # Load AI annotation file if present (terravision.ai.yml).
        # Detected before the user file so the .yml suffix check below
        # doesn't accidentally match it.
        if file.lower().endswith("terravision.ai.yml"):
            full_filepath = Path(source_location).joinpath(file)
            with open(full_filepath, "r") as fh:
                click.echo(f"  Detected AI annotation file : {fh.name} \n")
                ai_annotations = yaml.safe_load(fh) or dict()
            continue

        # Load user annotation YAML files if present
        if (
            file.lower().endswith("terravision.yml")
            or file.lower().endswith("architecture.yaml")
            and not yaml_detected
        ):
            full_filepath = Path(source_location).joinpath(file)
            with open(full_filepath, "r") as file:
                click.echo(f"  Detected architecture annotation file : {file.name} \n")
                yaml_detected = True
                annotations = yaml.safe_load(file)

    # Recursively search subdirectories if requested
    if recursive:
        for root, dir, files in os.walk(source_location):
            for d in dir:
                subdir = os.path.join(root, d)
                for file in os.listdir(subdir):
                    if file.lower().endswith(".tf") or file.lower().endswith(
                        "auto.tfvars"
                    ):
                        paths.append(os.path.join(subdir, file))

    # Validate that files were found
    if len(paths) == 0:
        click.echo(
            "ERROR: No Terraform .tf files found in current directory or your "
            "source location. Use --source parameter to specify directory or "
            "Github URL of source files"
        )
        exit()

    return paths


def handle_module(
    modules_list: List[Dict[str, Any]], tf_file_paths: List[str], filename: str
) -> Dict[str, Any]:
    """Process module declarations and map them to source locations.

    Creates a mapping between module names and their source directories,
    handling both local paths and remote module sources.

    Args:
        modules_list: List of module declaration dictionaries from HCL
        tf_file_paths: List of Terraform file paths
        filename: Source file containing the module declarations

    Returns:
        Dictionary with 'tf_file_paths' and 'module_source_dict' keys
    """
    temp_modules_dir = temp_dir.name
    module_source_dict: Dict[str, Dict[str, str]] = dict()

    # Map each module to its source location
    for i in range(len(modules_list)):
        module_stanza = modules_list[i]
        key = next(iter(module_stanza))
        module_source = module_stanza[key]["source"]

        # Handle remote vs local module sources
        if not module_source.startswith(".") and not module_source.startswith("\\"):
            # Remote module: create cache path
            localfolder = module_source.replace("/", "_")
            cache_path = str(
                os.path.join(temp_modules_dir, ";" + key + ";" + localfolder)
            )
            module_source_dict[key] = {
                "cache_path": str(cache_path),
                "source_file": filename,
            }
        else:
            # Local module: use source path directly
            module_source_dict[key] = {
                "cache_path": module_source,
                "source_file": filename,
            }

    return {"tf_file_paths": tf_file_paths, "module_source_dict": module_source_dict}


def iterative_parse(
    tf_file_paths: List[str],
    hcl_dict: Dict[str, Any],
    extract_sections: List[str],
    tfdata: Dict[str, Any],
    tf_mod_dir: str,
    source_dir: str = "",
) -> Dict[str, Any]:
    """Parse Terraform files and extract resources, modules, and variables.

    Iteratively processes each Terraform file, parsing HCL2 syntax and extracting
    specified sections. Handles parsing errors and discovers nested modules.

    Args:
        tf_file_paths: List of Terraform file paths to parse
        hcl_dict: Dictionary to store parsed HCL content
        extract_sections: List of section names to extract (e.g., 'resource', 'module')
        tfdata: Main data dictionary to populate with parsed content
        tf_mod_dir: Directory containing Terraform modules
        source_dir: Root source directory (for .terraform/modules/modules.json lookup)

    Returns:
        Updated tfdata dictionary with parsed content
    """
    tfdata["module_source_dict"] = dict()

    # Load Terraform's modules.json for local module resolution (issue #168)
    # Check terraform init working directory first (temp dir where init ran),
    # then fall back to source_dir
    init_dir = tfdata.get("terraform_init_dir", "")
    terraform_modules = _load_terraform_modules_json(init_dir) if init_dir else {}
    if not terraform_modules:
        terraform_modules = (
            _load_terraform_modules_json(source_dir) if source_dir else {}
        )
    if terraform_modules:
        click.echo(
            f"  Found .terraform/modules/modules.json with "
            f"{len(terraform_modules)} module(s)"
        )

    # Parse each Terraform file
    for filename in tf_file_paths:
        filepath = Path(filename)
        fname = filepath.parent.name + "/" + filepath.name
        click.echo(f"  Parsing {filename}")

        # Read the raw text once so we can both parse it as HCL AND
        # harvest line comments out of it. python-hcl2 strips comments
        # during parsing, so the only way to surface human documentation
        # to downstream consumers (the AI annotation context block in
        # particular) is to scan the raw source ourselves before handing
        # it to the parser.
        try:
            with click.open_file(filename, "r", encoding="utf8") as f:
                raw_content = f.read()
        except OSError as read_err:
            print("Could not read Terraform file:", filename, read_err)
            continue

        per_resource, unattached = _extract_comments_from_tf(raw_content)
        if per_resource:
            for key, comment in per_resource.items():
                tf_comments.setdefault(key, comment)
        if unattached:
            tf_unattached_comments.extend(unattached)

        # Attempt to parse HCL2 content
        try:
            hcl_dict[filename] = hcl2.load(io.StringIO(raw_content))
        except Exception:
            # Retry with preprocessed content to fix known parser limitations
            try:
                preprocessed = _preprocess_hcl(raw_content)
                hcl_dict[filename] = hcl2.load(io.StringIO(preprocessed))
            except Exception as error:
                print("A Terraform HCL parsing error occurred:", filename, error)
                continue

        # Extract specified sections from parsed HCL
        for section in extract_sections:
            if section in hcl_dict[filename]:
                section_name = "all_" + section
                if section_name not in tfdata.keys():
                    tfdata[section_name] = {}
                tfdata[section_name][filename] = hcl_dict[filename][section]
                click.echo(
                    click.style(
                        f"    Found {len(hcl_dict[filename][section])} {section} stanza(s)",
                        fg="green",
                    )
                )

                # Discover and process nested modules
                if section == "module":
                    for mod_dict in hcl_dict[filename]["module"]:
                        module_name = next(iter(mod_dict))
                        modpath = os.path.join(tf_mod_dir, module_name)
                        sourcemod = mod_dict[module_name]["source"]
                        version_constraint = mod_dict[module_name].get("version", "")

                        # Handle relative module paths
                        if sourcemod.startswith("."):
                            curdir = os.getcwd()
                            os.chdir(os.path.dirname(filename))
                            modpath = os.path.abspath(sourcemod)
                            os.chdir(curdir)

                        # Fallback to source if module directory doesn't exist
                        if not os.path.isdir(modpath):
                            modpath = mod_dict[module_name]["source"]

                        # Recursively find files in module directory
                        source_files_list = find_tf_files(
                            modpath,
                            [],
                            module_name,
                            version=version_constraint,
                            terraform_modules=terraform_modules,
                        )
                        existing_files = list(tf_file_paths)
                        tf_file_paths.extend(
                            x for x in source_files_list if x not in existing_files
                        )
                        # Store source path for downstream module matching.
                        # Local modules use the resolved absolute path (matches
                        # file paths for resource-to-module association).
                        # Remote modules store the source string (preserves
                        # existing behavior where plan/graph data provides
                        # module prefixes).
                        if sourcemod.startswith("."):
                            tfdata["module_source_dict"][module_name] = str(modpath)
                        else:
                            tfdata["module_source_dict"][module_name] = sourcemod

    # Handle duplicate module references
    oldpath: List[str] = []
    for module, modpath in tfdata["module_source_dict"].items():
        if modpath in oldpath:
            # Module called multiple times - duplicate resources
            duplicate = modpath
            for filepath, res_list in tfdata["all_resource"].items():
                if duplicate in filepath:
                    tfdata["all_resource"][filepath].append(
                        tfdata["all_resource"][filepath][0]
                    )
        else:
            oldpath.append(modpath)

    return tfdata


def read_tfsource(
    source_list: Tuple[str, ...],
    varfile_list: Tuple[str, ...],
    annotate: str,
    tfdata: Dict[str, Any],
) -> Dict[str, Any]:
    """Parse all Terraform files from source locations.

    Main entry point for parsing Terraform source files. Discovers and parses
    .tf files, loads variable files, and processes annotation files.

    Args:
        source_list: Tuple of source directory paths or Git URLs
        varfile_list: Tuple of variable file paths (.tfvars)
        annotate: Path to annotation YAML file (optional)
        tfdata: Dictionary to populate with parsed data

    Returns:
        Updated tfdata dictionary containing all parsed Terraform data
    """
    global annotations
    global ai_annotations
    global tf_comments
    global tf_unattached_comments

    # Reset the comment buckets at the start of each parse run so a
    # second invocation in the same Python process doesn't ship stale
    # comments from a previous source. The annotation globals are
    # intentionally NOT reset (existing behaviour for backwards compat).
    tf_comments = dict()
    tf_unattached_comments = list()

    click.echo(click.style("\nParsing Terraform Source Files..", fg="white", bold=True))

    # Also discover terravision.ai.yml in the current working directory
    # (the spec places the AI file next to the rendered diagram, not in the
    # source dir). Source-dir discovery still happens inside find_tf_files.
    cwd_ai_path = Path.cwd() / "terravision.ai.yml"
    if cwd_ai_path.is_file():
        try:
            with open(cwd_ai_path, "r") as fh:
                click.echo(f"  Detected AI annotation file : {cwd_ai_path} \n")
                ai_annotations = yaml.safe_load(fh) or dict()
        except (OSError, yaml.YAMLError) as exc:
            click.echo(
                click.style(
                    f"  WARNING: Could not read {cwd_ai_path}: {exc}",
                    fg="yellow",
                )
            )
    hcl_dict: Dict[str, Any] = dict()
    # Normalize varfile_list to a list (callers may pass tuple or list)
    varfile_list = list(varfile_list)

    # Parse each source location
    for source in source_list:
        tf_file_paths = find_tf_files(source, paths=[], recursive=False)
        tf_mod_dir = os.path.join(Path.home(), ".terraform", "modules")

        # Load custom annotation file if provided
        if annotate:
            with open(annotate, "r") as file:
                click.echo(f"  Will use architecture annotation file : {file.name} \n")
                annotations = yaml.safe_load(file)

        # Resolve source directory for .terraform/modules/modules.json lookup
        # When source is a URL, derive the directory from the cloned .tf file paths
        if os.path.isdir(source):
            source_dir = source
        elif tf_file_paths:
            source_dir = os.path.dirname(tf_file_paths[0])
        else:
            source_dir = ""
        tfdata = iterative_parse(
            tf_file_paths, hcl_dict, EXTRACT, tfdata, tf_mod_dir, source_dir
        )

    # Auto-detect and load .tfvars files
    for file in tf_file_paths:
        if "auto.tfvars" in file or "terraform.tfvars" in file:
            click.echo(f"  Will use auto variables from file : {file} \n")
            varfile_list = varfile_list + [file]

    # Use all variable files if none specified
    if len(varfile_list) == 0 and tfdata.get("all_variable"):
        varfile_list = list(tfdata["all_variable"].keys())

    tfdata["varfile_list"] = varfile_list
    tfdata["tempdir"] = temp_dir
    tfdata["annotations"] = annotations
    tfdata["ai_annotations"] = ai_annotations
    tfdata["tf_comments"] = tf_comments
    tfdata["tf_unattached_comments"] = tf_unattached_comments

    return tfdata


def _preprocess_hcl(content: str) -> str:
    """Preprocess HCL content to work around python-hcl2 parser limitations.

    Joins continuation lines that start with && or || operators back onto the
    previous line, since the lark-based parser cannot handle these operators
    at the start of a new line.
    """
    return re.sub(r"\n(\s*)(&&|\|\|)", r" \2", content)


def clean_file(filename: str, tempdir: str):
    """Clean problematic characters from Terraform files.

    Attempts to fix HCL parsing errors by removing or escaping problematic
    characters and syntax that may cause parsing failures.

    Args:
        filename: Path to the Terraform file to clean
        tempdir: Temporary directory to write cleaned file

    Returns:
        File handle to the cleaned temporary file
    """
    filepath = str(Path(tempdir, "cleaning.tmp"))
    f_tmp = click.open_file(filepath, "w")

    with fileinput.FileInput(filename, inplace=False) as file:
        for line in file:
            # Skip comment lines
            if line.strip().startswith("#"):
                continue

            # Check for problematic characters
            if (
                '", "' in line
                or ":" in line
                or "*" in line
                or "?" in line
                or "[" in line
                or '("' in line
                or "==" in line
                or "]" in line
            ):
                # Clean AWS resource references with special characters
                if "aws_" in line and "resource" not in line:
                    array = line.split("=")
                    if len(array) > 1:
                        badstring = array[1]
                    else:
                        badstring = line
                    # Remove non-alphanumeric characters except dots and underscores
                    cleaned_string = re.sub("[^0-9a-zA-Z._]+", " ", badstring)
                    line = array[0] + ' = "' + cleaned_string + '"'
                else:
                    # Comment out problematic lines
                    line = f"# {line}" + "\r"

            f_tmp.write(line)

    # Reopen file for reading
    f_tmp = click.open_file(filepath, "r")
    return f_tmp
