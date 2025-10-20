from hmac import new
from multiprocessing import process
import modules.helpers as helpers
import hcl2
import click
import re
from pathlib import Path

# "data.aws_availability_zones": ["AZ1", "AZ2", "AZ3"],
DATA_REPLACEMENTS = {
    "data.aws_availability_zones_names": ["us-east-1a", "us-east-1b", "us-east-1c"],
    "data.aws_subnet_ids": ["subnet-a", "subnet-b", "subnet-c"],
    "data.aws_vpc_ids": ["vpc-a", "vpc-b", "vpc-c"],
    "data.aws_security_group_ids": ["sg-a", "sg-b", "sg-c"],
}


def resolve_all_variables(tfdata, debug: bool, already_processed: bool) -> dict:
    # Load default variable values and user variable values
    tfdata = get_variable_values(tfdata, already_processed)
    # Create view of locals by module
    tfdata = extract_locals(tfdata)
    # Create metadata view from nested TF file resource attributes
    tfdata = get_metadata(tfdata)
    # Replace metadata (resource attributes) variables and locals with actual values
    tfdata = handle_metadata_vars(tfdata)
    # Inject parent module variables that are referenced downstream in sub modules
    if "all_module" in tfdata.keys():
        tfdata = inject_module_variables(tfdata)
    # Dump out findings after file scans are complete
    if debug:
        helpers.output_log(tfdata)
    return tfdata


def handle_module_vars(eval_string, tfdata):
    outvalue = ""
    splitlist = eval_string.split(".")
    outputname = helpers.find_between(eval_string, splitlist[1] + ".", " ")
    mod = helpers.find_between(eval_string, splitlist[0] + ".", ".")
    for file in tfdata["all_output"].keys():
        for i in tfdata["all_output"][file]:
            if outputname in i.keys() and mod in file:
                outvalue = i[outputname]["value"]
                if "*.id" in outvalue and "*.id" in eval_string:
                    outvalue = tfdata["meta_data"][outvalue]["count"]
                    break
                if "*.id" in outvalue and "[" in eval_string and "]" in eval_string:
                    # Specific number of array being used
                    index = int(
                        helpers.find_between(eval_string, "[", "]").replace(" ", "")
                    )
                    outvalue = f"module.{mod}.{helpers.strip_var_curlies(outvalue).replace('.*.id', '').strip()}[{index}]"
                    break
    stringarray = eval_string.split(".")
    if len(stringarray) >= 3:
        modulevar = "module" + "." + stringarray[1] + "." + stringarray[2]
        modulevar = modulevar.strip()
        eval_string = helpers.cleanup_curlies(eval_string.replace(modulevar, outvalue))
    return eval_string


def inject_module_variables(tfdata: dict):
    for file, module_list in tfdata["all_module"].items():
        for module_items in module_list:
            for module, params in module_items.items():
                module_source = params["source"]
                for key, value in params.items():
                    if "module." in str(value) and key != "depends_on":
                        value = handle_module_vars(str(value), tfdata)
                    if "var." in str(value):
                        if isinstance(value, list):
                            for i in range(len(value)):
                                value[i] = helpers.replace_variables(
                                    value[i],
                                    module_source,
                                    tfdata["variable_map"]["main"],
                                    False,
                                )
                        else:
                            value = helpers.replace_variables(
                                value,
                                module_source,
                                tfdata["variable_map"]["main"],
                                False,
                            )
                    # Add var value to master list of all variables so it can be used downstream
                    if (
                        key != "source" and key != "version"
                    ):  # and key in all_variables.keys():
                        tfdata["variable_map"][module][key] = value
    return tfdata


def handle_metadata_vars(tfdata):
    for resource, attr_list in tfdata["meta_data"].items():
        for key, orig_value in attr_list.items():
            value = str(orig_value)
            # TODO: Use Regex to check that preceding character is a space or operand
            while (
                (
                    "var." in value
                    or "local." in value
                    or "data." in value
                    or (
                        "module." in value
                        and "aws_" not in value
                        and "UNKNOWN" not in value
                    )
                )
                and key != "depends_on"
                and key != "original_count"
            ):
                mod = attr_list["module"]
                value = find_replace_values(value, mod, tfdata)
            tfdata["meta_data"][resource][key] = value
    return tfdata


