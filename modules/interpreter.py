"""Terraform variable and metadata interpreter.

Handles resolution of Terraform variables, locals, data sources, and module outputs.
Processes resource metadata and manages variable substitution across modules.
"""

from typing import Dict, List, Any, Tuple
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


def resolve_all_variables(
    tfdata: Dict[str, Any], debug: bool, already_processed: bool
) -> Dict[str, Any]:
    """Resolve all Terraform variables, locals, and module outputs.

    Args:
        tfdata: Terraform data dictionary containing resources and variables
        debug: Enable debug output and logging
        already_processed: Skip variable file processing if already done

    Returns:
        Updated tfdata with all variables resolved
    """
    # Load default variable values and user variable values
    tfdata = get_variable_values(tfdata, already_processed)
    # Create view of locals by module
    tfdata = extract_locals(tfdata)
    # Create metadata view from nested TF file resource attributes
    tfdata = merge_metadata(tfdata)
    # Replace metadata (resource attributes) variables and locals with actual values
    tfdata = handle_metadata_vars(tfdata)
    # Inject parent module variables that are referenced downstream in sub modules
    if "all_module" in tfdata.keys():
        tfdata = inject_module_variables(tfdata)
    # Dump out findings after file scans are complete
    if debug:
        helpers.output_log(tfdata)
    return tfdata


def handle_module_vars(eval_string: str, tfdata: Dict[str, Any]) -> str:
    """Resolve module output variable references.

    Args:
        eval_string: String containing module.name.output reference
        tfdata: Terraform data dictionary

    Returns:
        String with module variable resolved to actual value
    """
    outvalue = ""
    splitlist = eval_string.split(".")
    # Extract output name and module name from reference
    outputname = helpers.find_between(eval_string, splitlist[1] + ".", " ")
    mod = helpers.find_between(eval_string, splitlist[0] + ".", ".")
    # Search through all output files for matching module
    for file in tfdata["all_output"].keys():
        for i in tfdata["all_output"][file]:
            if outputname in i.keys() and f";{mod};" in file:
                outvalue = i[outputname]["value"]
                # Handle wildcard ID references
                if "*.id" in outvalue and "*.id" in eval_string:
                    outvalue = tfdata["meta_data"][outvalue]["count"]
                    break
                # Handle specific array index references
                if "*.id" in outvalue and "[" in eval_string and "]" in eval_string:
                    index = int(
                        helpers.find_between(eval_string, "[", "]").replace(" ", "")
                    )
                    outvalue = f"module.{mod}.{helpers.strip_var_curlies(outvalue).replace('.*.id', '').replace('.*', '').strip()}[{index}]"
                    break
    # Replace module variable with resolved value
    stringarray = eval_string.split(".")
    if len(stringarray) >= 3:
        modulevar = "module" + "." + stringarray[1] + "." + stringarray[2]
        modulevar = modulevar.strip()
        eval_string = helpers.cleanup_curlies(eval_string.replace(modulevar, outvalue))
    return eval_string


