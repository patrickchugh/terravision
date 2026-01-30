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

import modules.config_loader as config_loader
import modules.helpers as helpers
from modules.provider_detector import PROVIDER_PREFIXES
from modules.config_loader import load_config
from modules.provider_detector import get_provider_for_resource


def _get_provider_config_constants(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Load provider-specific configuration constants from tfdata.

    Args:
        tfdata: Terraform data dictionary with provider_detection

    Returns:
        Dictionary with provider-specific constants
    """
    from modules.provider_detector import get_primary_provider_or_default

    provider = get_primary_provider_or_default(tfdata)
    config = config_loader.load_config(provider)
    provider_upper = provider.upper()

    return {
        "REVERSE_ARROW_LIST": getattr(
            config, f"{provider_upper}_REVERSE_ARROW_LIST", []
        ),
        "IMPLIED_CONNECTIONS": getattr(
            config, f"{provider_upper}_IMPLIED_CONNECTIONS", {}
        ),
        "GROUP_NODES": getattr(config, f"{provider_upper}_GROUP_NODES", []),
        "CONSOLIDATED_NODES": getattr(
            config, f"{provider_upper}_CONSOLIDATED_NODES", []
        ),
        "NODE_VARIANTS": getattr(config, f"{provider_upper}_NODE_VARIANTS", {}),
        "SPECIAL_RESOURCES": getattr(config, f"{provider_upper}_SPECIAL_RESOURCES", {}),
        "ACRONYMS_LIST": getattr(config, f"{provider_upper}_ACRONYMS_LIST", []),
        "NAME_REPLACEMENTS": getattr(config, f"{provider_upper}_NAME_REPLACEMENTS", {}),
    }


# List of dictionary sections to output in log
output_sections = ["locals", "module", "resource", "data", "output"]


def extract_json_from_string(text: str) -> dict:
    """Extract JSON object from text, handling code blocks and raw JSON."""
    # Try code block with json marker
    match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try code block without marker
    match = re.search(r"```\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding raw JSON object
    match = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

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
    with open(Path.cwd() / "tfdata.json", "w") as file:
        json.dump(tfdata, file, indent=4)
    out_path = (Path.cwd() / "tfdata.json").resolve()
    click.echo(
        click.style(
            f"\nINFO: Debug flag used. Current state has been written to {out_path}\n",
            fg="yellow",
            bold=True,
        )
    )


def remove_recursive_links(tfdata: dict):
    """Remove 2-node circular references from the graph.

    Detects and removes bidirectional links between two nodes (A->B and B->A)
    to prevent rendering issues. Longer cycles (A->B->C->A) are preserved.

    For consolidated nodes (API Gateway, CloudWatch, etc. that are merged from
    multiple sub-resources), prefers to keep their OUTGOING connections by
    removing the incoming connection from the other node instead.

    Args:
        tfdata: Dictionary containing 'graphdict' with node relationships

    Returns:
        dict: Updated tfdata with circular references removed from graphdict
    """
    graphdict = tfdata.get("graphdict")
    circular = find_circular_refs(graphdict)

    # Load consolidated node names from config
    config_constants = _get_provider_config_constants(tfdata)
    consolidated_nodes = config_constants.get("CONSOLIDATED_NODES", [])

    # Build set of consolidated node resource names (the merged names like "aws_api_gateway_integration.gateway")
    consolidated_names = set()
    for consolidated in consolidated_nodes:
        for prefix, config in consolidated.items():
            consolidated_names.add(config.get("resource_name", ""))

    def is_consolidated_node(node: str) -> bool:
        """Check if node is a consolidated node (the merged target, not a source)."""
        return node in consolidated_names

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

            # For consolidated nodes, keep their outgoing connections
            # (remove incoming connection from other node instead)
            node_a_consolidated = is_consolidated_node(node_a)
            node_b_consolidated = is_consolidated_node(node_b)

            if node_a_consolidated and not node_b_consolidated:
                # node_a is consolidated, keep its outgoing, remove node_b's connection to it
                if node_a in graphdict.get(node_b, []):
                    graphdict[node_b].remove(node_a)
                    click.echo(
                        click.style(
                            f"  Removed link from {node_b} to {node_a} (keeping consolidated node outgoing)",
                            fg="white",
                        )
                    )
            elif node_b_consolidated and not node_a_consolidated:
                # node_b is consolidated, keep its outgoing, remove node_a's connection to it
                if node_b in graphdict.get(node_a, []):
                    graphdict[node_a].remove(node_b)
                    click.echo(
                        click.style(
                            f"  Removed link from {node_a} to {node_b} (keeping consolidated node outgoing)",
                            fg="white",
                        )
                    )
            else:
                # Neither or both consolidated - default behavior
                if node_b in graphdict.get(node_a, []):
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
    """Remove numbered suffix (~N) or [N] from resource name.

    Args:
        s: Resource name potentially with suffix

    Returns:
        Resource name without suffix
    """
    s = s.split("~")[0] if "~" in s else s
    return re.sub(r"\[\d+\]", "", s)


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


def pretty_name(name: str, show_title=True, is_group=False) -> str:
    """
    Generate clean, human-readable labels for Terraform resource names.

    Examples:
      - aws_cloudfront_distribution.this -> "Cloudfront Distribution"
      - aws_lambda_function.cache_reader -> "Lambda Function - Cache Reader"
      - aws_subnet.cache_a                -> "Subnet - Cache A"
      - aws_efs_mount_target.this         -> "EFS Mount Target"
      - aws_alb.elb~1                     -> "App Load Balancer - ELB"
      - azurerm_virtual_machine.vm        -> "Virtual Machine - VM"
      - google_compute_instance.web       -> "Compute Instance - Web"

    Args:
        name: The Terraform resource name to format
        show_title: Whether to include instance name after dash
        is_group: If True, skip truncation (for group/cluster labels)

    Trimming: max output length is 40 chars with a soft line-break
    inserted after ~21 characters when the label is longer than that.
    Group labels (is_group=True) are never truncated.
    """
    if not name:
        return ""

    skip_keywords = {"null_", "random", "time_sleep", "empty", "blank"}
    if any(k in name for k in skip_keywords):
        return " "

    # Get provider - if unknown, return simple formatted name without config
    provider = get_provider_for_resource(name)
    if provider == "unknown":
        # For non-cloud resources, return a simple formatted name
        simple_name = name.split(".")[-1] if "." in name else name
        return simple_name.replace("_", " ").title()

    # Load provider-specific config for cloud resources
    provider = provider.upper()
    config_constants = load_config(provider)
    NAME_REPLACEMENTS = getattr(config_constants, f"{provider}_NAME_REPLACEMENTS")
    ACRONYMS_LIST = getattr(config_constants, f"{provider}_ACRONYMS_LIST")

    # normalize and remove module prefixes / numbered suffixes and array indices

    name = name.replace("tv_", "")
    for prefix in PROVIDER_PREFIXES.keys():
        name = name.replace(prefix, "")

    name = get_no_module_no_number_name(name)
    name = name.split("~", 1)[0]
    name = name.replace("-", "_")

    m = re.match(r"^([a-z0-9_]+)(?:\.([a-z0-9_]+))?$", name)
    if not m:
        return (name or "") if is_group else (name or "")[:40]

    resource_type = m.group(1) or ""
    instance_raw = (m.group(2) or "").strip()

    # placeholders we don't want as instance labels
    placeholders = {"this", "resource"}
    if instance_raw in placeholders:
        instance_raw = ""

    def _soft_break(s: str, soft_at: int, max_len: int) -> str:
        """Insert a soft newline after the nearest word boundary after soft_at.
        Do not cut a word. If no boundary found after soft_at, try before;
        if none, return truncated string without introducing a newline."""
        if len(s) <= soft_at:
            return s if len(s) <= max_len else s[:max_len]
        # prefer first space after soft_at
        after = s.find(" ", soft_at)
        if after != -1 and after <= max_len:
            br = after
        else:
            # fallback to last space before soft_at
            before = s.rfind(" ", 0, soft_at)
            if before != -1:
                br = before
            else:
                # no safe break available; return truncated string
                return s[:max_len] if len(s) > max_len else s
        # insert newline at the chosen space position
        return s[:br] + "\n" + s[br + 1 :][: max_len - (1 if br < max_len else 0)]

    # Special-case: availability zone formatting
    # Input example: aws_az.availability_zone_us_east_1a~1
    # Desired output: "Availability Zone US East 1a"
    if resource_type == "az" and instance_raw.startswith("availability_zone_"):
        zone = instance_raw[len("availability_zone_") :]
        parts = [p for p in zone.split("_") if p]
        acronyms = {a.lower(): a for a in ACRONYMS_LIST if a}
        formatted_parts = []
        for p in parts:
            key = re.sub(r"[^\w]", "", p).lower()
            if not key:
                continue
            if key in acronyms:
                formatted_parts.append(acronyms[key].upper())
                continue
            if key.isalpha() and len(key) == 2:
                formatted_parts.append(key.upper())
                continue
            mpart = re.match(r"^(\d+)([a-zA-Z])$", p)
            if mpart:
                formatted_parts.append(f"{mpart.group(1)}{mpart.group(2).lower()}")
                continue
            formatted_parts.append(p.title())
        region_part = " ".join(formatted_parts)
        az_label = f"Availability Zone {region_part}"
        # soft-break and truncate to new limits (skip for groups)
        if not is_group:
            az_label = _soft_break(az_label, soft_at=21, max_len=40)
        return az_label

    # Prefer a full replacement for the whole resource_type (e.g. alb -> application_load_balancer)
    left_raw = NAME_REPLACEMENTS.get(resource_type, "")
    if left_raw:
        if instance_raw and instance_raw.replace("_", "") == resource_type:
            instance_raw = ""
    else:
        # split resource_type into service + suffix (lambda_function -> lambda + function)
        parts = resource_type.split("_")
        servicename = parts[0] if parts else resource_type
        servicename_repl = NAME_REPLACEMENTS.get(servicename, servicename)
        type_suffix = " ".join(parts[1:]) if len(parts) > 1 else ""
        left_raw = (
            f"{servicename_repl} {type_suffix}".strip()
            if type_suffix
            else servicename_repl
        )
        # avoid duplication when instance matches service/name replacement
        if instance_raw and (
            instance_raw.replace("_", "").lower() == servicename.lower()
            or instance_raw.replace("_", "").lower()
            == str(servicename_repl).replace(" ", "").lower()
        ):
            instance_raw = ""

    left_part = (left_raw or "").replace("_", " ").strip()
    right_part = (instance_raw or "").replace("_", " ").strip()

    if show_title and right_part:
        combined = f"{left_part} - {right_part}"
    else:
        combined = left_part

    combined = re.sub(r"\s+", " ", combined).strip()

    # Title-case while preserving acronyms
    acronyms = {a.lower(): a for a in ACRONYMS_LIST if a}
    words = combined.split(" ")
    processed_words = []
    seen = set()
    for w in words:
        key = re.sub(r"[^\w]", "", w).lower()
        if not key:
            continue
        if key in acronyms:
            out = acronyms[key].upper()
        else:
            out = w.title()
        if out.lower() not in seen:
            seen.add(out.lower())
            processed_words.append(out)

    final = " ".join(processed_words).strip()

    # Soft break after ~21 chars and increase max length to 40 (skip for groups)
    if not is_group:
        final = _soft_break(final, soft_at=21, max_len=40)

    return final


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

    Checks for duplicates before appending to prevent duplicate connections.

    Args:
        thelist: Original list
        new_item: Item to append

    Returns:
        New list with item appended (no duplicates)
    """
    new_list = list(thelist)
    if new_item not in new_list:
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


def check_variant(
    resource: str, metadata: Dict[str, Any], tfdata: Dict[str, Any]
) -> Union[str, bool]:
    """Check if resource has a variant suffix based on metadata.

    Args:
        resource: Resource name
        metadata: Resource metadata
        tfdata: Terraform data dictionary (required for provider-specific config)

    Returns:
        Variant name or False

    Note:
        This function now REQUIRES tfdata to load provider-specific NODE_VARIANTS.
        It no longer uses module-level defaults.
    """
    # Load provider-specific constants
    config_constants = _get_provider_config_constants(tfdata)
    NODE_VARIANTS = config_constants["NODE_VARIANTS"]

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


def list_of_parents(
    searchdict: Dict[str, Any], target: str, exactmatch=False
) -> List[str]:
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
                    not exactmatch
                    and helpers.get_no_module_name(item).startswith(
                        helpers.get_no_module_name(target)
                    )
                    and key not in final_list
                ):
                    final_list.append(key)
                if (
                    exactmatch
                    and helpers.get_no_module_name(item)
                    == helpers.get_no_module_name(target)
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


def consolidated_node_check(
    resource_type: str, tfdata: Dict[str, Any]
) -> Union[str, bool]:
    """Check if resource should be consolidated into a standard node.

    Args:
        resource_type: Resource type to check
        tfdata: Terraform data dictionary (required for provider-specific config)

    Returns:
        Consolidated node name or False

    Note:
        This function now REQUIRES tfdata to load provider-specific CONSOLIDATED_NODES.
        It no longer uses module-level defaults.
    """
    # Load provider-specific constants
    config_constants = _get_provider_config_constants(tfdata)
    CONSOLIDATED_NODES = config_constants["CONSOLIDATED_NODES"]

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

    # Pattern for Azure resources (azurerm_, azuread_, azapi_)
    azure_pattern = r"((?:azurerm|azuread|azapi)_\w+\.\w+)"
    azure_matches = re.findall(azure_pattern, text)
    results.extend(azure_matches)

    # Pattern for GCP resources
    gcp_pattern = r"(google_\w+\.\w+)"
    gcp_matches = re.findall(gcp_pattern, text)
    results.extend(gcp_matches)

    # Pattern for module.name.resource.name[*].id
    module_pattern = r"module\.(\w+)\.(\w+_\w+)\.(\w+)(?:\[\*?\])?(?:\.id)?"
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


def validate_no_shared_connections(
    graphdict: Dict[str, List[str]], tfdata: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate that no two group nodes share connections to the same resource.

    This is critical for graphviz rendering. When multiple groups (subnets, AZs, etc.)
    point to the same resource, it creates rendering issues. Resources should be
    expanded into numbered instances (~1, ~2, etc.) to match their parent groups.

    However, some resources are INTENTIONALLY shared across groups:
    - Subnet groups (ElastiCache, RDS) - span multiple subnets by design
    - Route table associations - connect route tables to subnets
    - Non-drawable resources (no icon) - don't appear in visual diagram

    Args:
        graphdict: Graph dictionary mapping nodes to their connections
        tfdata: Terraform data dictionary with provider config

    Returns:
        Tuple of (is_valid, list_of_errors)
        - is_valid: True if no shared connections found, False otherwise
        - list_of_errors: List of error messages describing violations

    Example violations:
        - aws_subnet.a → aws_instance.web
        - aws_subnet.b → aws_instance.web
        Result: ERROR - aws_instance.web should be aws_instance.web~1, aws_instance.web~2
    """
    config = _get_provider_config_constants(tfdata)
    GROUP_NODES = config.get("GROUP_NODES", [])

    # Resources that are INTENTIONALLY shared across groups (cross-group by design)
    INTENTIONAL_SHARED_RESOURCES = [
        "_subnet_group",  # aws_elasticache_subnet_group, aws_db_subnet_group, etc.
        "_route_table_association",  # Route table associations
        "_nat_gateway",  # NAT gateways can be shared
        "_internet_gateway",  # Internet gateways span VPC
        "_route_table",  # Route tables can be shared
    ]

    # Resources that are typically non-drawable (no icon/not visually rendered)
    NON_DRAWABLE_RESOURCES = [
        "aws_appautoscaling_policy",
        "aws_appautoscaling_target",
        "aws_iam_role_policy_attachment",
        "aws_iam_policy",
        "aws_cloudwatch_metric_alarm",
        "aws_route_table_association",
    ]

    errors = []

    # Build mapping of resource → list of parent groups
    resource_to_parents = {}

    for node, connections in graphdict.items():
        # Check if this node is a group node
        is_group = any(group_type in node for group_type in GROUP_NODES)
        if not is_group:
            continue

        # For each connection from this group
        for connection in connections:
            # Skip if connection itself is a group or special node
            if any(group_type in connection for group_type in GROUP_NODES):
                continue
            if connection.startswith("tv_") or connection.startswith("aws_group."):
                continue

            # Skip intentional shared resources (cross-group by design)
            if any(
                shared_type in connection
                for shared_type in INTENTIONAL_SHARED_RESOURCES
            ):
                continue

            # Skip non-drawable resources (not visually rendered)
            if any(
                non_drawable in connection for non_drawable in NON_DRAWABLE_RESOURCES
            ):
                continue

            # Track which groups point to this connection
            if connection not in resource_to_parents:
                resource_to_parents[connection] = []
            resource_to_parents[connection].append(node)

    # Check for violations: any resource with multiple parent groups
    for resource, parent_groups in resource_to_parents.items():
        if len(parent_groups) > 1:
            # Check if resource already has numbered instances (ends with ~N)
            if "~" not in resource:
                errors.append(
                    f"SHARED CONNECTION VIOLATION: '{resource}' is connected from multiple groups: {parent_groups}. "
                    f"This causes graphviz rendering issues. Resource should be expanded into numbered instances "
                    f"({resource}~1, {resource}~2, etc.) to match each parent group."
                )

    return (len(errors) == 0, errors)


def validate_graphdict(
    graphdict: Dict[str, List[str]], tfdata: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Run all validation checks on graphdict before rendering.

    This function aggregates all validation checks to catch common issues
    that cause rendering problems or incorrect diagrams.

    Args:
        graphdict: Graph dictionary mapping nodes to their connections
        tfdata: Terraform data dictionary

    Returns:
        Tuple of (is_valid, list_of_all_errors)
    """
    all_errors = []

    # Check 1: No shared connections between groups
    valid, errors = validate_no_shared_connections(graphdict, tfdata)
    if not valid:
        all_errors.extend(errors)

    # Future checks can be added here:
    # - Check for circular dependencies
    # - Check for orphaned nodes
    # - Check for invalid node names
    # - etc.

    return (len(all_errors) == 0, all_errors)
