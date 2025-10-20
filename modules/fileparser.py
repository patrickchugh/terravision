import fileinput
import os
import re
import tempfile
from pathlib import Path
from sys import exit
import click
import yaml
import hcl2
import modules.gitlibs as gitlibs


# Create Tempdir and Module Cache Directories
annotations = dict()
start_dir = Path.cwd()
temp_dir = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
MODULE_DIR = str(Path(Path.home(), ".terravision", "module_cache"))
if not os.path.exists(MODULE_DIR):
    os.makedirs(MODULE_DIR)

# List of dictionary sections to extract from TF file
EXTRACT = ["module", "output", "variable", "locals", "resource", "data"]


def walklevel(some_dir, level=1):
    paths = list()
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        if file.lower().endswith(".tf") or file.lower().endswith("auto.tfvars"):
            paths.append(os.path.join(root, file))
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]
    return paths


def find_tf_files(source: str, paths=list(), mod="main", recursive=False) -> list:
    global annotations
    yaml_detected = False
    # If source is a Git address, clone to temp dir
    if not os.path.isdir(source):
        source_location = gitlibs.clone_files(source, temp_dir.name, mod)
    else:
        # Source is a local folder
        source_location = source.strip()
    files = [f for f in os.listdir(source_location)]
    click.echo(f"  Added Source Location: {source}")
    for file in files:
        if (
            file.lower().endswith(".tf")
            or file.lower().endswith("auto.tfvars")
            or "terraform.tfvars" in file
        ):
            paths.append(os.path.join(source_location, file))
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
    if recursive:
        for root, dir, files in os.walk(source_location):
            for d in dir:
                subdir = os.path.join(root, d)
                for file in os.listdir(subdir):
                    if file.lower().endswith(".tf") or file.lower().endswith(
                        "auto.tfvars"
                    ):
                        paths.append(os.path.join(subdir, file))
    if len(paths) == 0:
        click.echo(
            "ERROR: No Terraform .tf files found in current directory or your source location. Use --source parameter to specify location or Github URL of source files"
        )
        exit()
    return paths


def handle_module(modules_list, tf_file_paths, filename):
    temp_modules_dir = temp_dir.name
    module_source_dict = dict()
    # Create a mapping dict between modules and their source dirs for variable separation
    for i in range(len(modules_list)):
        module_stanza = modules_list[i]
        key = next(iter(module_stanza))  # Get first key
        module_source = module_stanza[key]["source"]
        # Convert Source URLs to module cache paths
        if not module_source.startswith(".") and not module_source.startswith("\\"):
            localfolder = module_source.replace("/", "_")
            cache_path = str(
                os.path.join(temp_modules_dir, ";" + key + ";" + localfolder)
            )
            module_source_dict[key] = {
                "cache_path": str(cache_path),
                "source_file": filename,
            }
        else:
            module_source_dict[key] = {
                "cache_path": module_source,
                "source_file": filename,
            }
    return {"tf_file_paths": tf_file_paths, "module_source_dict": module_source_dict}


