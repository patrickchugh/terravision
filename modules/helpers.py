"""Helper functions module for TerraVision.

This module provides utility functions for string manipulation, resource name
processing, variable replacement, graph operations, and Terraform-specific
data extraction and transformation.
"""

import json
import os
import re
from contextlib import suppress
from pathlib import Path
from sys import exit
from typing import Dict, List, Any, Tuple, Optional, Union

import click

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
    """Check if string contains a domain extension.

    Args:
        string: String to check for domain extensions

    Returns:
        True if domain extension found
    """
    exts = [".com", ".net", ".org", ".io", ".biz"]
    for dot in exts:
        if dot in string and not string.startswith("."):
            return True
    return False


def export_tfdata(tfdata: Dict[str, Any]) -> None:
    """Export Terraform data dictionary to tfdata.json for debugging.

    Args:
        tfdata: Terraform data dictionary to export
    """
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
    """Remove 2-node circular references from the graph.

    Detects and removes bidirectional links between two nodes (A->B and B->A)
    to prevent rendering issues. Longer cycles (A->B->C->A) are preserved.

    Args:
        tfdata: Dictionary containing 'graphdict' with node relationships

    Returns:
        dict: Updated tfdata with circular references removed from graphdict
    """
    graphdict = tfdata.get("graphdict")
    circular = find_circular_refs(graphdict)

    if circular:
        click.echo(
            click.style(
                f"\nINFO: Found {len(circular)} 2-node circular references in the graph. These will be removed to prevent rendering issues.\n",
                fg="yellow",
                bold=True,
            )
        )
        # Remove one direction of each bidirectional link
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
    """Find 2-node circular references (A->B->A) in the dependency graph.

    Only detects direct bidirectional links between two nodes. Longer cycles
    like A->B->C->A are not detected or reported.

    Args:
        graph: Dictionary where keys are nodes and values are lists of connected nodes

    Returns:
        list: List of cycles, each represented as [node_a, node_b, node_a]
    """
    circular_refs = []
    seen = set()

    # Check each node and its connections
    for node_a in graph:
        if node_a not in graph:
            continue
        for node_b in graph[node_a]:
            # Check if node_b also connects back to node_a
            if node_b in graph and node_a in graph[node_b]:
                # Use sorted tuple to avoid duplicate detection (A->B and B->A are the same cycle)
                cycle_key = tuple(sorted([node_a, node_b]))
                if cycle_key not in seen:
                    seen.add(cycle_key)
                    circular_refs.append([node_a, node_b, node_a])

    return circular_refs


def process_graphdict(relations_graphdict: Dict[str, Any]) -> Dict[str, Any]:
    """Remove module prefixes from graph dictionary keys and values.

    Args:
        relations_graphdict: Graph dictionary with module-prefixed names

    Returns:
        Processed dictionary with module prefixes removed
    """
    processed_dict = {}
    for key, value in relations_graphdict.items():
        processed_dict[get_no_module_name(key)] = relations_graphdict[key]
        processed_value = []
        for item in value:
            processed_value.append(get_no_module_name(item))
        processed_dict[get_no_module_name(key)] = processed_value
    return processed_dict


def get_no_module_name(node: str) -> Optional[str]:
    """Remove module prefix from resource name.

    Args:
        node: Resource name potentially with module prefix

    Returns:
        Resource name without module prefix
    """
    if not node:
        return
    if "module." in node:
        no_module_name = node.split(".")[-2] + "." + node.split(".")[-1]
    else:
        no_module_name = node
    return no_module_name


def extract_subfolder_from_repo(source_url: str) -> Tuple[str, str]:
    """Extract repo URL and subfolder from a string.

    Handles URLs like 'https://github.com/user/repo.git//code/02-one-server'.

    Args:
        source_url: Git repository URL potentially with subfolder

    Returns:
        Tuple of (repo_url, subfolder) - subfolder is empty string if none exists
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


def get_no_module_no_number_name(node: str) -> Optional[str]:
    """Remove module prefix and array indices from resource name.

    Args:
        node: Resource name with potential module prefix and indices

    Returns:
        Cleaned resource name
    """
    if not node:
        return
    if "module." in node:
        no_module_name = node.split(".")[-2] + "." + node.split(".")[-1]
    else:
        no_module_name = node
    no_module_name = no_module_name.split("[")[0]
    return no_module_name


def check_list_for_dash(connections: List[str]) -> bool:
    """Check if all items in list contain numbered suffix (~).

    Args:
        connections: List of connection strings

    Returns:
        True if all items have ~ suffix
    """
    has_dash = True
    for item in connections:
        if not "~" in item:
            has_dash = False
    return has_dash


def sort_graphdict(graphdict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Sort graph dictionary keys and connection lists.

    Args:
        graphdict: Graph dictionary to sort

    Returns:
        Sorted graph dictionary
    """
    for key in graphdict:
        graphdict[key].sort()
    return dict(sorted(graphdict.items()))


