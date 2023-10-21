import re
from contextlib import suppress
from pathlib import Path
from sys import exit
import click
import hcl2
import modules.helpers as helpers
from modules.helpers import *
from modules.postfix import Conversion, Evaluate

DATA_REPLACEMENTS = {
    "data.aws_availability_zones": ["AZ1", "AZ2", "AZ3"],
    "data.aws_availability_zones_names": ["us-east-1a", "us-east-1b", "us-east-1c"],
    "data.aws_subnet_ids": ["subnet-a", "subnet-b", "subnet-c"],
    "data.aws_vpc_ids": ["vpc-a", "vpc-b", "vpc-c"],
    "data.aws_security_group_ids": ["sg-a", "sg-b", "sg-c"],
}


def inject_module_variables(tfdata: dict):
    for file, module_list in tfdata["all_module"].items():
        for module_items in module_list:
            for module, params in module_items.items():
                module_source = params["source"]
                for key, value in params.items():
                    if "module." in str(value):
                        pass
                    if "var." in str(value):
                        if isinstance(value, list):
                            for i in range(len(value)):
                                value[i] = replace_variables(
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
    # Add quotes for raw strings to aid postfix evaluation
    for module in tfdata["variable_map"]:
        for variable in tfdata["variable_map"][module]:
            value = tfdata["variable_map"][module][variable]
            if (
                isinstance(value, str)
                and "(" not in value
                and "[" not in value
                and not value.startswith('"')
            ):
                tfdata["variable_map"][module][variable] = f'"{value}"'
    return tfdata


def handle_metadata_vars(tfdata):
    for resource, attr_list in tfdata["meta_data"].items():
        for key, orig_value in attr_list.items():
            value = str(orig_value)
            while (
                (
                    "var." in value
                    or "local." in value
                    or "module." in value
                    or "data." in value
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
        lookup = cleanup(localitem.split("local.")[1])
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
                        f"    WARNING: Cannot resolve {localitem}, assigning empty value in module {module}"
                    )
        else:
            # value = value.replace(localitem, "None")
            value = helpers.find_replace(localitem, "None", value)
            click.echo(f"    ERROR: Cannot find definition for local var {localitem}")
            exit()
    return value


def replace_module_vars(found_list: list, value: str, module: str, tfdata: dict):
    for module_var in found_list:
        cleantext = fix_lists(module_var)
        splitlist = cleantext.split(".")
        outputname = find_between(cleantext, splitlist[1] + ".", " ")
        oldvalue = value
        for ofile in tfdata["all_output"].keys():
            for i in tfdata["all_output"][ofile]:
                if outputname in i.keys():
                    value = value.replace(module_var, i[outputname]["value"])
                    for keyword in ["var.", "local.", "module.", "data."]:
                        if keyword in value:
                            if "module." in value:
                                mod = value.split("module.")[1].split(".")[0]
                            else:
                                mod = module
                            value = find_replace_values(value, mod, tfdata)
                    break
        if value == oldvalue:
            value = value.replace(module_var, '"UNKNOWN"')
    return value


def replace_var_values(
    found_list: list, varobject_found_list: list, value: str, module: str, tfdata: dict
):
    for varitem in found_list:
        lookup = (
            varitem.split("var.")[1]
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
            # value = helpers.find_replace(varitem. str(tfdata["variable_map"][module_name].get(lookup)), value)
            break
        else:
            click.echo(
                click.style(
                    f"\nERROR: No variable value supplied for {varitem} but it is referenced in module {module} ",
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


def eval_tf_functions(eval_string):
    # Check if there are any Terraform functions used to compute resources
    function_name = check_for_tf_functions(eval_string)
    # Determine startpos of function parameter
    startpos = eval_string.find(function_name + "(") + len(function_name)
    rhs = eval_string[startpos + 1 : len(eval_string)]
    endpos = rhs.find(")")
    middle = rhs[0:endpos]
    if "(" in middle:
        # We have nested fucnctions
        # get right hand side of statement
        ob = False
        cb = False
        for i in range(len(rhs)):
            if rhs[i] == "(":
                ob = True
            if rhs[i] == ")":
                cb = True
                if ob == True:
                    ob = False
                    cb = False
                else:
                    middle = rhs[0:i]
                    endpos = i
                    break
    func_param = middle
    eval_result = None
    # Call emulated Teraform function to get predicted result
    with suppress(Exception):
        eval_result = str(getattr(tf_function_handlers, function_name)(func_param))
    if not eval_result:
        click.echo(f"    WARNING: Unable to evaluate {function_name}({func_param})")
        eval_result = f"ERROR!_{function_name}(" + func_param + ")"
    eval_string = eval_string.replace(
        f"{function_name}(" + func_param + ")", str(eval_result)
    )
    eval_string = fix_lists(eval_string)
    return eval_string


def find_conditional_statements(resource, attr_list: dict):
    # Handle conditional counts and loops
    if "for_each" in attr_list:
        eval_string = attr_list["for_each"]
        return "ERROR!" + eval_string
    if (
        "count" in attr_list.keys()
        and not isinstance(attr_list["count"], int)
        and not resource.startswith("null_resource")
    ):
        eval_string = str(attr_list["count"])
        return helpers.cleanup_curlies(eval_string)
    for attrib in attr_list:
        if "for" in attrib and ("in" in attrib or ":" in attrib):
            eval_string = attr_list[attrib]
            # we have a for loop so deal with that part first
            # TODO: Implement for loop handling for real, for now just null it out
            eval_string = find_between(
                eval_string, "[for", ":", "[", True, eval_string.count("[")
            )
            eval_string = find_between(
                eval_string, ":", "]", "", True, eval_string.count("]")
            )
            return helpers.cleanup_curlies(eval_string)
    return False


def handle_module_vars(eval_string, tfdata):
    outvalue = ""
    splitlist = eval_string.split(".")
    outputname = find_between(eval_string, splitlist[1] + ".", " ")
    for file in tfdata["all_outputs"].keys():
        for i in tfdata["all_outputs"][file]:
            if outputname in i.keys():
                outvalue = i[outputname]["value"]
                if "*.id" in outvalue:
                    resource_name = fix_lists(outvalue.split(".*")[0])
                    outvalue = tfdata["meta_data"][resource_name]["count"]
                    outvalue = find_conditional_statements(outvalue)
                    break
    stringarray = eval_string.split(".")
    modulevar = cleanup("module" + "." + stringarray[1] + "." + stringarray[2]).strip()
    eval_string = eval_string.replace(modulevar, outvalue)
    return eval_string


def handle_splat_statements(eval_string, tfdata):
    splitlist = eval_string.split(".")
    resource_type = "aws_" + helpers.find_between(eval_string, "aws_", ".")
    resource_name = helpers.find_between(eval_string, ".", "[")
    resource = resource_type + "." + resource_name
    return tfdata["meta_data"][resource]["count"]


def show_error(mod, resource, eval_string, exp, tfdata):
    click.echo(
        f"    ERROR: {mod} : {resource} count = 0 (Error in calling function {exp}))"
    )
    tfdata["meta_data"][resource]["count"] = 0
    tfdata["meta_data"][resource]["ERROR_count"] = eval_string
    return tfdata


def handle_conditional_resources(tfdata):
    click.echo(f"\n  Conditional Resource List:")
    for resource, attr_list in tfdata["meta_data"].items():
        mod = tfdata["meta_data"][resource]["module"]
        eval_string = find_conditional_statements(resource, attr_list)
        if eval_string and not "ERROR" in eval_string:
            original_string = tfdata["meta_data"][resource]["original_count"]
            if "module." in eval_string:
                eval_string = handle_module_vars(eval_string, tfdata)
            if "aws_" and "[*]." in eval_string:
                eval_string = handle_splat_statements(eval_string, tfdata)
            # We have a conditionally created resource
            checks = 0
            original_step1 = eval_string
            while check_for_tf_functions(eval_string) != False:
                if checks > 100:
                    break
                eval_string = helpers.fix_lists(eval_string)
                eval_string = eval_tf_functions(eval_string)
                checks = checks + 1
            if checks > 100:
                eval_string = eval_string + "ERROR!"
            exp = eval_string
            if not "ERROR!" in exp:
                obj = Conversion(len(exp))
                pf = obj.infixToPostfix(exp)
                if not pf == "ERROR!":
                    obj = Evaluate(len(pf))
                    eval_value = obj.evaluatePostfix(pf)
                    if eval_value == "" or eval_value == " ":
                        eval_value = 0
                    if eval_value == "ERROR!":
                        show_error(mod, resource, eval_string, exp, tfdata)
                    else:
                        click.echo(
                            f"    Module {mod} : {resource} count = {original_string}"
                        )
                        if checks > 1:
                            click.echo(
                                f"                 {resource} count = {original_step1}"
                            )
                        click.echo(f"                 {resource} count = {exp})")
                        click.echo(f"                 {resource} count = {eval_value}")
                        attr_list["count"] = int(eval_value)
                else:
                    click.echo(
                        f"    ERROR: {mod} : {resource} count = 0 (Error in evaluation of value {exp})"
                    )
                    tfdata["meta_data"][resource]["count"] = 0
                    tfdata["meta_data"][resource]["ERROR_count"] = eval_string
            else:
                show_error(mod, resource, eval_string, exp, tfdata)
    tfdata["hidden"] = [
        key
        for key, attr_list in tfdata["meta_data"].items()
        if str(attr_list.get("count")) == "0"
        or str(attr_list.get("count")).startswith("$")
    ]
    return tfdata


def get_metadata(tfdata):  # -> set
    """
    Extract resource attributes from resources by looping through each resource in each file.
    Returns a set with a node_list of unique resources, resource attributes (metadata)
    """
    node_list = []
    meta_data = dict()
    # Default module is assumed main unless over-ridden
    mod = "main"
    click.echo("\n  Processing Resource Attributes..\n")
    if not tfdata.get("all_resource"):
        click.echo(
            click.style(
                f"\WARNING: Unable to find any resources ",
                fg="white",
                bold=True,
            )
        )
        tfdata["all_resource"] = {}
        tfdata["node_list"] = {}
    for filename, resource_list in tfdata["all_resource"].items():
        if "all_module" in tfdata.keys():
            # Default module assumed to be main
            # Search for mod name in all_module and switch module scope if found
            mod = "main"
            for _, module_list in tfdata["all_module"].items():
                for module in module_list:
                    for moddata in module:
                        if ".terraform" in filename:
                            mod = moddata
                            break
        for item in resource_list:
            for k in item.keys():
                resource_type = k
                for i in item[k]:
                    resource_name = i
                    # Check if Cloudwatch is present in policies and create node for Cloudwatch service if found
                    if resource_type == "aws_iam_policy":
                        if "logs:" in item[resource_type][resource_name]["policy"][0]:
                            if not "aws_cloudwatch_log_group.logs" in node_list:
                                node_list.append("aws_cloudwatch_log_group.logs")
                            meta_data["aws_cloudwatch_log_group.logs"] = item[
                                resource_type
                            ][resource_name]
                node_list.append(f"{resource_type}.{resource_name}")
                md = item[k][i]
                if md.get("count"):
                    md["original_count"] = str(md["count"])
                if resource_type.startswith("aws"):
                    meta_data[f"{resource_type}.{resource_name}"] = md
                    meta_data[f"{resource_type}.{resource_name}"]["module"] = mod
                    if f"{resource_type}.{resource_name}-1" in tfdata["node_list"]:
                        for i in range(1, 4):
                            meta_data[f"{resource_type}.{resource_name}-{i}"] = md
                            meta_data[f"{resource_type}.{resource_name}-{i}"][
                                "module"
                            ] = mod
    tfdata["meta_data"] = meta_data
    tfdata["all_node_list"] = node_list
    tfdata["node_list"] = list(dict.fromkeys(tfdata["graphdict"]))
    return tfdata


def get_variable_values(tfdata) -> dict:
    """Returns a list of all variables from local .tfvar defaults, supplied varfiles and module var values"""
    click.echo("\nProcessing Variables..\n")
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
                click.echo(f"    var.{var_name}")
                var_data[var_name] = var_value
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
                    var_mappings[mod][var_name] = var_value
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
    if tfdata.get("all_variable"):
        # Over-write defaults with passed varfile specified values
        for varfile in tfdata["varfile_list"]:
            # Open supplied varfile for reading
            with click.open_file(varfile, "r") as f:
                variable_values = hcl2.load(f)
            for uservar in variable_values:
                var_data[uservar.lower()] = variable_values[uservar]
                if not var_mappings.get("main"):
                    var_mappings["main"] = {}
                var_mappings["main"][uservar.lower()] = variable_values[uservar]
    tfdata["variable_list"] = var_data
    tfdata["variable_map"] = var_mappings
    return tfdata
