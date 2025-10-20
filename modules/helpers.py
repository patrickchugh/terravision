import os
import re
from contextlib import suppress
from pathlib import Path
from sys import exit
import click
import json
import modules.cloud_config as cloud_config
import modules.helpers as helpers

REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AWS_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.AWS_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.AWS_SPECIAL_RESOURCES
ACRONYMS_LIST = cloud_config.AWS_ACRONYMS_LIST
NAME_REPLACEMENTS = cloud_config.AWS_NAME_REPLACEMENTS

# List of dictionary sections to output in log
output_sections = ["locals", "module", "resource", "data", "output"]


def extract_json_from_string(text: str) -> dict:
    """Extract JSON object from text, handling code blocks and raw JSON."""
    # Try code block with optional json/JSON marker
    match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE
    )
    if match:
        with suppress(json.JSONDecodeError):
            return json.loads(match.group(1))

    # Try finding raw JSON object
    match = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text, re.DOTALL)
    if match:
        with suppress(json.JSONDecodeError):
            return json.loads(match.group(1))

    return {}


def check_for_domain(string: str) -> bool:
    exts = [".com", ".net", ".org", ".io", ".biz"]
    for dot in exts:
        if dot in string and not string.startswith("."):
            return True
    return False


# Export dict to a file called tfdata.json
def export_tfdata(tfdata: dict):
    tfdata["tempdir"] = str(tfdata["tempdir"])
    with open("tfdata.json", "w") as file:
        json.dump(tfdata, file, indent=4)
    click.echo(
        click.style(
            f"\nINFO: Debug flag used. Current state has been written to tfdata.json\n",
            fg="yellow",
            bold=True,
        )
    )


def remove_recursive_links(tfdata: dict):
    graphdict = tfdata.get("graphdict")
    circular = find_circular_refs(graphdict)
    if circular:
        click.echo(
            click.style(
                f"\nINFO: Found {len(circular)} circular references in the graph. These will be removed to prevent rendering issues.\n",
                fg="yellow",
                bold=True,
            )
        )
        for i, cycle in enumerate(circular, 1):
            print(f"  {i}. {' -> '.join(cycle)}")
            node_b = cycle[-1]
            node_a = cycle[-2]
            if node_b in graphdict[node_a]:
                graphdict[node_a].remove(node_b)
                click.echo(
                    click.style(
                        f"  Removed link from {node_a} to {node_b}",
                        fg="white",
                    )
                )
    return tfdata


def find_circular_refs(graph):
    """Find all circular references in the dependency graph."""
    circular_refs = []

    def dfs(node, path, visited_in_path):
        if node not in graph:
            return
        for neighbor in graph[node]:
            # Normalize neighbor name (remove array indices for comparison)
            neighbor_base = neighbor.split("[")[0] if "[" in neighbor else neighbor
            if neighbor in visited_in_path:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                circular_refs.append(cycle)
                continue
            if neighbor in graph:
                dfs(neighbor, path + [neighbor], visited_in_path | {neighbor})

    for node in graph:
        dfs(node, [node], {node})
    # Remove duplicate cycles
    unique_cycles = []
    seen = set()
    for cycle in circular_refs:
        # Normalize cycle representation
        min_idx = cycle.index(min(cycle[:-1]))
        normalized = tuple(cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]])
        if normalized not in seen:
            seen.add(normalized)
            unique_cycles.append(cycle)

    return unique_cycles


def process_graphdict(relations_graphdict: dict):
    processed_dict = {}
    for key, value in relations_graphdict.items():
        processed_dict[get_no_module_name(key)] = relations_graphdict[key]
        processed_value = []
        for item in value:
            processed_value.append(get_no_module_name(item))
        processed_dict[get_no_module_name(key)] = processed_value
    return processed_dict


def get_no_module_name(node: str):
    if not node:
        return
    if "module." in node:
        no_module_name = node.split(".")[-2] + "." + node.split(".")[-1]
    else:
        no_module_name = node
    return no_module_name


def extract_subfolder_from_repo(source_url: str) -> tuple[str, str]:
    """
    Extract repo URL and subfolder from a string like 'https://github.com/user/repo.git//code/02-one-server'.

    Returns:
        tuple: (repo_url, subfolder) - subfolder is empty string if none exists
    """
    # Find the subfolder separator // after the protocol
    if source_url.count("//") > 1:
        # Split on the second occurrence of //
        protocol_end = source_url.find("//") + 2
        remaining = source_url[protocol_end:]
        if "//" in remaining:
            repo_part, subfolder = remaining.split("//", 1)
            repo_url = source_url[:protocol_end] + repo_part
            subfolder = subfolder.rstrip("/")
            return repo_url, subfolder

    # Handle URLs without // but ending in path without .git
    if not source_url.endswith(".git") and "/" in source_url:
        parts = source_url.rstrip("/").split("/")
        if len(parts) > 3:  # protocol://domain/user/repo/subfolder
            repo_url = "/".join(parts[:-1])
            subfolder = parts[-1]
            return repo_url, subfolder

    return source_url, ""