def inject_module_variables(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Inject parent module variables into child modules.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with module variables injected
    """
    # Loop through all module definitions
    for file, module_list in tfdata["all_module"].items():
        for module_items in module_list:
            for module, params in module_items.items():
                module_source = params["source"]
                # Process each parameter passed to the module
                for key, value in params.items():
                    # Resolve module output references
                    if "module." in str(value) and key != "depends_on":
                        value = handle_module_vars(str(value), tfdata)
                    # Resolve variable references
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
                    # Add resolved value to variable map for downstream use
                    if key != "source" and key != "version":
                        tfdata["variable_map"][module][key] = value
    return tfdata


def handle_metadata_vars(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Replace variables in resource metadata with actual values.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with resolved metadata variables
    """
    # Loop through each resource's metadata attributes
    for resource, attr_list in tfdata["meta_data"].items():
        for key, orig_value in attr_list.items():
            value = str(orig_value)
            # Iteratively resolve all variable references
            while (
                (
                    "var." in value
                    or "local." in value
                    or "data." in value
                    or (
                        "module." in value
                        and not re.search(r"module\.[\w-]+\.aws_", value)
                    )
                )
                and key != "depends_on"
                and key != "original_count"
            ):
                mod = attr_list["module"]
                old_value = value
                value = find_replace_values(value, mod, tfdata)
                if value == old_value:
                    click.echo(
                        click.style(
                            f"   WARNING: Cannot fully resolve {resource}.{key}, unresolved references remain",
                            fg="yellow",
                        )
                    )
                    break
            # Update metadata with resolved value
            tfdata["meta_data"][resource][key] = value
    return tfdata


def replace_data_values(
    found_list: List[str], value: str, tfdata: Dict[str, Any]
) -> str:
    """Replace Terraform data source references with mock values.

    Args:
        found_list: List of data source references found in value
        value: String containing data source references
        tfdata: Terraform data dictionary

    Returns:
        String with data sources replaced by mock values
    """
    initial_value = value
    # Loop through each data source reference
    for d in found_list:
        # Check against known data source replacements
        for search_string, keyvalue in DATA_REPLACEMENTS.items():
            if search_string in d:
                # Return list directly if single data reference
                if (
                    initial_value.startswith("${data.")
                    and len(found_list) == 1
                    and not isinstance(keyvalue, str)
                ):
                    value = keyvalue
                else:
                    value = str(value.replace(d, str(keyvalue)))
        # Mark as unknown if no replacement found
        if value == initial_value:
            value = str(value.replace(d, '"UNKNOWN"'))
    return value


def replace_local_values(
    found_list: List[str], value: str, module: str, tfdata: Dict[str, Any]
) -> str:
    """Replace local variable references with actual values.

    Args:
        found_list: List of local variable references
        value: String containing local references
        module: Module name for variable lookup
        tfdata: Terraform data dictionary

    Returns:
        String with local variables resolved
    """
    # Loop through each local variable reference
    for localitem in found_list:
        lookup = helpers.cleanup(localitem.split("local.")[1])
        if tfdata["all_locals"]:
            # Check if local exists in current module
            if (
                module in tfdata["all_locals"]
                and lookup in tfdata["all_locals"][module].keys()
            ):
                replacement_value = tfdata["all_locals"][module].get(lookup)
                value = helpers.find_replace(localitem, str(replacement_value), value)
            else:
                # Fall back to main module locals
                if tfdata["all_locals"].get("main"):
                    if lookup in tfdata["all_locals"]["main"].keys():
                        replacement_value = tfdata["all_locals"]["main"].get(lookup)
                        value = helpers.find_replace(
                            localitem, str(replacement_value), value
                        )
                    else:
                        value = value.replace(localitem, "None")
                        click.echo(
                            f"   WARNING: Cannot resolve {localitem}, assigning empty value in module {module}"
                        )
        else:
            # No locals defined
            value = helpers.find_replace(localitem, "None", value)
            click.echo(f"    ERROR: Cannot find definition for local var {localitem}")
            exit()
    return value


def replace_module_vars(
    found_list: List[str],
    value: str,
    module: str,
    tfdata: Dict[str, Any],
    recursion_depth: int = 0,
) -> str:
    """Replace module output references with actual values.

    Args:
        found_list: List of module variable references
        value: String containing module references
        module: Current module name
        tfdata: Terraform data dictionary
        recursion_depth: Current recursion depth to prevent infinite loops

    Returns:
        String with module variables resolved
    """
    # Loop through each module variable reference
    for module_var in found_list:
        if "module." in value:
            cleantext = module_var
            splitlist = cleantext.split(".")
            outputname = helpers.find_between(cleantext, splitlist[1] + ".", " ")
            oldvalue = value
            mod = value.split("module.")[1].split(".")[0]
            # Search through output files for matching module
            for ofile in tfdata["all_output"].keys():
                if "modules" and f";{mod};" in ofile:
                    # Found the right output file for this module
                    for i in tfdata["all_output"][ofile]:
                        if outputname in i.keys():
                            # Check if this is a module output reference (not a resource)
                            if "module." in module_var and not re.search(
                                r"module\.[\w-]+\.aws_", module_var
                            ):
                                # Handle specific array index references
                                if (
                                    "[" in module_var
                                    and "[*]" not in module_var
                                    and "*.id" in i[outputname]["value"]
                                ):
                                    value = value.replace(
                                        module_var, f"module.{mod}.{module_var}"
                                    )
                                    value = value.replace(
                                        module_var, i[outputname]["value"]
                                    )
                                    index = helpers.find_between(
                                        module_var, "[", "]"
                                    ).replace(" ", "")
                                    value = helpers.strip_var_curlies(
                                        value.replace(".*.id", f"[{index}]")
                                    ).strip()
                                    continue
                            # Recursively resolve if output contains other variables
                            if (
                                (
                                    "module." in i[outputname]["value"]
                                    and not not re.search(
                                        r"module\.\w+\.aws_", module_var
                                    )
                                )
                                or "var." in i[outputname]["value"]
                                or "local." in i[outputname]["value"]
                            ):
                                value = find_replace_values(
                                    value, mod, tfdata, recursion_depth + 1
                                )
                                continue
                            else:
                                # Direct replacement with output value
                                if (
                                    not f"module.{mod}.{module_var}" in value
                                    and f"module.{mod}.{module_var}" not in module_var
                                ):
                                    value = value.replace(
                                        module_var, f"module.{mod}.{module_var}"
                                    )
                                value = value.replace(
                                    module_var, i[outputname]["value"]
                                )
                                value = helpers.remove_terraform_functions(value)
                                value = helpers.cleanup_curlies(value).strip()
                else:
                    continue
            # Mark as unknown if no resolution found
            if value == oldvalue and not re.search(r"module\.[\w-]+\.aws_", module_var):
                value = value.replace(module_var, '"UNKNOWN"')
                click.echo(
                    f"   WARNING: Cannot resolve {module_var}, assigning UNKNOWN value in module {module}"
                )
            # Clean up wildcard ID references
            if "[" in value and "*.id" in value:
                value = (value.replace(".*.id", "")).strip()
    return value


def replace_var_values(
    found_list: List[str],
    varobject_found_list: List[str],
    value: str,
    module: str,
    tfdata: Dict[str, Any],
) -> str:
    """Replace variable references with actual values.

    Args:
        found_list: List of simple variable references
        varobject_found_list: List of object-type variable references
        value: String containing variable references
        module: Module name for variable lookup
        tfdata: Terraform data dictionary

    Returns:
        String with variables resolved to actual values
    """
    # Loop through each variable reference
    for varitem in found_list:
        varitem_lower = varitem.lower()
        # Extract variable name from reference
        lookup = (
            varitem_lower.split("var.")[1]
            .lower()
            .replace("}", "")
            .replace(" ", "")
            .replace(".", "")
        )
        if not module:
            module = "main"
        # Check if variable exists in current module and is resolved
        if (lookup in tfdata["variable_map"][module].keys()) and (
            "var." + lookup not in str(tfdata["variable_map"][module][lookup])
        ):
            # Handle object-type variables (e.g., var.config.key)
            obj = ""
            for item in varobject_found_list:
                if lookup in item:
                    obj = tfdata["variable_map"][module][lookup]
                    varitem = item
            # Extract key from object variable
            if value.count(lookup) < 2 and obj != "" and isinstance(obj, dict):
                key = varitem.split(".")[2]
                if key in obj.keys():
                    keyvalue = obj[key]
                else:
                    keyvalue = obj
                # Add quotes to string values
                if (
                    isinstance(keyvalue, str)
                    and not keyvalue.startswith("[")
                    and not keyvalue.startswith("{")
                ):
                    keyvalue = f'"{keyvalue}"'
                value = value.replace(varitem, str(keyvalue), 1)
            # Handle simple variable replacement
            elif value.count(lookup) < 2 and obj == "":
                replacement_value = str(tfdata["variable_map"][module].get(lookup))
                if (
                    isinstance(replacement_value, str)
                    and '"' not in replacement_value
                    and not replacement_value.startswith("[")
                ):
                    replacement_value = f'"{replacement_value}"'
                value = value.replace(varitem, replacement_value, 1)
            else:
                value = value.replace(
                    varitem, str(tfdata["variable_map"][module][lookup]) + " ", 1
                )
        # Variable exists but still contains unresolved references
        elif lookup in tfdata["variable_map"][module].keys():
            if "var." in tfdata["variable_map"][module].get(lookup):
                value = helpers.find_replace(varitem, '"UNKNOWN"', value)
            else:
                value = value.replace(
                    varitem, str(tfdata["variable_map"][module].get(lookup), 1)
                )
            break
        # Search parent modules for variable
        elif helpers.list_of_parents(tfdata["variable_map"], lookup):
            module_list = helpers.list_of_parents(tfdata["variable_map"], lookup)
            module_name = (
                [m for m in module_list if m == module][0]
                if [m for m in module_list if m == module]
                else module_list[0]
            )
            value = value.replace(
                varitem, str(tfdata["variable_map"][module_name].get(lookup)), 1
            )
            break
        # Variable not found anywhere
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


def find_replace_values(
    varstring: str, module: str, tfdata: Dict[str, Any], recursion_depth: int = 0
) -> str:
    """Find and replace all variable types in a string.

    Args:
        varstring: String containing variable references
        module: Module name for variable lookup
        tfdata: Terraform data dictionary
        recursion_depth: Current recursion depth to prevent infinite loops

    Returns:
        String with all variables resolved
    """
    # Check for infinite loop - prevent excessive recursion
    if recursion_depth >= 50:
        click.echo(
            f"   WARNING: Cannot resolve variable after 50 iterations: {varstring}"
        )
        return "UNKNOWN"

    # Regex string matching to create lists of different variable markers found
    value = helpers.strip_var_curlies(str(varstring))
    # Find all variable types using regex patterns
    var_found_list = re.findall(r"var\.[A-Za-z0-9_\-]+", value)
    data_found_list = re.findall(r"data\.[A-Za-z0-9_\-\.\[\]]+", value)
    varobject_found_list = re.findall(r"var\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", value)
    local_found_list = re.findall(r"local\.[A-Za-z0-9_\-\.\[\]]+", value)
    modulevar_found_list = [
        m.rstrip("[") for m in re.findall(r"module\.[A-Za-z0-9_\-\.\[\]]+", value)
    ]
    # Replace found variable strings with actual values in order
    value = replace_data_values(data_found_list, value, tfdata)
    value = replace_module_vars(
        modulevar_found_list, value, module, tfdata, recursion_depth
    )
    value = replace_var_values(
        var_found_list, varobject_found_list, value, module, tfdata
    )
    value = replace_local_values(local_found_list, value, module, tfdata)
    return value


def extract_locals(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and organize local variables by module.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with locals organized by module
    """
    module_locals = dict()
    # Flatten nested locals structure and organize by module
    if not tfdata.get("all_locals"):
        tfdata["all_locals"] = {}
        return tfdata
    # Process each file's local variables
    for file, localvarlist in tfdata["all_locals"].items():
        # Extract module name from filename
        if ";" in file:
            modname = file.split(";")[1]
        else:
            modname = "main"
        # Merge locals for each module
        for local in localvarlist:
            if module_locals.get(modname):
                module_locals[modname] = {**module_locals[modname], **local}
            else:
                module_locals[modname] = local
    tfdata["all_locals"] = module_locals
    return tfdata


def prefix_module_names(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Add module prefix to resource names within modules.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with module-prefixed resource names
    """
    # Track processed resources to avoid duplicates when modules called multiple times
    processed_list = []
    # Loop through each resource in tfdata["all_resource"]
    for file, resourcelist in dict(tfdata["all_resource"]).items():
        # Check if resource belongs to a module
        for module_name, module_path in tfdata["module_source_dict"].items():
            if module_path in file:
                # Add module prefix to resource names
                for index, elementdict in enumerate(resourcelist):
                    for resource_type, value in elementdict.items():
                        for resource_name in value:
                            renamed_resource_name = (
                                f"module.{module_name}.{resource_type}.{resource_name}"
                            )
                            # Only rename if not already prefixed and not processed
                            if (
                                "module." not in resource_name
                                and renamed_resource_name not in processed_list
                            ):
                                # Create new dict with renamed resource
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


def show_error(
    mod: str, resource: str, eval_string: str, exp: str, tfdata: Dict[str, Any]
) -> Dict[str, Any]:
    """Display error message and update metadata with error info.

    Args:
        mod: Module name
        resource: Resource name
        eval_string: Expression that caused error
        exp: Exception message
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with error information
    """
    click.echo(
        f"    ERROR: {mod} : {resource} count = 0 (Error in calling function {exp}))"
    )
    tfdata["meta_data"][resource]["count"] = 0
    tfdata["meta_data"][resource]["ERROR_count"] = eval_string
    return tfdata


def handle_implied_resources(
    item: Dict[str, Any],
    resource_type: str,
    resource_name: str,
    tfdata: Dict[str, Any],
    meta_data: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Add implied resources based on resource attributes.

    Args:
        item: Resource item dictionary
        resource_type: Type of resource
        resource_name: Name of resource
        tfdata: Terraform data dictionary
        meta_data: Resource metadata dictionary

    Returns:
        Tuple of updated meta_data and tfdata
    """
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


def handle_numbered_nodes(
    resource_node: str, tfdata: Dict[str, Any], meta_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle resources with count/for_each that create numbered nodes.

    Args:
        resource_node: Resource node name with bracket notation
        tfdata: Terraform data dictionary
        meta_data: Resource metadata dictionary

    Returns:
        Updated meta_data with numbered node information
    """
    # Determine count by number of objects created by Terraform
    all_matching_list = helpers.find_all_resources_containing(
        tfdata["node_list"], resource_node.split("[")[0] + "["
    )
    resource_count = len(all_matching_list)
    # Copy metadata to each numbered instance
    for actual_name in all_matching_list:
        import copy

        meta_data[actual_name] = copy.deepcopy(meta_data[resource_node])
        meta_data[actual_name]["count"] = resource_count
    return meta_data


def parse_resource_node(resource_node: str) -> Tuple[str, str]:
    """Parse resource node into type and name."""
    if resource_node.startswith("module."):
        parts = resource_node.split(".")
        resource_type = parts[2] if len(parts) > 2 else ""
        resource_name = ".".join(parts[3:]) if len(parts) > 3 else ""
    else:
        parts = resource_node.split(".", 1)
        resource_type = parts[0]
        resource_name = parts[1] if len(parts) > 1 else ""
    return resource_type, resource_name


def find_resource_in_all_resource(
    resource_type: str, base_name: str, resource_node: str, tfdata: Dict[str, Any]
) -> Tuple[Dict[str, Any], str]:
    """Find matching resource item and key in all_resource."""
    for resource_list in tfdata["all_resource"].values():
        for item in resource_list:
            if resource_type in item:

                if base_name in item[resource_type]:
                    return item, base_name
                if resource_node in item[resource_type]:
                    return item, resource_node
                # Check if resource_node matches first key
                first_key = next(iter(item[resource_type]), None)
                if first_key in resource_node:
                    return item, first_key
                # Check if first_key is the same module, resource_type but different name
                no_resource_name = resource_node.rsplit(".", 1)[0]
                if no_resource_name in first_key:
                    return item, first_key
    return None, None


def merge_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract resource attributes from raw Terraform source code and merge with attributes from terraform plan.
    Required so that relationships between resources can be accurately mapped by revealing attributes with original variable names,
    that often point to other resources once resolved.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with meta_data keys populated
    """
    meta_data = dict()
    click.echo(click.style(f"\nProcessing resources..", fg="white", bold=True))
    if not tfdata.get("all_resource"):
        click.echo(
            click.style("\nWARNING: Unable to find any resources", fg="red", bold=True)
        )
        tfdata["all_resource"] = {}
        tfdata["meta_data"] = {}
        return tfdata

    for resource_node in tfdata["node_list"]:
        click.echo(f"   {resource_node}")
        resource_type, resource_name = parse_resource_node(resource_node)
        base_name = resource_name.split("[")[0] if resource_name else ""
        item, actual_key = find_resource_in_all_resource(
            resource_type, base_name, resource_node, tfdata
        )
        if item:
            meta_data, tfdata = handle_implied_resources(
                item, resource_type, actual_key, tfdata, meta_data
            )
            if resource_node in tfdata["original_metadata"]:
                omd = dict(tfdata["original_metadata"][resource_node])
                md = item[resource_type][actual_key]
                if md.get("count"):
                    md["original_count"] = str(md["count"])
                omd.update(md)
                # Replace True values with original Terraform source expressions
                # True indicates "known after apply" - preserve the original HCL expression
                for k, v in list(omd.items()):
                    if v is True and k in md and md[k] is not True:
                        # Use the original HCL expression from all_resource
                        omd[k] = md[k]
                # Clean up metadata by removing empty values which add no info and clutter metadata
                omd = {
                    k: v
                    for k, v in omd.items()
                    if v is not True and v != "" and v != {} and v != [] and v != None
                }
                meta_data[resource_node] = omd
                if "~" in resource_node or meta_data[resource_node].get("count"):
                    meta_data = handle_numbered_nodes(resource_node, tfdata, meta_data)
            else:
                print("Key is not in container: ", resource_node)
            tfdata["meta_data"] = meta_data
    return tfdata


def get_variable_values(
    tfdata: Dict[str, Any], already_processed: bool
) -> Dict[str, Any]:
    """Load and organize all Terraform variable values.

    Args:
        tfdata: Terraform data dictionary
        already_processed: Skip varfile processing if already done

    Returns:
        Updated tfdata with variable_list and variable_map populated
    """
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
    # Load default values from variable definitions in source files
    for var_source_file, var_list in tfdata["all_variable"].items():
        var_source_dir = str(Path(var_source_file).parent)
        for item in var_list:
            for k in item.keys():
                var_name = k
                # Extract default value if present
                if "default" in item[k]:
                    var_value = item[k]["default"]
                    if isinstance(var_value, str):
                        var_value = f'"{var_value}"'
                else:
                    var_value = ""
                var_data[var_name.lower()] = var_value
                # Map variables to their modules
                if tfdata.get("module_source_dict"):
                    matching = [
                        m
                        for m in tfdata["module_source_dict"]
                        if tfdata["module_source_dict"][m] in str(var_source_file)
                    ]
                # Add to main module if no module match
                if not matching:
                    if not var_mappings.get("main"):
                        var_mappings["main"] = {}
                        var_mappings["main"] = {"source_dir": var_source_dir}
                    var_mappings["main"][var_name] = var_value
                # Add to matched modules
                for mod in matching:
                    if not var_mappings.get(mod):
                        var_mappings[mod] = {}
                        var_mappings[mod]["source_dir"] = var_source_dir
                    var_mappings[mod][var_name.lower()] = var_value
    # Add module parameters as variables
    if tfdata.get("module_source_dict"):
        for file, modulelist in tfdata["all_module"].items():
            for module in modulelist:
                for mod, params in module.items():
                    for variable in params:
                        var_data[variable] = params[variable]
                        if not var_mappings.get(mod):
                            var_mappings[mod] = {}
                        var_mappings[mod][variable] = params[variable]
    # Override defaults with user-supplied varfile values
    if tfdata.get("all_variable") and not already_processed:
        for varfile in tfdata["varfile_list"]:
            with click.open_file(varfile, encoding="utf8", mode="r") as f:
                variable_values = hcl2.load(f)
            # Apply user-supplied values
            for uservar in variable_values:
                var_data[uservar.lower()] = variable_values[uservar]
                if not var_mappings.get("main"):
                    var_mappings["main"] = {}
                var_mappings["main"][uservar.lower()] = variable_values[uservar]
    # Store results in tfdata
    tfdata["variable_list"] = var_data
    tfdata["variable_map"] = var_mappings

    return tfdata