def replace_data_values(found_list: list, value: str, tfdata: dict):
    initial_value = value
    for d in found_list:
        for search_string, keyvalue in DATA_REPLACEMENTS.items():
            if search_string in d:
                if (
                    initial_value.startswith("${data.")
                    and len(found_list) == 1
                    and not isinstance(keyvalue, str)
                ):
                    value = keyvalue
                else:
                    value = str(value.replace(d, str(keyvalue)))

        if value == initial_value:
            value = str(value.replace(d, '"UNKNOWN"'))
    return value


def replace_local_values(found_list: list, value, module, tfdata):
    for localitem in found_list:
        lookup = helpers.cleanup(localitem.split("local.")[1])
        if tfdata["all_locals"]:
            if (
                module in tfdata["all_locals"]
                and lookup in tfdata["all_locals"][module].keys()
            ):
                replacement_value = tfdata["all_locals"][module].get(lookup)
                # value = value.replace(localitem, str(replacement_value))
                value = helpers.find_replace(localitem, str(replacement_value), value)
            else:
                if tfdata["all_locals"].get("main"):
                    if lookup in tfdata["all_locals"]["main"].keys():
                        replacement_value = tfdata["all_locals"]["main"].get(lookup)
                        # value = value.replace(localitem, str(replacement_value))
                        value = helpers.find_replace(
                            localitem, str(replacement_value), value
                        )
                    else:
                        value = value.replace(localitem, "None")
                        click.echo(
                            f"   WARNING: Cannot resolve {localitem}, assigning empty value in module {module}"
                        )
        else:
            # value = value.replace(localitem, "None")
            value = helpers.find_replace(localitem, "None", value)
            click.echo(f"    ERROR: Cannot find definition for local var {localitem}")
            exit()
    return value


def replace_module_vars(found_list: list, value: str, module: str, tfdata: dict):
    for module_var in found_list:
        if "module." in value:
            cleantext = module_var
            splitlist = cleantext.split(".")
            outputname = helpers.find_between(cleantext, splitlist[1] + ".", " ")
            oldvalue = value
            mod = value.split("module.")[1].split(".")[0]
            for ofile in tfdata["all_output"].keys():
                if "modules" and f";{mod};" in ofile:
                    # We have found the right output file
                    for i in tfdata["all_output"][ofile]:
                        if outputname in i.keys():
                            # Resolve module var to output
                            value = value.replace(module_var, i[outputname]["value"])
                            if (
                                "module." in i[outputname]["value"]
                                or "var." in i[outputname]["value"]
                                or "local." in i[outputname]["value"]
                            ):
                                # Output refers to other variables so need to rescursively resolve
                                value = find_replace_values(value, mod, tfdata)
                else:
                    continue
            if value == oldvalue:
                value = value.replace(module_var, '"UNKNOWN"')
                click.echo(
                    f"   WARNING: Cannot resolve {module_var}, assigning empty value in module {module}"
                )
            value = oldvalue.replace(
                outputname, helpers.strip_var_curlies(value)
            ).replace('"', "")
            value = value.replace(" ", "")
            if "[" in value and "*.id" in value:
                value = (value.replace(".*.id", "")).strip()
    return value