def get_no_module_no_number_name(node: str):
    if not node:
        return
    if "module." in node:
        no_module_name = node.split(".")[-2] + "." + node.split(".")[-1]
    else:
        no_module_name = node
    no_module_name = no_module_name.split("[")[0]
    return no_module_name


def check_list_for_dash(connections: list):
    has_dash = True
    for item in connections:
        if not "~" in item:
            has_dash = False
    return has_dash


def sort_graphdict(graphdict: dict):
    for key in graphdict:
        graphdict[key].sort()
    return dict(sorted(graphdict.items()))


def url(string: str) -> str:
    if string.count("://") == 0:
        return "https://" + string
    return string


def check_for_tf_functions(string):
    for tf_function in dir(tf_function_handlers):
        if (
            tf_function + "(" in string or "_" + tf_function + "(" in string
        ) and "ERROR!_" + tf_function not in string:
            return tf_function
    return False


def find_nth(string, substring, n):
    if n == 1:
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)


def unique_services(nodelist: list) -> list:
    service_list = []
    for item in nodelist:
        service = str(item.split(".")[0]).strip()
        service_list.append(service)
    return sorted(set(service_list))


def remove_numbered_suffix(s: str) -> str:
    return s.split("~")[0] if "~" in s else s


def find_between(text, begin, end, alternative="", replace=False, occurrence=1):
    if not text:
        return
    # Handle Nested Functions with multiple brackets in parameters
    if begin not in text and not replace:
        return ""
    elif begin not in text and replace:
        return text
    if end == ")":
        begin_index = text.find(begin)
        # begin_index = find_nth(text, begin, occurrence)
        end_index = find_nth(text, ")", occurrence)
        end_index = text.find(")", begin_index)
        middle = text[begin_index + len(begin) : end_index]
        num_brackets = middle.count("(")
        if num_brackets >= 1:
            end_index = find_nth(text, ")", num_brackets + 1)
            middle = text[begin_index + len(begin) : end_index]
        return middle
    else:
        middle = text.split(begin, 1)[1].split(end, 1)[0]
    # If looking for a space but no space found, terminate with any non alphanumeric char except _
    # so that variable names don't get broken up (useful for extracting variable names and locals)
    if (end == " " or end == "") and not middle.endswith(" "):
        for i in range(0, len(middle)):
            char = middle[i]
            if not char.isalpha() and char != "_" and char != "~":
                end = char
                middle = text.split(begin, 1)[1].split(end, 1)[0]
                break
    if replace:
        return text.replace(begin + middle, alternative, 1)
    else:
        return middle


def remove_duplicate_words(string):
    words = string.split()
    unique_words = set(words)
    unique_words_list = list(unique_words)
    return " ".join(unique_words_list)


# 'aws_lb_target_group_attachment.mytg1["1"][1]'


# Function to remove square brackets from string
def remove_brackets_and_numbers(input_string):
    output_string = ""
    in_bracket = False
    for char in input_string:
        if char == "[":
            in_bracket = True
        elif char == "]":
            in_bracket = False
        elif not in_bracket and char not in ["[", "]"]:
            output_string += char
    return output_string


def pretty_name(name: str, show_title=True) -> str:
    """
    Beautification for AWS Labels
    """
    resourcename = ""
    if "null_" in name or "random" in name or "time_sleep" in name:
        return "Null"
    else:
        name = name.replace("tv_aws_", "")
        name = name.replace("aws_", "")
    name = get_no_module_name(name)
    servicename = name.split(".")[0]
    service_label = name.split(".")[-1]
    service_label = service_label.split("~")[0]
    if servicename.startswith(service_label.replace("_", "")):
        service_label = ""
    if servicename in NAME_REPLACEMENTS.keys():
        servicename = NAME_REPLACEMENTS[servicename]
    if service_label.title == servicename:
        service_label = ""
    final_label = (service_label if show_title else "") + " " + servicename
    final_label = final_label[:22]
    final_label = final_label.replace("_", " ")
    final_label = final_label.replace("~", " ")
    final_label = final_label.replace("this", "").strip()
    acronym = False
    final_label = final_label.title()[:21]
    for acro in ACRONYMS_LIST:
        if acro.title() in final_label:
            acronym = True
            final_label = final_label.replace(acro.title(), acro.upper())
    final_label = remove_duplicate_words(final_label)
    if acronym:
        return final_label
    else:
        return str(final_label.title())[:21]


