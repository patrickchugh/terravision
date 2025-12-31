"""File parser module for TerraVision.

This module handles parsing of Terraform files (.tf), variable files (.tfvars),
and annotation files (YAML). It discovers files from local directories or Git
repositories, parses HCL2 syntax, and extracts resources, modules, and variables.
"""

import fileinput
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


def find_tf_files(
    source: str,
    paths: Optional[List[str]] = None,
    mod: str = "main",
    recursive: bool = False,
) -> List[str]:
    """Discover Terraform files in local directory or Git repository.

    Searches for .tf files, .tfvars files, and annotation YAML files in the
    specified source location. Handles both local directories and Git URLs.

    Args:
        source: Local directory path or Git repository URL
        paths: Existing list of file paths to append to (default: empty list)
        mod: Module name for organizing cloned repositories (default: 'main')
        recursive: Whether to recursively search subdirectories (default: False)

    Returns:
        List of absolute paths to discovered Terraform files
    """
    global annotations

    if paths is None:
        paths = list()

    yaml_detected = False

    # Clone Git repository or use local directory
    if not os.path.isdir(source):
        source_location = gitlibs.clone_files(source, temp_dir.name, mod)
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

        # Load annotation YAML files if present
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

    Returns:
        Updated tfdata dictionary with parsed content
    """
    tfdata["module_source_dict"] = dict()

    # Parse each Terraform file
    for filename in tf_file_paths:
        filepath = Path(filename)
        fname = filepath.parent.name + "/" + filepath.name
        click.echo(f"  Parsing {filename}")

        # Attempt to parse HCL2 content
        with click.open_file(filename, "r", encoding="utf8") as f:
            try:
                hcl_dict[filename] = hcl2.load(f)
            except Exception as error:
                print("A Terraform HCL parsing error occurred:", filename, error)
                continue

            # Retry with character cleanup if initial parse failed
            if filename not in hcl_dict.keys():
                click.echo(
                    f"   WARNING: Unknown Error reading TF file {filename}. "
                    f"Attempting character cleanup fix.."
                )
                with tempfile.TemporaryDirectory(dir=temp_dir.name) as tempclean:
                    f_tmp = clean_file(filename, str(tempclean))
                    hcl_dict[filename] = hcl2.load(f_tmp)
                    if filename not in hcl_dict.keys():
                        click.echo(
                            f"   ERROR: Unknown Error reading TF file {filename}. "
                            f"Aborting!"
                        )
                        exit()

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
                        source_files_list = find_tf_files(modpath, [], module_name)
                        existing_files = list(tf_file_paths)
                        tf_file_paths.extend(
                            x for x in source_files_list if x not in existing_files
                        )
                        tfdata["module_source_dict"][module_name] = str(modpath)

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

    click.echo(click.style("\nParsing Terraform Source Files..", fg="white", bold=True))
    hcl_dict: Dict[str, Any] = dict()

    # Parse each source location
    for source in source_list:
        tf_file_paths = find_tf_files(source, [], False)
        tf_mod_dir = os.path.join(Path.home(), ".terraform", "modules")

        # Load custom annotation file if provided
        if annotate:
            with open(annotate, "r") as file:
                click.echo(f"  Will use architecture annotation file : {file.name} \n")
                annotations = yaml.safe_load(file)

        tfdata = iterative_parse(tf_file_paths, hcl_dict, EXTRACT, tfdata, tf_mod_dir)

    # Auto-detect and load .tfvars files
    for file in tf_file_paths:
        if "auto.tfvars" in file or "terraform.tfvars" in file:
            click.echo(f"  Will use auto variables from file : {file} \n")
            varfile_list = varfile_list + (file,)

    # Use all variable files if none specified
    if len(varfile_list) == 0 and tfdata.get("all_variable"):
        varfile_list = tuple(tfdata["all_variable"].keys())

    tfdata["varfile_list"] = list(varfile_list)
    tfdata["tempdir"] = temp_dir
    tfdata["annotations"] = annotations

    return tfdata


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