def replace_var_values(
    found_list: list, varobject_found_list: list, value: str, module: str, tfdata: dict
):
    for varitem in found_list:
        varitem_lower = varitem.lower()
        lookup = (
            varitem_lower.split("var.")[1]
            .lower()
            .replace("}", "")
            .replace(" ", "")
            .replace(".", "")
        )
        if not module:
            module = "main"
        if (lookup in tfdata["variable_map"][module].keys()) and (
            "var." + lookup not in str(tfdata["variable_map"][module][lookup])
        ):
            # Possible object type var encountered
            obj = ""
            for item in varobject_found_list:
                if lookup in item:
                    obj = tfdata["variable_map"][module][lookup]
                    varitem = item
            if value.count(lookup) < 2 and obj != "" and isinstance(obj, dict):
                key = varitem.split(".")[2]
                if key in obj.keys():
                    keyvalue = obj[key]
                else:
                    keyvalue = obj
                if (
                    isinstance(keyvalue, str)
                    and not keyvalue.startswith("[")
                    and not keyvalue.startswith("{")
                ):
                    keyvalue = f'"{keyvalue}"'
                value = value.replace(varitem, str(keyvalue), 1)
                # value = helpers.find_replace(varitem, str(keyvalue, value))
            elif value.count(lookup) < 2 and obj == "":
                replacement_value = str(tfdata["variable_map"][module].get(lookup))
                if (
                    isinstance(replacement_value, str)
                    and '"' not in replacement_value
                    and not replacement_value.startswith("[")
                ):
                    replacement_value = f'"{replacement_value}"'
                value = value.replace(varitem, replacement_value, 1)
                # value = helpers.find_replace(varitem, replacement_value, value)
            else:
                value = value.replace(
                    varitem, str(tfdata["variable_map"][module][lookup]) + " ", 1
                )
        elif lookup in tfdata["variable_map"][module].keys():
            if "var." in tfdata["variable_map"][module].get(lookup):
                # value = value.replace(varitem, '"UNKNOWN"',1)
                value = helpers.find_replace(varitem, '"UNKNOWN"', value)
            else:
                value = value.replace(
                    varitem, str(tfdata["variable_map"][module].get(lookup), 1)
                )
            break
        elif helpers.list_of_parents(tfdata["variable_map"], lookup):
            module_list = helpers.list_of_parents(tfdata["variable_map"], lookup)
            module_name = module_list[0]
            value = value.replace(
                varitem, str(tfdata["variable_map"][module_name].get(lookup)), 1
            )
            break
        else:
            if lookup.lower() in tfdata["variable_list"]:
                value = tfdata["variable_list"][lookup.lower()]
            if not value:
                click.echo(
                    click.style(
                        f"\nWARNING: No variable value supplied for {varitem} but it is referenced in module {module} ",
                        fg="white",
                        bold=True,
                    )
                )
                click.echo(
                    "Consider passing a valid Terraform .tfvars variable file with the --varfile parameter\n"
                )
                exit()
    return value


def find_replace_values(varstring, module, tfdata):
    # Regex string matching to create lists of different variable markers found
    value = helpers.strip_var_curlies(str(varstring))
    var_found_list = re.findall("var\.[A-Za-z0-9_\-]+", value)
    data_found_list = re.findall("data\.[A-Za-z0-9_\-\.\[\]]+", value)
    varobject_found_list = re.findall("var\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", value)
    local_found_list = re.findall("local\.[A-Za-z0-9_\-\.\[\]]+", value)
    modulevar_found_list = re.findall("module\.[A-Za-z0-9_\-\.\[\]]+", value)
    # Replace found variable strings with variable values
    value = replace_data_values(data_found_list, value, tfdata)
    value = replace_module_vars(modulevar_found_list, value, module, tfdata)
    value = replace_var_values(
        var_found_list, varobject_found_list, value, module, tfdata
    )
    value = replace_local_values(local_found_list, value, module, tfdata)
    return value


def extract_locals(tfdata):
    module_locals = dict()
    # Remove array layer of locals dict structure and copy over to final_locals dict first
    if not tfdata.get("all_locals"):
        tfdata["all_locals"] = {}
        return tfdata
    for file, localvarlist in tfdata["all_locals"].items():
        if ";" in file:
            modname = file.split(";")[1]
        else:
            modname = "main"
        for local in localvarlist:
            if module_locals.get(modname):
                module_locals[modname] = {**module_locals[modname], **local}
            else:
                module_locals[modname] = local
    tfdata["all_locals"] = module_locals
    return tfdata