def replace_variables(vartext, filename, all_variables, quotes=False):
    # Replace Variables found within resource meta data
    if isinstance(filename, list):
        filename = filename[0]
    vartext = str(vartext).strip()
    replaced_vartext = vartext
    var_found_list = re.findall(r"var\.[A-Za-z0-9_-]+", vartext)
    if var_found_list:
        for varstring in var_found_list:
            varname = varstring.replace("var.", "")
            with suppress(Exception):
                if str(all_variables[varname]) == "":
                    replaced_vartext = replaced_vartext.replace(varstring, '""')
                else:
                    replacement_value = getvar(varname, all_variables)
                    if replacement_value == "NOTFOUND":
                        click.echo(
                            click.style(
                                f"\nERROR: No variable value supplied for var.{varname} in {os.path.basename(os.path.dirname(filename))}/{os.path.basename(filename)}",
                                fg="red",
                                bold=True,
                            )
                        )
                        click.echo(
                            "Consider passing a valid Terraform .tfvars variable file with the --varfile parameter or setting a TF_VAR env variable\n"
                        )
                        exit()
                    replaced_vartext = replaced_vartext.replace(
                        "${" + varstring + "}", str(replacement_value)
                    )
                    replaced_vartext = replaced_vartext.replace(
                        varstring, str(replacement_value)
                    )
        return replaced_vartext


def output_log(tfdata):
    for section in output_sections:
        click.echo(f"\n  {section.title()} list :")
        if tfdata.get("all_" + section):
            for file, valuelist in tfdata["all_" + section].items():
                filepath = Path(file)
                fname = filepath.parent.name + "/" + filepath.name
                for item in valuelist:
                    if isinstance(item, dict):
                        for key in item:
                            output_string = (
                                f"    {fname}: {key}.{next(iter(item[key]))}"
                            )
                            output_string = output_string.replace(";", "|")
                            click.echo(output_string)
                    else:
                        output_string = f"    {fname}: {item}"
                        output_string = output_string.replace(";", "|")
                        click.echo(output_string)
    if tfdata.get("variable_map"):
        click.echo("\n  Variable List:")
        for module, variable in tfdata["variable_map"].items():
            if module == "main":
                variable["source"] = "main"
            click.echo(f"\n    Module: {module}")
            for key in variable:
                if not key.startswith("source"):
                    showval = str(variable[key])
                    if len(showval) > 60:
                        showval = showval[:60] + "..."
                    click.echo(f"      var.{key} = {showval}")
    return


def getvar(variable_name, all_variables_dict):
    # See if variable exists as an environment variable
    env_var = os.getenv("TF_VAR_" + variable_name)
    if env_var:
        return env_var
    # Check if it exists in all variables dict
    if variable_name in all_variables_dict:
        return all_variables_dict[variable_name]
    else:
        # Check if same variable with different casing exists
        for var in all_variables_dict:
            if var.lower() == variable_name.lower():
                return all_variables_dict[var]
    return "NOTFOUND"


def find_common_elements(dict_of_lists: dict, keyword: str) -> list:
    results = []
    for key1, list1 in dict_of_lists.items():
        for key2, list2 in dict_of_lists.items():
            if key1 != key2:
                for element in list1:
                    if element in list2 and keyword in key1 and keyword in key2:
                        results.append((key1, key2, element))
    return results


def find_resource_references(searchdict: dict, target_resource: str) -> dict:
    final_dict = dict()
    for item in searchdict:
        if target_resource in searchdict[item]:
            final_dict[item] = searchdict[item]
        for listitem in searchdict[item]:
            if target_resource in listitem:
                final_dict[item] = searchdict[item]
    return final_dict


def find_resource_containing(search_list: list, keyword: str):
    for actual_name in search_list:
        if keyword in actual_name:
            found = actual_name
            return found
    return False


def find_all_resources_containing(search_list: list, keyword: str):
    foundlist = list()
    for actual_name in search_list:
        if keyword in actual_name:
            foundlist.append(actual_name)
    if foundlist:
        return foundlist
    else:
        return False


def append_dictlist(thelist: list, new_item: object):
    new_list = list(thelist)
    new_list.append(new_item)
    return new_list


def remove_recursive(graphdict: dict) -> dict:
    for node, connections in graphdict.items():
        if node in connections:
            print(node)
        for c in connections:
            if graphdict.get(c):
                if node in graphdict.get(c):
                    print(node, c)
    return graphdict