def iterative_parse(
    tf_file_paths: dict,
    hcl_dict: dict,
    extract_sections: list,
    tfdata: dict,
    tf_mod_dir,
):
    # Parse each TF file encountered in source locations
    tfdata["module_source_dict"] = dict()
    for filename in tf_file_paths:
        filepath = Path(filename)
        fname = filepath.parent.name + "/" + filepath.name
        click.echo(f"  Parsing {filename}")
        with click.open_file(filename, "r", encoding="utf8") as f:
            # with suppress(Exception):
            try:
                hcl_dict[filename] = hcl2.load(f)
            except Exception as error:
                print("A Terraform HCL parsing error occurred:", filename, error)
                continue
            # Handle HCL parsing errors due to unexpected characters
            if not filename in hcl_dict.keys():
                click.echo(
                    f"   WARNING: Unknown Error reading TF file {filename}. Attempting character cleanup fix.."
                )
                with tempfile.TemporaryDirectory(dir=temp_dir.name) as tempclean:
                    f_tmp = clean_file(filename, str(tempclean))
                    hcl_dict[filename] = hcl2.load(f_tmp)
                    if not filename in hcl_dict.keys():
                        click.echo(
                            f"   ERROR: Unknown Error reading TF file {filename}. Aborting!"
                        )
                        exit()
            # Isolate variables, locals and other sections of interest into tfdata dict
            for section in extract_sections:
                if section in hcl_dict[filename]:
                    section_name = "all_" + section
                    if not section_name in tfdata.keys():
                        tfdata[section_name] = {}
                    tfdata[section_name][filename] = hcl_dict[filename][section]
                    click.echo(
                        click.style(
                            f"    Found {len(hcl_dict[filename][section])} {section} stanza(s)",
                            fg="green",
                        )
                    )
                    if section == "module":
                        # Expand source locations to include any newly found sub-module locations
                        for mod_dict in hcl_dict[filename]["module"]:
                            module_name = next(iter(mod_dict))
                            modpath = os.path.join(tf_mod_dir, module_name)
                            sourcemod = mod_dict[module_name]["source"]
                            if sourcemod.startswith("."):
                                curdir = os.getcwd()
                                os.chdir(os.path.dirname(filename))
                                modpath = os.path.abspath(sourcemod)
                                os.chdir(curdir)
                            if not os.path.isdir(modpath):
                                modpath = mod_dict[module_name]["source"]
                            source_files_list = find_tf_files(modpath, [], module_name)
                            existing_files = list(tf_file_paths)
                            tf_file_paths.extend(
                                x for x in source_files_list if x not in existing_files
                            )
                            tfdata["module_source_dict"][module_name] = str(modpath)
    # Look for module files that are called more than once and add to resource list
    oldpath = []
    for module, modpath in tfdata["module_source_dict"].items():
        if modpath in oldpath:
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
    source_list: tuple, varfile_list: tuple, annotate: str, tfdata: dict
):  # -> dict
    global annotations
    """ Parse all .TF extension files in source folder and returns dict with variables and resources found """
    click.echo(click.style("\nParsing Terraform Source Files..", fg="white", bold=True))
    hcl_dict = dict()
    for source in source_list:
        # Get List of Terraform Files to parse
        tf_file_paths = find_tf_files(source, [], False)
        tf_mod_dir = os.path.join(source, ".terraform", "modules")
        if annotate:
            with open(annotate, "r") as file:
                click.echo(f"  Will use architecture annotation file : {file.name} \n")
                annotations = yaml.safe_load(file)
        tfdata = iterative_parse(tf_file_paths, hcl_dict, EXTRACT, tfdata, tf_mod_dir)
    # Auto load any tfvars
    for file in tf_file_paths:
        if "auto.tfvars" in file or "terraform.tfvars" in file:
            click.echo(f"  Will use auto variables from file : {file} \n")
            varfile_list = varfile_list + (file,)
    # Load in variables from user file into a master list
    if len(varfile_list) == 0 and tfdata.get("all_variable"):
        varfile_list = tfdata["all_variable"].keys()
    tfdata["varfile_list"] = list(varfile_list)
    tfdata["tempdir"] = temp_dir
    tfdata["annotations"] = annotations
    return tfdata


def clean_file(filename: str, tempdir: str):
    filepath = str(Path(tempdir, "cleaning.tmp"))
    f_tmp = click.open_file(filepath, "w")
    with fileinput.FileInput(
        filename,
        inplace=False,
    ) as file:
        for line in file:
            if line.strip().startswith("#"):
                continue
            if (
                '", "' in line
                or ":" in line
                or "*" in line
                or "?" in line
                or "[" in line
                or '("' in line
                or "==" in line
                or "?" in line
                or "]" in line
                or ":" in line
            ):
                # if '", "' in line or ':' in line or '*' in line or '?' in line or '[' in line or '("' in line or '==' in line or '?' in line or '${' in line or ']' in line:
                if "aws_" in line and not "resource" in line:
                    array = line.split("=")
                    if len(array) > 1:
                        badstring = array[1]
                    else:
                        badstring = line
                    cleaned_string = re.sub("[^0-9a-zA-Z._]+", " ", badstring)
                    line = array[0] + ' = "' + cleaned_string + '"'
                else:
                    line = f"# {line}" + "\r"
            f_tmp.write(line)
    f_tmp = click.open_file(filepath, "r")
    return f_tmp