def prefix_module_names(tfdata):
    # List to hold unique resources that have been processed (needed when modules called more than once)
    processed_list = []
    # Loop through each resource in tfdata["all_resource"]
    for file, resourcelist in dict(tfdata["all_resource"]).items():
        # Loop through each module in tfdata["module_source_dict"]
        for module_name, module_path in tfdata["module_source_dict"].items():
            if module_path in file:
                # We have a resource created within a module, so add the .module prefix to all the resource names
                for index, elementdict in enumerate(resourcelist):
                    for resource_type, value in elementdict.items():
                        for resource_name in value:
                            renamed_resource_name = (
                                f"module.{module_name}.{resource_type}.{resource_name}"
                            )
                            if (
                                "module." not in resource_name
                                and renamed_resource_name not in processed_list
                            ):

                                new_dict = dict(
                                    tfdata["all_resource"][file][index][resource_type]
                                )
                                new_dict.update(
                                    {renamed_resource_name: value[resource_name]}
                                )
                                del new_dict[resource_name]
                                tfdata["all_resource"][file][index] = {
                                    resource_type: new_dict
                                }
                                processed_list.append(renamed_resource_name)
                            else:
                                break
    return tfdata


def show_error(mod, resource, eval_string, exp, tfdata):
    click.echo(
        f"    ERROR: {mod} : {resource} count = 0 (Error in calling function {exp}))"
    )
    tfdata["meta_data"][resource]["count"] = 0
    tfdata["meta_data"][resource]["ERROR_count"] = eval_string
    return tfdata


# Adds additional metadata
def handle_implied_resources(item, resource_type, resource_name, tfdata, meta_data):
    # Check if Cloudwatch is present in policies and create node for Cloudwatch service if found
    if resource_type == "aws_iam_policy":
        if "logs:" in item[resource_type][resource_name]["policy"][0]:
            if not "aws_cloudwatch_log_group.logs" in tfdata["node_list"]:
                tfdata["node_list"].append("aws_cloudwatch_log_group.logs")
                tfdata["graphdict"]["aws_cloudwatch_log_group.logs"] = []
            meta_data["aws_cloudwatch_log_group.logs"] = item[resource_type][
                resource_name
            ]
    return meta_data, tfdata


def handle_numbered_nodes(resource_node, tfdata, meta_data):
    # Determine count by number of objects created by Terraform
    all_matching_list = helpers.find_all_resources_containing(
        tfdata["node_list"], resource_node.split("[")[0] + "["
    )
    resource_count = len(all_matching_list)
    for actual_name in all_matching_list:
        meta_data[actual_name] = meta_data[resource_node]
        meta_data[actual_name]["count"] = resource_count
    return meta_data


def find_actual_resource(
    node_list: list, resource: str, resource_type: str, mod: str, tfdata: dict
) -> str:
    # If we have a singleton resource already in the nodelist no need to search further
    if resource in node_list:
        return resource
    else:
        # search for possible candidate nodes with number bracket
        search = f"{resource}["
        all_candidates = helpers.find_all_resources_containing(node_list, search)
        if all_candidates:
            return all_candidates[0]
        else:
            # possible name mutation so find closest resource
            if not resource in tfdata["original_metadata"].keys():
                resource = helpers.list_of_dictkeys_containing(
                    tfdata["original_metadata"],
                    f"module.{mod}.{resource_type}.",
                )
                if resource:
                    return resource[0]
                else:
                    return False