def check_variant(resource: str, metadata: dict) -> str:
    for variant_service in NODE_VARIANTS:
        if resource.startswith(variant_service):
            for keyword in NODE_VARIANTS[variant_service]:
                if (
                    keyword in str(metadata)
                    and NODE_VARIANTS[variant_service] != resource
                ):
                    return NODE_VARIANTS[variant_service][keyword]
            return False
    return False


def find_replace(find: str, replace: str, string: str):
    original_string = string
    string = string.replace(find, replace, 1)
    return string


def list_of_parent_nodes(graphdict: dict, nodelist: list):
    parent_list = list()
    for node in nodelist:
        parent_nodes = list_of_parents(graphdict, node)
        for p in parent_nodes:
            if "~" not in p:
                parent_list.append(p)
    return parent_list


def list_of_parents(searchdict: dict, target: str):
    final_list = list()
    for key, value in searchdict.items():
        if isinstance(value, str):
            if target in value:
                final_list.append(key)
        elif isinstance(value, dict):
            for subkey in value.keys():
                if target in str(value[subkey]) or target in subkey:
                    final_list.append(key)
        elif isinstance(value, list):
            if target in value:
                final_list.append(key)
            elif ".*" in target:
                target = target.replace("*", "")
            for item in value:
                if not item:
                    continue
                if (
                    helpers.get_no_module_name(item).startswith(
                        helpers.get_no_module_name(target)
                    )
                    and key not in final_list
                ):
                    final_list.append(key)
    return final_list


def any_parent_has_count(tfdata: dict, target_resource: str):
    parents_list = list_of_parents(tfdata["graphdict"], target_resource)
    any_parent_has_count = False
    # Check if any of the parents of the connections have a count property
    for parent in parents_list:
        if "~" in parent:
            any_parent_has_count = True
            break
        c = (
            tfdata["meta_data"][parent].get("count")
            or tfdata["meta_data"][parent].get("for_each")
            or tfdata["meta_data"][parent].get("desired_count")
            or tfdata["meta_data"][parent].get("max_capacity")
        )
        if tfdata["meta_data"].get(parent) and isinstance(c, int):
            any_parent_has_count = True
    return any_parent_has_count


# Takes a resource and returns a standardised consolidated node if matched with the static definitions
def consolidated_node_check(resource_type: str) -> bool:
    for checknode in CONSOLIDATED_NODES:
        prefix = str(list(checknode.keys())[0])
        if get_no_module_name(resource_type).startswith(prefix) and resource_type:
            return checknode[prefix]["resource_name"]
    return False


def remove_all_items(test_list: list, item: str) -> list:
    # using filter() + __ne__ to perform the task
    res = list(filter((item).__ne__, test_list))
    return res


def list_of_dictkeys_containing(searchdict: dict, target_keyword: str) -> list:
    final_list = list()
    for item in searchdict:
        if target_keyword in item:
            final_list.append(item)
    return final_list


# Cleans out special characters
def cleanup_curlies(text: str) -> str:
    text = str(text)
    for ch in ["$", "{", "}"]:
        if ch in text:
            text = text.replace(ch, " ")
    return text.strip()


# Filter out ${} variable padding from strings
def strip_var_curlies(s: str):
    final_string = ""
    stack = []
    if ".id}" in s:
        s = s.replace(".id}", "}")
    if "${" in s:
        s = s.replace("${", "~")
    for i in range(len(s)):
        if s[i] == "~":
            stack.append(s[i])
        elif s[i] == "{":
            stack.append(s[i])
            final_string += s[i]
        elif stack and stack[-1] == "~" and s[i] == "}":
            stack.pop()
            final_string += " "
        elif stack and stack[-1] == "{" and s[i] == "}":
            stack.pop()
            final_string += s[i]
        else:
            final_string += s[i]
    return final_string


def extract_terraform_resource(text: str) -> str:
    """Extract terraform resource type and name from a string like '${module.mymodule.aws_apigatewayv2_api.myapi.id}'"""
    import re

    pattern = r"\$\{(?:[^(]*\()?(?:module\.[^.]+\.)?([^.]+\.[^.*}]+)(?:\.[^}]*)?\}?"
    match = re.search(pattern, text)
    return match.group(1) if match else ""


# Cleans out special characters
def cleanup(text: str) -> str:
    text = str(text)
    for ch in [
        "\\",
        "`",
        "*",
        "{",
        "}",
        "(",
        ")",
        ">",
        "!",
        "$",
        "'",
        '"',
        "  ",
        ",",
        "[",
    ]:
        if ch in text:
            text = text.replace(ch, " ")
    return text.strip()