def url(string: str) -> str:
    """Add https:// protocol if missing from URL.

    Args:
        string: URL string

    Returns:
        URL with protocol
    """
    if string.count("://") == 0:
        return "https://" + string
    return string


def find_nth(string: str, substring: str, n: int) -> int:
    """Find nth occurrence of substring in string.

    Args:
        string: String to search
        substring: Substring to find
        n: Occurrence number (1-indexed)

    Returns:
        Index of nth occurrence
    """
    if n == 1:
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)


def unique_services(nodelist: List[str]) -> List[str]:
    """Extract unique service types from node list.

    Args:
        nodelist: List of resource names

    Returns:
        Sorted list of unique service types
    """
    service_list = []
    for item in nodelist:
        service = str(item.split(".")[0]).strip()
        service_list.append(service)
    return sorted(set(service_list))


def remove_numbered_suffix(s: str) -> str:
    """Remove numbered suffix (~N) from resource name.

    Args:
        s: Resource name potentially with suffix

    Returns:
        Resource name without suffix
    """
    return s.split("~")[0] if "~" in s else s


def find_between(
    text: str,
    begin: str,
    end: str,
    alternative: str = "",
    replace: bool = False,
    occurrence: int = 1,
) -> str:
    """Extract text between two delimiters.

    Args:
        text: Source text
        begin: Starting delimiter
        end: Ending delimiter
        alternative: Replacement text if replace=True
        replace: Whether to replace found text
        occurrence: Which occurrence to find

    Returns:
        Text between delimiters or modified text if replace=True
    """
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


def remove_duplicate_words(string: str) -> str:
    """Remove duplicate words from string.

    Args:
        string: Input string

    Returns:
        String with unique words only
    """
    words = string.split()
    unique_words = set(words)
    unique_words_list = list(unique_words)
    return " ".join(unique_words_list)


# 'aws_lb_target_group_attachment.mytg1["1"][1]'


def remove_brackets_and_numbers(input_string: str) -> str:
    """Remove square brackets and their contents from string.

    Args:
        input_string: String with brackets

    Returns:
        String without brackets or their contents
    """
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


def replace_variables(
    vartext: str,
    filename: Union[str, List[str]],
    all_variables: Dict[str, Any],
    quotes: bool = False,
) -> Optional[str]:
    """Replace Terraform variable references with actual values.

    Args:
        vartext: Text containing variable references
        filename: Source filename for error messages
        all_variables: Dictionary of variable values
        quotes: Whether to add quotes (unused)

    Returns:
        Text with variables replaced
    """
    # Replace Variables found within resource meta data
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


def output_log(tfdata: Dict[str, Any]) -> None:
    """Output parsed Terraform data to console.

    Args:
        tfdata: Terraform data dictionary
    """
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
    """Retrieve a Terraform variable value from environment or variables dictionary.

    Searches for variable values in the following order:
    1. Environment variable with TF_VAR_ prefix
    2. Exact match in all_variables_dict
    3. Case-insensitive match in all_variables_dict

    Args:
        variable_name: Name of the variable to retrieve (without 'var.' prefix)
        all_variables_dict: Dictionary containing all defined Terraform variables

    Returns:
        str: Variable value if found, "NOTFOUND" otherwise
    """
    # See if variable exists as an environment variable
    env_var = os.getenv("TF_VAR_" + variable_name)
    if env_var:
        return env_var

    # Check if it exists in all variables dict
    if variable_name in all_variables_dict:
        return all_variables_dict[variable_name]

    # Check if same variable with different casing exists
    for var in all_variables_dict:
        if var.lower() == variable_name.lower():
            return all_variables_dict[var]

    return "NOTFOUND"


