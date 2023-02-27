import re
import click
from requests.api import head
from tqdm import tqdm
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from posixpath import dirname, split
from sys import exit
from urllib.parse import urlparse
from modules.helpers import *
from modules.postfix import Conversion, Evaluate
from sys import exit
import modules.helpers as helpers
import hcl2

DATA_REPLACEMENTS = {"data.aws_availability_zones": "['AZ1', 'AZ2', 'AZ3']"}


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
                "var." in value
                or "local." in value
                or "module." in value
                or "data." in value
            ):
                value = find_replace_values(value, attr_list["module"], tfdata)
            tfdata["meta_data"][resource][key] = value
    return tfdata


def find_replace_values(varstring, module, tfdata):
    value = str(varstring)
    var_found_list = re.findall("\$\{var\.[A-Za-z0-9_\-]+\}", value) or re.findall(
        "var\.[A-Za-z0-9_\-]+", value
    )
    data_found_list = re.findall(
        "\${data\.[A-Za-z0-9_\-\.\[\]]+\}", value
    ) or re.findall("data\.[A-Za-z0-9_\-\.\[\]]+", value)
    varobject_found_list = re.findall(
        "\$\{var\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\}", value
    ) or re.findall("var\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", value)
    local_found_list = re.findall("\$\{local\.[A-Za-z0-9_\-]+\}", value) or re.findall(
        "local\.[A-Za-z0-9_\-]+", value
    )
    modulevar_found_list = re.findall(
        "\$\{module\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\}", value
    ) or re.findall("module\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", value)
    for d in data_found_list:
        for search_string, keyvalue in DATA_REPLACEMENTS.items():
            if search_string in d:
                value = str(value.replace(d, str(keyvalue)))
        if value == varstring:
            value = str(value.replace(d, "UNKNOWN"))
    for module_var in modulevar_found_list:
        cleantext = fix_lists(module_var)
        splitlist = cleantext.split(".")
        outputname = find_between(cleantext, splitlist[1] + ".", " ")
        oldvalue = value
        for ofile in tfdata["all_output"].keys():
            for i in tfdata["all_output"][ofile]:
                if outputname in i.keys():
                    value = value.replace(module_var, i[outputname]["value"])
                    break
        if value == oldvalue:
            value = value.replace(module_var, "UNKNOWN")
    for varitem in var_found_list:
        lookup = varitem.split("var.")[1].lower().replace("}", "")
        if (lookup in tfdata["variable_map"][module].keys()) and (
            "var." + lookup not in str(tfdata["variable_map"][module][lookup])
        ):
            # Possible object type var encountered
            obj = ""
            for item in varobject_found_list:
                if lookup in item:
                    obj = tfdata["variable_map"][module][lookup]
                    varitem = item
            # click.echo(f'    var.{lookup}')
            if value.count(lookup) < 2 and obj != "" and isinstance(obj, dict):
                key = varitem.split(".")[2]
                keyvalue = obj[key]
                if (
                    isinstance(keyvalue, str)
                    and not keyvalue.startswith("[")
                    and not keyvalue.startswith("{")
                ):
                    keyvalue = f'"{keyvalue}"'
                value = value.replace(varitem, str(keyvalue))
            elif value.count(lookup) < 2 and obj == "":
                replacement_value = str(tfdata["variable_map"][module].get(lookup))
                if (
                    isinstance(replacement_value, str)
                    and '"' not in replacement_value
                    and not replacement_value.startswith("[")
                ):
                    replacement_value = f'"{replacement_value}"'
                value = value.replace(varitem, replacement_value)
            else:
                value = value.replace(
                    varitem, str(tfdata["variable_map"][module][lookup]) + " "
                )
        elif lookup in tfdata["variable_map"]["main"].keys():
            value = value.replace(
                varitem, str(tfdata["variable_map"]["main"].get(lookup))
            )
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
    # Handle Locals
    for localitem in local_found_list:
        lookup = cleanup(localitem.split("local.")[1])
        if tfdata["all_locals"]:
            if lookup in tfdata["all_locals"][module].keys():
                replacement_value = tfdata["all_locals"][module].get(lookup)
                value = value.replace(localitem, replacement_value)
            else:
                value = value.replace(localitem, "None")
                click.echo(
                    f"    WARNING: Cannot resolve {localitem}, assigning empty value"
                )
        else:
            value = value.replace(localitem, "None")
            click.echo(f"    ERROR: Cannot find definition for local var {localitem}")
            exit()
    return value


def extract_locals(tfdata):
    click.echo("\n  Parsing locals...")
    module_locals = dict()
    # Remove array layer of locals dict structure and copy over to final_locals dict first
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
        return helpers.cleanup_curlies(eval_string)
    if (
        "count" in attr_list.keys()
        and not isinstance(attr_list["count"], int)
        and not resource.startswith("null_resource")
    ):
        eval_string = str(attr_list["count"])
        return helpers.cleanup_curlies(eval_string)
    for attrib in attr_list:
        if "for" in attrib and "in" in attrib:
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