def get_metadata(tfdata):  # -> set
    """
    Extract resource attributes from resources by looping through each resource in each file.
    Returns a set with a node_list of unique resources, and dict of resource attributes (metadata)
    """
    meta_data = dict()
    # Create list of node names that will be created
    tfdata["node_list"] = list(dict.fromkeys(tfdata["graphdict"]))
    # Default module is assumed main unless over-ridden
    mod = "main"
    click.echo(click.style(f"\nProcessing resources..", fg="white", bold=True))
    if not tfdata.get("all_resource"):
        click.echo(
            click.style(
                f"\nWARNING: Unable to find any resources ", fg="red", bold=True
            )
        )
        tfdata["all_resource"] = dict()
    else:
        for filename, resource_list in tfdata["all_resource"].items():
            if ";" in filename:
                mod = filename.split(";")[1]
            # Source code doesn't have final resource names so we need to match them up to right metadata records
            for item in resource_list:
                for resource_type in item.keys():
                    for resource_name in item[resource_type]:
                        if resource_name.startswith("module."):
                            resource_node = resource_name
                        else:
                            resource_node = f"{resource_type}.{resource_name}"

                        meta_data, tfdata = handle_implied_resources(
                            item, resource_type, resource_name, tfdata, meta_data
                        )
                    click.echo(f"   {resource_node}")
                    found_node = find_actual_resource(
                        tfdata["node_list"], resource_node, resource_type, mod, tfdata
                    )
                    if not found_node:
                        break  # not a created resource
                    else:
                        # Store original metadata from tf
                        omd = dict(tfdata["original_metadata"][found_node])
                        # Get metadata as specified in source files
                        md = item[resource_type][resource_name]
                        # Capture original count value string
                        if md.get("count"):
                            md["original_count"] = str(md["count"])
                        # Over-ride original metadata params where present
                        omd.update(md)
                        meta_data[resource_node] = omd
                        meta_data[resource_node]["module"] = mod
                        meta_data[found_node] = omd
                        meta_data[found_node]["module"] = mod
                        # Check if numbered node exists in metadata
                        if "~" in found_node:
                            meta_data = handle_numbered_nodes(
                                found_node, tfdata, meta_data
                            )
    tfdata["meta_data"] = meta_data
    return tfdata


def get_metadata_old(tfdata):  # -> set
    """
    Extract resource attributes from resources by looping through each resource in each file.
    Returns a set with a node_list of unique resources, resource attributes (metadata)
    """
    meta_data = dict()
    tfdata["node_list"] = list(dict.fromkeys(tfdata["graphdict"]))
    # Default module is assumed main unless over-ridden
    mod = "main"
    click.echo(
        click.style(
            f"\nProcessing resources..",
            fg="white",
            bold=True,
        )
    )
    if not tfdata.get("all_resource"):
        click.echo(
            click.style(
                f"\nWARNING: Unable to find any resources ",
                fg="red",
                bold=True,
            )
        )
        tfdata["all_resource"] = dict()
    for filename, resource_list in tfdata["all_resource"].items():
        if ";" in filename:
            mod = filename.split(";")[1]
        for item in resource_list:
            for resource_type in item.keys():
                for resource_name in item[resource_type]:
                    # Check if Cloudwatch is present in policies and create node for Cloudwatch service if found
                    if resource_type == "aws_iam_policy":
                        if "logs:" in item[resource_type][resource_name]["policy"][0]:
                            if (
                                not "aws_cloudwatch_log_group.logs"
                                in tfdata["node_list"]
                            ):
                                tfdata["node_list"].append(
                                    "aws_cloudwatch_log_group.logs"
                                )
                            meta_data["aws_cloudwatch_log_group.logs"] = item[
                                resource_type
                            ][resource_name]
                if "module." in resource_name:
                    mod = resource_name.split(".")[1]
                    resource_node = resource_name
                else:
                    resource_node = f"{resource_type}.{resource_name}"
                click.echo(f"   {resource_node}")
                # Check if numbered node exists in metadata
                if not resource_node in tfdata["original_metadata"].keys():
                    # TODO: check if there is a count attribute as well here before renaming
                    if "[0]~1" not in resource_node:
                        resource_node = f"{resource_node}[0]~1"
                    # Sometimes resource names get mutated due to dynamic stanzas so just guess the resource name by type
                    if not resource_node in tfdata["original_metadata"].keys():
                        resource_node = helpers.list_of_dictkeys_containing(
                            tfdata["original_metadata"],
                            f"module.{mod}.{resource_type}.",
                        )
                        if not resource_node:
                            break  # resource would not be created so ignore
                        else:
                            resource_node = resource_node[0]
                omd = dict(tfdata["original_metadata"][resource_node])
                md = item[resource_type][resource_name]
                omd.update(md)
                md = omd
                # Capture original count value string
                if md.get("count"):
                    md["original_count"] = str(md["count"])
                if helpers.find_resource_containing(tfdata["node_list"], resource_node):
                    matching_node = helpers.find_resource_containing(
                        tfdata["node_list"], resource_node
                    )
                    meta_data[resource_node] = md
                    meta_data[resource_node]["module"] = mod
                    if md.get("count") and tfdata["original_metadata"][
                        matching_node
                    ].get("count"):
                        meta_data[resource_node]["count"] = int(
                            tfdata["original_metadata"][matching_node]["count"]
                        )
                    elif md.get("count"):
                        meta_data[resource_node]["count"] = 1
                if (
                    f"{resource_node}~1" in tfdata["node_list"]
                    and tfdata["original_metadata"][f"{resource_node}~1"]["count"] > 1
                ):
                    for i in range(
                        1,
                        tfdata["original_metadata"][f"{resource_node}~1"]["count"] + 1,
                    ):
                        meta_data[resource_node] = md
                        meta_data[f"{resource_node}~{i}"] = md
                        meta_data[f"{resource_node}~{i}"]["module"] = mod
                        meta_data[f"{resource_node}~{i}"]["count"] = int(
                            tfdata["original_metadata"][f"{resource_node}~1"]["count"]
                        )
                        meta_data[resource_node]["count"] = int(
                            tfdata["original_metadata"][f"{resource_node}~1"]["count"]
                        )
    tfdata["meta_data"] = meta_data
    return tfdata