def find_common_elements(dict_of_lists: dict, keyword: str) -> list:
    """Find shared elements between dictionary lists where keys contain a keyword.

    Identifies elements that appear in multiple lists, but only when both keys
    contain the specified keyword. Useful for finding duplicate connections
    between similar resources (e.g., security groups).

    Args:
        dict_of_lists: Dictionary where values are lists of elements
        keyword: String that must be present in both keys to check for common elements

    Returns:
        list: List of tuples (key1, key2, common_element) for each shared element
    """
    results = []

    # Compare each pair of keys in the dictionary
    for key1, list1 in dict_of_lists.items():
        for key2, list2 in dict_of_lists.items():
            # Skip comparing a key with itself
            if key1 != key2:
                # Find elements that exist in both lists
                for element in list1:
                    if element in list2 and keyword in key1 and keyword in key2:
                        results.append((key1, key2, element))

    return results


def find_shared_security_groups(graphdict: dict) -> list:
    """Find all keys where the same security group appears in multiple connection lists"""
    sg_to_keys = {}

    # Build mapping of security groups to keys that reference them
    for key, connections in graphdict.items():
        for connection in connections:
            if "aws_security_group" in connection:
                if connection not in sg_to_keys:
                    sg_to_keys[connection] = []
                sg_to_keys[connection].append(key)

    # Return keys where security groups are shared (appear in multiple lists)
    return [key for sg, keys in sg_to_keys.items() if len(keys) > 1 for key in keys]


def find_resource_references(
    searchdict: Dict[str, List[str]], target_resource: str
) -> Dict[str, List[str]]:
    """Find all dictionary entries that reference a target resource.

    Args:
        searchdict: Dictionary to search
        target_resource: Resource name to find

    Returns:
        Dictionary of entries containing the target resource
    """
    final_dict = dict()
    for item in searchdict:
        if target_resource in searchdict[item]:
            final_dict[item] = searchdict[item]
        for listitem in searchdict[item]:
            if target_resource in listitem:
                final_dict[item] = searchdict[item]
    return final_dict


def find_resource_containing(search_list: List[str], keyword: str) -> Union[str, bool]:
    """Find first resource in list containing keyword.

    Args:
        search_list: List of resource names
        keyword: Keyword to search for

    Returns:
        First matching resource name or False
    """
    for actual_name in search_list:
        if keyword in actual_name:
            found = actual_name
            return found
    return False


def find_all_resources_containing(
    search_list: List[str], keyword: str
) -> Union[List[str], bool]:
    """Find all resources in list containing keyword.

    Args:
        search_list: List of resource names
        keyword: Keyword to search for

    Returns:
        List of matching resource names or False
    """
    foundlist = list()
    for actual_name in search_list:
        if keyword in actual_name:
            foundlist.append(actual_name)
    if foundlist:
        return foundlist
    else:
        return False


def append_dictlist(thelist: List[Any], new_item: Any) -> List[Any]:
    """Append item to list and return new list.

    Args:
        thelist: Original list
        new_item: Item to append

    Returns:
        New list with item appended
    """
    new_list = list(thelist)
    new_list.append(new_item)
    return new_list