def handle_conditional_resources(tfdata):
    click.echo(f"\n  Conditional Resource List:")
    for resource, attr_list in tfdata["meta_data"].items():
        mod = tfdata["meta_data"][resource]["module"]
        eval_string = find_conditional_statements(resource, attr_list)
        if eval_string:
            if "module." in eval_string:
                eval_string = handle_module_vars(eval_string, tfdata)
            if "aws_" and "[*]." in eval_string:
                eval_string = handle_splat_statements(eval_string, tfdata)
            # We have a conditionally created resource
            while check_for_tf_functions(eval_string) != False:
                eval_string = helpers.fix_lists(eval_string)
                eval_string = eval_tf_functions(eval_string)
            exp = eval_string
            if not "ERROR!" in exp:
                obj = Conversion(len(exp))
                pf = obj.infixToPostfix(exp)
                if not pf == "ERROR!":
                    obj = Evaluate(len(pf))
                    eval_value = obj.evaluatePostfix(pf)
                    if eval_value == "" or eval_value == " ":
                        eval_value = 0
                    click.echo(
                        f"    Module {mod} : {resource} count = {eval_value} ({exp})"
                    )
                    attr_list["count"] = int(eval_value)
                else:
                    click.echo(
                        f"    ERROR: {mod} : {resource} count = 0 (Error in evaluation of value {exp})"
                    )
            else:
                click.echo(
                    f"    ERROR: {mod} : {resource} count = 0 (Error in calling function {exp}))"
                )
    tfdata["hidden"] = [
        key
        for key, attr_list in tfdata["meta_data"].items()
        if str(attr_list.get("count")) == "0"
        or str(attr_list.get("count")).startswith("$")
    ]
    return tfdata


def get_metadata(tfdata):  #  -> set
    """
    Extract resource attributes from resources by looping through each resource in each file.
    Returns a set with a node_list of unique resources, resource attributes (metadata) and hidden (zero count) nodes
    """
    node_list = []
    meta_data = dict()
    variable_list = tfdata.get("variable_map")
    all_locals = tfdata.get("all_locals")
    all_outputs = tfdata.get("all_output")
    for filename, resource_list in tfdata["all_resource"].items():
        if ";" in filename:
            # We have a module file being processed
            modarr = filename.split(";")
            mod = modarr[1]
        else:
            mod = "main"
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
                # click.echo(f'    {resource_type}.{resource_name}')
                node_list.append(f"{resource_type}.{resource_name}")
                meta_data[f"{resource_type}.{resource_name}"] = item[k][i]
                meta_data[f"{resource_type}.{resource_name}"]["module"] = mod

    # Handle CF Special meta data
    cf_data = [s for s in meta_data.keys() if "aws_cloudfront" in s]
    if cf_data:
        for cf_resource in cf_data:
            if "origin" in meta_data[cf_resource]:
                for origin_source in meta_data[cf_resource]["origin"]:
                    if isinstance(origin_source, str) and origin_source.startswith("{"):
                        origin_source = literal_eval(origin_source)
                    origin_domain = cleanup(origin_source.get("domain_name")).strip()
                    if origin_domain:
                        meta_data[cf_resource]["origin"] = handle_cloudfront_domains(
                            str(origin_source), origin_domain, meta_data
                        )

    tfdata["meta_data"] = meta_data
    tfdata["node_list"] = node_list
    return tfdata


def handle_cloudfront_domains(origin_string: str, domain: str, mdata: dict) -> str:
    for key, value in mdata.items():
        for k, v in value.items():
            if domain in str(v) and not domain.startswith("aws_"):
                o = origin_string.replace(domain, key)
                return origin_string.replace(domain, key)
    return origin_string


def get_variable_values(tfdata) -> dict:
    """Returns a list of all variables from local .tfvar defaults, supplied varfiles and module var values"""
    click.echo("Processing Variables..")
    if not tfdata.get("all_variable"):
        tfdata["all_variable"] = dict()
    var_data = dict()
    var_mappings = dict()
    # Load default values from all existing files in source locations
    for var_source_file, var_list in tfdata["all_variable"].items():
        var_source_dir = str(Path(var_source_file).parent)
        for item in var_list:
            for k in item.keys():
                var_name = k
                for var_attr in item[k]:
                    # Populate dict with default values first
                    if (
                        var_attr == "default"
                    ):  # and not var_name in variable_values.keys():
                        if item[k][var_attr] == "":
                            var_value = ""
                        else:
                            var_value = item[k][var_attr]
                        var_data[var_name] = var_value
                        # Also update var mapping dict with modules and matching variables
                        matching = [
                            m
                            for m in tfdata["module_source_dict"]
                            if tfdata["module_source_dict"][m]["cache_path"][1:-1]
                            in str(var_source_file)
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
    if tfdata["module_source_dict"]:
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
    # tfdata["variable_list"] = var_data
    tfdata["variable_map"] = var_mappings
    return tfdata