def get_variable_values(tfdata, already_processed: bool) -> dict:
    """Returns a list of all variables from local .tfvar defaults, supplied varfiles and module var values"""
    click.echo(
        click.style(
            f"\nProcessing variables..",
            fg="white",
            bold=True,
        )
    )
    if not tfdata.get("all_variable"):
        tfdata["all_variable"] = dict()
    var_data = dict()
    var_mappings = dict()
    matching = list()
    # Load default values from all existing files in source locations
    for var_source_file, var_list in tfdata["all_variable"].items():
        var_source_dir = str(Path(var_source_file).parent)
        for item in var_list:
            for k in item.keys():
                var_name = k
                # Populate dict with default values first
                if "default" in item[k]:
                    var_value = item[k]["default"]
                    if isinstance(var_value, str):
                        var_value = f'"{var_value}"'
                else:
                    var_value = ""
                var_data[var_name.lower()] = var_value
                # Also update var mapping dict with modules and matching variables
                if tfdata.get("module_source_dict"):
                    matching = [
                        m
                        for m in tfdata["module_source_dict"]
                        if tfdata["module_source_dict"][m] in str(var_source_file)
                    ]  # omit first char of module source in case it is a .
                if not matching:
                    if not var_mappings.get("main"):
                        var_mappings["main"] = {}
                        var_mappings["main"] = {"source_dir": var_source_dir}
                    var_mappings["main"][var_name] = var_value
                for mod in matching:
                    if not var_mappings.get(mod):
                        var_mappings[mod] = {}
                        var_mappings[mod]["source_dir"] = var_source_dir
                    var_mappings[mod][var_name.lower()] = var_value
    if tfdata.get("module_source_dict"):
        # Insert module parameters as variable names
        for file, modulelist in tfdata["all_module"].items():
            for module in modulelist:
                for mod, params in module.items():
                    for variable in params:
                        var_data[variable] = params[variable]
                        if not var_mappings.get(mod):
                            var_mappings[mod] = {}
                        var_mappings[mod][variable] = params[variable]
    if tfdata.get("all_variable") and not already_processed:
        # Over-write defaults with passed varfile specified values
        for varfile in tfdata["varfile_list"]:
            # Open supplied varfile for reading
            with click.open_file(varfile, encoding="utf8", mode="r") as f:
                variable_values = hcl2.load(f)
            for uservar in variable_values:
                var_data[uservar.lower()] = variable_values[uservar]
                if not var_mappings.get("main"):
                    var_mappings["main"] = {}
                var_mappings["main"][uservar.lower()] = variable_values[uservar]
    tfdata["variable_list"] = var_data
    tfdata["variable_map"] = var_mappings

    return tfdata