def remove_recursive(graphdict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Debug function to print recursive references.

    Args:
        graphdict: Graph dictionary

    Returns:
        Unchanged graph dictionary
    """
    for node, connections in graphdict.items():
        if node in connections:
            print(node)
        for c in connections:
            if graphdict.get(c):
                if node in graphdict.get(c):
                    print(node, c)
    return graphdict


def check_variant(resource: str, metadata: Dict[str, Any]) -> Union[str, bool]:
    """Check if resource has a variant suffix based on metadata.

    Args:
        resource: Resource name
        metadata: Resource metadata

    Returns:
        Variant name or False
    """
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


def find_replace(find: str, replace: str, string: str) -> str:
    """Replace first occurrence of substring.

    Args:
        find: Substring to find
        replace: Replacement string
        string: Source string

    Returns:
        Modified string
    """
    original_string = string
    string = string.replace(find, replace, 1)
    return string


def list_of_parent_nodes(
    graphdict: Dict[str, List[str]], nodelist: List[str]
) -> List[str]:
    """Get list of parent nodes for given node list.

    Args:
        graphdict: Graph dictionary
        nodelist: List of nodes to find parents for

    Returns:
        List of parent node names without numbered suffixes
    """
    parent_list = list()
    for node in nodelist:
        parent_nodes = list_of_parents(graphdict, node)
        for p in parent_nodes:
            if "~" not in p:
                parent_list.append(p)
    return parent_list


def list_of_parents(searchdict: Dict[str, Any], target: str) -> List[str]:
    """Find all keys that reference the target in their values.

    Args:
        searchdict: Dictionary to search
        target: Target value to find

    Returns:
        List of keys that reference the target
    """
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


def any_parent_has_count(tfdata: Dict[str, Any], target_resource: str) -> bool:
    """Check if any parent resource has count/for_each attribute.

    Args:
        tfdata: Terraform data dictionary
        target_resource: Resource to check parents for

    Returns:
        True if any parent has count attribute
    """
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


def consolidated_node_check(resource_type: str) -> Union[str, bool]:
    """Check if resource should be consolidated into a standard node.

    Args:
        resource_type: Resource type to check

    Returns:
        Consolidated node name or False
    """
    for checknode in CONSOLIDATED_NODES:
        prefix = str(list(checknode.keys())[0])
        if get_no_module_name(resource_type).startswith(prefix) and resource_type:
            return checknode[prefix]["resource_name"]
    return False


def remove_all_items(test_list: List[str], item: str) -> List[str]:
    """Remove all occurrences of item from list.

    Args:
        test_list: List to filter
        item: Item to remove

    Returns:
        Filtered list
    """
    # using filter() + __ne__ to perform the task
    # using filter() + __ne__ to perform the task
    res = list(filter((item).__ne__, test_list))
    return res


def list_of_dictkeys_containing(
    searchdict: Dict[str, Any], target_keyword: str
) -> List[str]:
    """Find all dictionary keys containing a keyword.

    Args:
        searchdict: Dictionary to search
        target_keyword: Keyword to find in keys

    Returns:
        List of matching keys
    """
    final_list = list()
    for item in searchdict:
        if target_keyword in item:
            final_list.append(item)
    return final_list


def cleanup_curlies(text: str) -> str:
    """Remove curly braces and dollar signs from text.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    text = str(text)
    for ch in ["$", "{", "}"]:
        if ch in text:
            text = text.replace(ch, "")
    return text.strip()


def strip_var_curlies(s: str) -> str:
    """Remove Terraform variable syntax ${} from string.

    Args:
        s: String with variable syntax

    Returns:
        String with variable syntax removed
    """
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


def cleanup(text: str) -> str:
    """Remove special characters from text.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
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


def extract_terraform_resource(text: str) -> List[str]:
    """Extract Terraform resource references from string.

    Args:
        text: Text containing resource references

    Returns:
        List of resource references found
    """
    import re

    results = []

    # Pattern for aws_resource.name (with or without quotes/spaces)
    aws_pattern = r"(aws_\w+\.\w+)"
    aws_matches = re.findall(aws_pattern, text)
    results.extend(aws_matches)

    # Pattern for module.name.aws_resource.name[*].id
    module_pattern = r"module\.(\w+)\.(aws_\w+)\.(\w+)(?:\[\*?\])?(?:\.id)?"
    module_matches = re.findall(module_pattern, text)
    for match in module_matches:
        results.append(f"module.{match[0]}.{match[1]}.{match[2]}")

    return results


def remove_terraform_functions(text: str) -> str:
    """Remove Terraform functions from ${} expressions.

    Keeps only the inner content of function calls.

    Args:
        text: Text with Terraform function calls

    Returns:
        Text with functions removed
    """
    pattern = r"\$\{([^}]+)\}"

    def process_expression(match):
        content = match.group(1)
        # Common Terraform functions to remove
        functions = [
            "try",
            "coalesce",
            "lookup",
            "element",
            "length",
            "join",
            "split",
            "format",
            "formatlist",
        ]

        for func in functions:
            func_pattern = rf"{func}\s*\(\s*([^,)]+)(?:\s*,\s*[^)]+)?\s*\)"
            func_match = re.search(func_pattern, content)
            if func_match:
                return func_match.group(1)

        return content

    return re.sub(pattern, process_expression, text)
