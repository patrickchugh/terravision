"""Graph maker module for TerraVision.

This module constructs the resource dependency graph from parsed Terraform data.
It handles relationship detection, node consolidation, resource variants, and
multiple resource instances (count/for_each). The graph structure is used for
diagram generation.
"""

import copy
from typing import Dict, List, Any, Tuple, Generator, Optional, Set
import re
import click
import modules.config_loader as config_loader
import modules.helpers as helpers
import modules.resource_handlers as resource_handlers
from modules.provider_detector import get_primary_provider_or_default
from modules.resource_transformers import apply_transformation_pipeline


def extract_resource_references(attribute_value: Any, pattern: str) -> List[str]:
    """Extract resource references from attribute value using regex pattern.

    Args:
        attribute_value: The attribute value (list, string, etc.)
        pattern: Regex pattern to extract references

    Returns:
        List of extracted resource references
    """
    references = []

    if isinstance(attribute_value, list):
        for item in attribute_value:
            if isinstance(item, str):
                matches = re.findall(pattern, item)
                references.extend(matches)
    elif isinstance(attribute_value, str):
        matches = re.findall(pattern, attribute_value)
        references.extend(matches)

    return references


def find_matching_node_in_graphdict(
    original_resource: str,
    graphdict: Dict[str, List[str]],
    provider_config: Dict[str, Any],
) -> List[str]:
    """Find matching nodes in graphdict after consolidation.

    Handles resource renaming during consolidation (e.g., aws_lb.main -> aws_alb.elb).

    Args:
        original_resource: Original resource name from all_resource
        graphdict: Current graphdict (post-consolidation)
        provider_config: Provider-specific configuration

    Returns:
        List of matching node names in graphdict
    """
    matching_nodes = []
    resource_type = original_resource.split(".")[0]

    # Get list of resource types that might be consolidated together
    # For AWS: aws_lb, aws_alb, aws_nlb are often consolidated
    consolidated_types = provider_config.get("resource_types", [resource_type])

    for node in graphdict.keys():
        if "~" in node:  # Skip already-numbered nodes
            continue

        node_type = node.split(".")[0]

        # Check if node type matches or is a consolidated variant
        if node_type == resource_type or node_type in consolidated_types:
            matching_nodes.append(node)

    return matching_nodes


def _check_instance_for_multi_refs(
    instance_data: Dict[str, Any],
    pattern: Dict[str, Any],
    resource_key: str,
    resources_to_expand: Dict[str, tuple],
) -> None:
    """Check a resource instance for multi-reference trigger attributes.

    If trigger attributes contain multiple references, marks the resource
    for expansion and collects associated resources.

    Args:
        instance_data: The resource instance attributes
        pattern: The matching multi-instance pattern config
        resource_key: Fully qualified resource key (type.name)
        resources_to_expand: Dict to update with discovered expansions (mutated)
    """
    for trigger_attr in pattern["trigger_attributes"]:
        attr_value = instance_data.get(trigger_attr)
        if not attr_value:
            continue

        references = extract_resource_references(
            attr_value, pattern["resource_pattern"]
        )
        if len(references) <= 1:
            continue

        if resource_key not in resources_to_expand:
            resources_to_expand[resource_key] = (len(references), set())

        for assoc_attr in pattern["also_expand_attributes"]:
            assoc_value = instance_data.get(assoc_attr)
            if assoc_value:
                assoc_refs = extract_resource_references(
                    assoc_value, pattern["resource_pattern"]
                )
                resources_to_expand[resource_key][1].update(assoc_refs)


def _scan_resources_for_patterns(
    all_resource: Dict[str, Any], patterns: List[Dict[str, Any]]
) -> Dict[str, tuple]:
    """Scan all Terraform resources for multi-instance patterns.

    Args:
        all_resource: Dict of terraform file -> resource blocks
        patterns: List of multi-instance pattern configurations

    Returns:
        Dict mapping resource_key -> (count, set_of_associated_resources)
    """
    resources_to_expand: Dict[str, tuple[int, Set[str]]] = {}

    for resources in all_resource.values():
        if not isinstance(resources, list):
            continue

        for resource_block in resources:
            for resource_type, instances in resource_block.items():
                if not isinstance(instances, dict):
                    continue

                matching_patterns = [
                    p for p in patterns if resource_type in p["resource_types"]
                ]
                for pattern in matching_patterns:
                    for instance_name, instance_data in instances.items():
                        resource_key = f"{resource_type}.{instance_name}"
                        _check_instance_for_multi_refs(
                            instance_data, pattern, resource_key, resources_to_expand
                        )

    return resources_to_expand


def _find_associated_node(
    assoc_resource: str,
    graphdict: Dict[str, Any],
    meta_data: Dict[str, Any],
    count: int,
) -> None:
    """Find and set count for a single associated resource in the graph.

    Args:
        assoc_resource: The associated resource reference to find
        graphdict: The graph dictionary
        meta_data: Resource metadata (mutated to set count)
        count: The count to set
    """
    assoc_type = assoc_resource.split(".")[0]
    assoc_base = assoc_resource.split(".")[1] if "." in assoc_resource else ""
    if not assoc_base:
        return

    for node in graphdict.keys():
        if "~" in node:
            continue

        node_type = node.split(".")[0]
        node_base = node.split(".")[1] if "." in node else ""

        type_matches = (
            node_type == assoc_type
            or node_type in assoc_type
            or assoc_type in node_type
        )
        name_matches = assoc_base in node_base or node_base in assoc_base

        if name_matches and type_matches:
            if node not in meta_data:
                meta_data[node] = {}
            if not meta_data[node].get("count"):
                meta_data[node]["count"] = count


def _apply_counts_to_graph(
    resources_to_expand: Dict[str, tuple],
    patterns: List[Dict[str, Any]],
    graphdict: Dict[str, Any],
    meta_data: Dict[str, Any],
) -> None:
    """Apply detected counts to graph nodes and their associated resources.

    Args:
        resources_to_expand: Dict mapping resource_key -> (count, associated_set)
        patterns: Multi-instance pattern configurations
        graphdict: The graph dictionary
        meta_data: Resource metadata (mutated to set counts)
    """
    for resource_key, (count, associated_resources) in resources_to_expand.items():
        resource_type = resource_key.split(".")[0]

        matching_pattern = next(
            (p for p in patterns if resource_type in p["resource_types"]), {}
        )

        matching_nodes = find_matching_node_in_graphdict(
            resource_key, graphdict, matching_pattern
        )

        for node in matching_nodes:
            if node not in meta_data:
                meta_data[node] = {}
            if not meta_data[node].get("count"):
                meta_data[node]["count"] = count

        for assoc_resource in associated_resources:
            _find_associated_node(assoc_resource, graphdict, meta_data, count)


def detect_and_set_counts(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect multi-instance resources and set synthetic count attributes.

    Uses configuration-driven patterns to detect resources across all cloud providers
    that should be expanded into numbered instances.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with count attributes set for detected resources
    """
    primary_provider = get_primary_provider_or_default(tfdata)
    config = _get_provider_config(tfdata)
    pattern_attr = f"{primary_provider.upper()}_MULTI_INSTANCE_PATTERNS"
    patterns = getattr(config, pattern_attr, [])

    if not patterns:
        return tfdata

    resources_to_expand = _scan_resources_for_patterns(
        tfdata.get("all_resource", {}), patterns
    )

    _apply_counts_to_graph(
        resources_to_expand,
        patterns,
        tfdata.get("graphdict", {}),
        tfdata.get("meta_data", {}),
    )

    return tfdata


def _get_provider_config(tfdata: Dict[str, Any]):
    """Get provider-specific configuration based on tfdata.

    Args:
        tfdata: Terraform data dictionary with provider_detection

    Returns:
        Provider-specific config module
    """
    provider = get_primary_provider_or_default(tfdata)
    return config_loader.load_config(provider)


def _load_config_constants(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Load provider-specific configuration constants.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Dictionary with provider-specific constants
    """
    config = _get_provider_config(tfdata)
    provider = get_primary_provider_or_default(tfdata)
    provider_upper = provider.upper()

    # Load all constants from config that match provider prefix
    constants = {}
    for attr_name in dir(config):
        if attr_name.startswith(f"{provider_upper}_") and not attr_name.startswith("_"):
            # Remove provider prefix from key name
            key_name = attr_name.replace(f"{provider_upper}_", "")
            constants[key_name] = getattr(config, attr_name)

    return constants


def reverse_relations(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse connection directions for specific resource types.

    Adjusts arrow directions in the graph based on FORCED_DEST and FORCED_ORIGIN
    configuration to ensure logical flow in the diagram.

    Args:
        tfdata: Terraform data dictionary with graphdict

    Returns:
        Updated tfdata with reversed connections
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    FORCED_DEST = constants["FORCED_DEST"]
    FORCED_ORIGIN = constants["FORCED_ORIGIN"]
    AUTO_ANNOTATIONS = constants["AUTO_ANNOTATIONS"]

    for n, connections in dict(tfdata["graphdict"]).items():
        node = helpers.get_no_module_name(n)
        reverse_dest = len([s for s in FORCED_DEST if node.startswith(s)]) > 0

        for c in list(connections):
            # Reverse if node is a forced destination
            if reverse_dest:
                if not tfdata["graphdict"].get(c):
                    tfdata["graphdict"][c] = list()
                if n not in tfdata["graphdict"][c]:
                    tfdata["graphdict"][c].append(n)
                tfdata["graphdict"][n].remove(c)

            # Reverse if connection is a forced origin
            # Skip reversal for synthetic grouping nodes (tv_ prefix) - these are
            # TerraVision-generated hierarchy nodes that should contain their children
            reverse_origin = (
                len(
                    [
                        s
                        for s in FORCED_ORIGIN
                        if helpers.get_no_module_name(c).startswith(s)
                        and node.split(".")[0] not in str(AUTO_ANNOTATIONS)
                        and not node.startswith(
                            "tv_"
                        )  # Don't reverse synthetic group containment
                    ]
                )
                > 0
            )
            if reverse_origin:
                if n not in tfdata["graphdict"][c]:
                    tfdata["graphdict"][c].append(n)
                tfdata["graphdict"][node].remove(c)

    return tfdata


def _find_implied_connections(
    param: str, nodes: List[str], IMPLIED_CONNECTIONS: Dict
) -> List[str]:
    """Find implied connections based on keywords.

    Args:
        param: Parameter value to search for keywords
        nodes: List of all resource nodes
        IMPLIED_CONNECTIONS: Dictionary of implied connection keywords

    Returns:
        List of matching resource names from implied connections
    """
    matching = []
    # Check for implied connections based on keywords
    found_connection = list({s for s in IMPLIED_CONNECTIONS.keys() if s in str(param)})
    if found_connection:
        for n in nodes:
            if helpers.get_no_module_name(n).startswith(
                IMPLIED_CONNECTIONS[found_connection[0]]
            ):
                matching.append(n)
    return matching


def _find_matching_resources(param: str, nodes: List[str]) -> List[str]:
    """Find resources that match the parameter value.

    Args:
        param: Parameter value to search for references
        nodes: List of all resource nodes

    Returns:
        List of matching resource names
    """
    matching = []

    # Normalize count.index references by removing the index placeholder
    # This allows ${resource.name[count.index].id} to match resource.name
    normalized_param = param.replace("[count.index]", "")

    # Handle list references (e.g., resource[0])
    if (
        re.search(r"\[\d+\]", normalized_param)
        and "[*]" not in normalized_param
        and normalized_param != "[]"
    ):
        matching = list(
            {s for s in nodes if s.split("~")[0] in normalized_param.replace(".*", "")}
        )
    else:
        # Extract Terraform resource references from parameter
        extracted_resources_list = helpers.extract_terraform_resource(normalized_param)
        if extracted_resources_list:
            for r in extracted_resources_list:
                matching.extend(
                    list(
                        {
                            s
                            for s in nodes
                            if (r in s or helpers.cleanup_curlies(r) in s)
                            and s not in matching
                        }
                    )
                )

    return matching


def _should_reverse_arrow(
    param: str, resource_associated_with: str, REVERSE_ARROW_LIST: List[str]
) -> bool:
    """Determine if arrow direction should be reversed.

    Args:
        param: Parameter value being checked
        resource_associated_with: Resource name being checked
        REVERSE_ARROW_LIST: List of patterns that trigger arrow reversal

    Returns:
        True if arrow should be reversed
    """
    reverse_origin_match = [s for s in REVERSE_ARROW_LIST if s in str(param)]
    if len(reverse_origin_match) == 0:
        return False

    # Prevent double reversal if both sides match
    reverse_dest_match = [
        s for s in REVERSE_ARROW_LIST if s in resource_associated_with
    ]
    if len(reverse_dest_match) > 0:
        if REVERSE_ARROW_LIST.index(reverse_dest_match[0]) < REVERSE_ARROW_LIST.index(
            reverse_origin_match[0]
        ):
            return False

    return True


def _numbered_nodes_match(matched_resource: str, resource_associated_with: str) -> bool:
    """Check if numbered nodes have matching suffixes.

    Args:
        matched_resource: First resource name
        resource_associated_with: Second resource name

    Returns:
        True if both have ~ suffix and suffixes match, or if no suffix check needed
    """
    # Match numbered nodes with same suffix
    if "~" in matched_resource and "~" in resource_associated_with:
        matched_resource_no = matched_resource.split("~")[1]
        resource_associated_with_no = resource_associated_with.split("~")[1]
        if matched_resource_no != resource_associated_with_no:
            return False
    return True


def _add_connection_pair(
    connection_pairs: List[str],
    matched_resource: str,
    resource_associated_with: str,
    reverse: bool,
    tfdata: Dict[str, Any],
) -> None:
    """Add connection pair in appropriate direction.

    Args:
        connection_pairs: List to append connection pairs to
        matched_resource: Matched resource name
        resource_associated_with: Origin resource name
        reverse: Whether to reverse arrow direction
        tfdata: Terraform data dictionary
    """
    if reverse:
        # Reversed: matched -> resource
        if (
            resource_associated_with not in tfdata["graphdict"][matched_resource]
            and matched_resource not in tfdata["graphdict"][resource_associated_with]
        ):
            connection_pairs.append(matched_resource)
            connection_pairs.append(resource_associated_with)
    else:
        # Normal: resource -> matched
        if (
            matched_resource not in tfdata["graphdict"][resource_associated_with]
            and matched_resource not in connection_pairs
        ):
            connection_pairs.append(resource_associated_with)
            connection_pairs.append(matched_resource)


def check_relationship(
    resource_associated_with: str, plist: List[Any], tfdata: Dict[str, Any]
) -> List[str]:
    """Check if a resource references other known resources.

    Scans resource parameters for references to other Terraform resources,
    detecting both explicit references and implied connections based on keywords.

    Args:
        resource_associated_with: Resource name being checked
        plist: List of parameter values from the resource
        tfdata: Terraform data dictionary with node_list and hidden nodes

    Returns:
        List of connection pairs [origin, dest, origin, dest, ...]
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    IMPLIED_CONNECTIONS = constants["IMPLIED_CONNECTIONS"]
    REVERSE_ARROW_LIST = constants["REVERSE_ARROW_LIST"]

    nodes = tfdata["node_list"]
    hidden = tfdata["hidden"]
    connection_pairs: List[str] = list()

    # Scan each parameter for resource references
    for p in plist:
        param = str(p)
        matching = _find_matching_resources(param, nodes)
        implied = _find_implied_connections(param, nodes, IMPLIED_CONNECTIONS)
        # Combine explicit and implied matches, avoiding duplicates
        matching.extend([m for m in implied if m not in matching])

        # Process matched resources
        for matched_resource in matching:
            # Skip hidden resources
            if (
                matched_resource not in hidden
                and resource_associated_with not in hidden
                and _numbered_nodes_match(matched_resource, resource_associated_with)
            ):
                # Check if arrow direction should be reversed
                reverse = _should_reverse_arrow(
                    param, resource_associated_with, REVERSE_ARROW_LIST
                )

                # Add connection pair in appropriate direction
                _add_connection_pair(
                    connection_pairs,
                    matched_resource,
                    resource_associated_with,
                    reverse,
                    tfdata,
                )

    return connection_pairs


def scan_module_relationships(
    tfdata: Dict[str, Any], graphdict: Dict[str, List[str]]
) -> None:
    """Scan module-to-module relationships via output references and direct resource references."""
    if not tfdata.get("all_module"):
        return

    # Get provider prefixes and GROUP_NODES for multi-cloud support
    config = _get_provider_config(tfdata)
    constants = _load_config_constants(tfdata)
    provider_prefixes = config.PROVIDER_PREFIX  # e.g., ["aws_", "google_", "azurerm_"]
    GROUP_NODES = constants["GROUP_NODES"]

    # Build regex pattern for any provider resource (e.g., aws_|google_|azurerm_)
    provider_pattern = "|".join([p.replace("_", r"\_") for p in provider_prefixes])
    direct_ref_pattern = rf"module\.(\w+)\.({provider_pattern}\w+)\.(\w+)"

    for filepath, module_list in tfdata["all_module"].items():
        if not isinstance(module_list, list):
            continue
        for module_dict in module_list:
            if not isinstance(module_dict, dict):
                continue
            for module_name, module_metadata in module_dict.items():
                if not isinstance(module_metadata, dict):
                    continue

                # Find resources in this module
                module_resources = [
                    n
                    for n in tfdata["node_list"]
                    if n.startswith(f"module.{module_name}.")
                ]
                if not module_resources:
                    continue

                metadata_str = str(module_metadata)

                # Find direct resource references (e.g., module.s3_bucket.aws_s3_bucket.this)
                direct_refs = re.findall(direct_ref_pattern, metadata_str)
                for ref_module_name, resource_type, resource_name in set(direct_refs):
                    if ref_module_name == module_name:
                        continue
                    # Find matching resources in node_list
                    target_pattern = (
                        f"module.{ref_module_name}.{resource_type}.{resource_name}"
                    )
                    target_resources = [
                        n for n in tfdata["node_list"] if target_pattern in n
                    ]
                    # Create connections, excluding GROUP nodes
                    for origin in module_resources:
                        for dest in target_resources:
                            origin_type = helpers.get_no_module_name(origin).split(".")[
                                0
                            ]
                            dest_type = helpers.get_no_module_name(dest).split(".")[0]
                            if (
                                origin_type not in GROUP_NODES
                                and dest_type not in GROUP_NODES
                            ):
                                if (
                                    origin in graphdict
                                    and dest not in graphdict[origin]
                                ):
                                    add_connection(graphdict, origin, dest)

                # Find module output references (e.g., module.s3_bucket.bucket_id)
                module_output_refs = re.findall(r"module\.(\w+)\.(\w+)", metadata_str)
                for ref_module_name, output_name in set(module_output_refs):
                    if ref_module_name == module_name:
                        continue
                    # Skip if already handled as direct reference (starts with provider prefix)
                    if any(
                        output_name.startswith(prefix) for prefix in provider_prefixes
                    ):
                        continue
                    # Resolve output to actual resources
                    target_resources = resolve_module_output_to_resources(
                        ref_module_name, output_name, tfdata
                    )
                    # Create connections, excluding GROUP nodes
                    for origin in module_resources:
                        for dest in target_resources:
                            origin_type = helpers.get_no_module_name(origin).split(".")[
                                0
                            ]
                            dest_type = helpers.get_no_module_name(dest).split(".")[0]
                            if (
                                origin_type not in GROUP_NODES
                                and dest_type not in GROUP_NODES
                            ):
                                if (
                                    origin in graphdict
                                    and dest not in graphdict[origin]
                                ):
                                    add_connection(graphdict, origin, dest)


def add_connection(graphdict: Dict, origin: str, dest: str) -> None:
    """Add connection between origin and dest nodes."""
    if dest in graphdict[origin] or helpers.get_no_module_name(origin).startswith(
        "aws_security_group"
    ):
        return
    click.echo(f"   {origin} --> {dest}")
    graphdict[origin].append(dest)
    # Replace unnumbered with numbered version
    if "~" in origin and "~" in dest and dest.split("~")[0] in graphdict[origin]:
        graphdict[origin].remove(dest.split("~")[0])


def resolve_module_output_to_resources(
    module_name: str, output_name: str, tfdata: Dict[str, Any]
) -> List[str]:
    """Resolve module output reference to actual resource names.

    Args:
        module_name: Name of the module being referenced
        output_name: Name of the output variable
        tfdata: Terraform data dictionary

    Returns:
        List of actual resource names that the output references
    """
    resources = []
    # Search through output files for matching module
    for file in tfdata.get("all_output", {}).keys():
        if f";{module_name};" in file:
            for output_dict in tfdata["all_output"][file]:
                if output_name in output_dict:
                    output_value = output_dict[output_name].get("value", "")
                    # Extract resource references from output value
                    resource_refs = helpers.extract_terraform_resource(
                        str(output_value)
                    )
                    for ref in resource_refs:
                        # Find matching nodes in node_list
                        matching = [n for n in tfdata["node_list"] if ref in n]
                        resources.extend(matching)
                    break
    return resources


def _get_base_node_name(node: str, tfdata: Dict[str, Any]) -> str:
    """Determine base node name by stripping suffixes."""
    if node not in tfdata["meta_data"].keys():
        nodename = node.split("~")[0]
        if "[" in nodename:
            nodename = nodename.split("[")[0]
    else:
        nodename = node
    return nodename


def _should_skip_node(node: str, nodename: str) -> bool:
    """Check if node should be skipped during relationship scanning."""
    return (
        helpers.get_no_module_name(nodename).startswith("random")
        or helpers.get_no_module_name(node).startswith("aws_security_group")
        or helpers.get_no_module_name(node).startswith("null")
    )


def _get_metadata_generator(node: str, nodename: str, tfdata: Dict[str, Any]):
    """Get metadata generator for parameter scanning.

    Note: Mutates tfdata["meta_data"] by copying from original_metadata if needed.
    """
    if nodename not in tfdata["meta_data"].keys():
        if node in tfdata["original_metadata"]:
            # Mutation: populate meta_data from original_metadata
            tfdata["meta_data"][node] = copy.deepcopy(tfdata["original_metadata"][node])
            return dict_generator(tfdata["original_metadata"][node])
    return dict_generator(tfdata["meta_data"][nodename])


def _process_connection_pairs(
    matching_result: List[str], tfdata: Dict[str, Any]
) -> Dict[str, Any]:
    """Process connection pairs and add to graphdict.

    Returns mutated tfdata.
    """
    for i in range(0, len(matching_result), 2):
        origin = matching_result[i]
        dest = matching_result[i + 1]
        c_list = list(tfdata["graphdict"][origin])
        # Add connection if not exists and not security group
        if dest not in c_list and not helpers.get_no_module_name(origin).startswith(
            "aws_security_group"
        ):
            click.echo(f"   {origin} --> {dest}")
            c_list.append(dest)
            # Replace unnumbered with numbered version
            if "~" in origin and "~" in dest and dest.split("~")[0] in c_list:
                c_list.remove(dest.split("~")[0])
        # Update graphdict with new connections
        tfdata["graphdict"][origin] = c_list

    return tfdata


def _scan_node_relationships(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Scan each node for relationships with other resources.

    Returns mutated tfdata.
    """
    for node in tfdata["node_list"]:
        nodename = _get_base_node_name(node, tfdata)

        # Skip certain resource types
        if _should_skip_node(node, nodename):
            continue

        # Get metadata generator for parameter scanning
        dg = _get_metadata_generator(node, nodename, tfdata)

        # Check each parameter for relationships
        for param_item_list in dg:
            matching_result = check_relationship(node, param_item_list, tfdata)
            # Process connection pairs
            if matching_result and len(matching_result) >= 2:
                tfdata = _process_connection_pairs(matching_result, tfdata)

    return tfdata


def add_relations(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Build final graph structure by detecting ALL resource relationships.

    Scans resource metadata to find cross references between resources/modules and adds
    connections to the graph. Handles hidden nodes and security groups specially.

    Args:
        tfdata: Terraform data dictionary with node_list and meta_data

    Returns:
        Updated tfdata with complete graphdict including all relationships
    """
    # Deep copy graphdict to prevent mutation issues during iteration
    tfdata["graphdict"] = copy.deepcopy(tfdata["graphdict"])

    created_resources = len(tfdata["node_list"])
    click.echo(
        click.style(
            f"\nChecking for additional links between {created_resources} resources..",
            fg="white",
            bold=True,
        )
    )

    # Scan each node for relationships
    tfdata = _scan_node_relationships(tfdata)

    # Scan module-to-module relationships
    scan_module_relationships(tfdata, tfdata["graphdict"])

    # Store immutable snapshot for reference
    tfdata["original_graphdict_with_relations"] = copy.deepcopy(tfdata["graphdict"])

    return tfdata


def consolidate_nodes(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Consolidate similar resources into single nodes.

    Merges resources that should be represented as a single node in the diagram
    based on CONSOLIDATED_NODES configuration.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with consolidated nodes
    """
    for resource in dict(tfdata["graphdict"]):
        if "null_resource" in resource:
            del tfdata["graphdict"][resource]
            continue
        if resource not in tfdata["meta_data"].keys():
            res = resource.split("~")[0]
        else:
            res = resource
        if "[" in res:
            res = res.split("[")[0]
        if tfdata["meta_data"].get(res):
            resdata = copy.deepcopy(tfdata["meta_data"].get(res))
        elif tfdata["meta_data"].get(resource):
            resdata = copy.deepcopy(tfdata["meta_data"][resource])
        else:
            continue
        consolidated_name = helpers.consolidated_node_check(resource, tfdata)
        if consolidated_name:
            if not tfdata["meta_data"].get(consolidated_name):
                tfdata["graphdict"][consolidated_name] = list()
                tfdata["meta_data"][consolidated_name] = dict()
            # Use deepcopy to avoid shared references between consolidated nodes
            merged_data = copy.deepcopy(tfdata["meta_data"][consolidated_name])
            merged_data.update(copy.deepcopy(resdata))
            tfdata["meta_data"][consolidated_name] = merged_data
            # Don't over-ride count values with 0 when merging
            if consolidated_name not in tfdata["graphdict"].keys():
                tfdata["graphdict"][consolidated_name] = list()
            # Merge connections using set union (deduplicates automatically)
            # BUT skip connections to resources that ALSO consolidate to the same target
            # (these are internal links within the consolidated group, not external connections)
            new_connections = set(tfdata["graphdict"][consolidated_name])
            for conn in tfdata["graphdict"][resource]:
                # Skip internal connections - where target also consolidates to same node
                conn_consolidates_to = helpers.consolidated_node_check(conn, tfdata)
                if conn_consolidates_to == consolidated_name:
                    # Both source and target consolidate to same node - skip internal link
                    continue
                new_connections.add(conn)
            tfdata["graphdict"][consolidated_name] = list(new_connections)
            del tfdata["graphdict"][resource]
            # del tfdata["meta_data"][res]
            connected_resource = consolidated_name
        else:
            connected_resource = resource
        for index, connection in enumerate(tfdata["graphdict"][connected_resource]):
            if helpers.consolidated_node_check(connection, tfdata):
                consolidated_connection = helpers.consolidated_node_check(
                    connection, tfdata
                )
                if consolidated_connection and consolidated_connection != connection:
                    if (
                        not consolidated_connection
                        in tfdata["graphdict"][connected_resource]
                        and connected_resource not in consolidated_connection
                    ):
                        tfdata["graphdict"][connected_resource][
                            index
                        ] = consolidated_connection
                    elif (
                        connected_resource in consolidated_connection
                        or consolidated_connection
                        in tfdata["graphdict"][connected_resource]
                    ):
                        tfdata["graphdict"][connected_resource].insert(index, "null")
                        tfdata["graphdict"][connected_resource].remove(connection)
        if "null" in tfdata["graphdict"][connected_resource]:
            tfdata["graphdict"][connected_resource] = list(
                filter(lambda a: a != "null", tfdata["graphdict"][connected_resource])
            )

    tfdata["graphdict"] = tfdata["graphdict"]
    return tfdata


def handle_variants(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Rename nodes based on resource variants.

    Applies variant suffixes to node names based on resource attributes
    (e.g., Lambda runtime, EC2 instance type) for better diagram clarity.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with variant node names
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    SPECIAL_RESOURCES = constants["SPECIAL_RESOURCES"]

    # Get provider config and prefixes
    provider = get_primary_provider_or_default(tfdata)
    config = _get_provider_config(tfdata)
    provider_prefixes = (
        config.PROVIDER_PREFIX
    )  # List of prefixes (e.g., ["azurerm_", "azuread_"])

    # Loop through all top level nodes and rename if variants exist
    for node in dict(tfdata["graphdict"]):
        node_title = helpers.get_no_module_name(node).split(".")[1]
        if node[-1].isdigit() and node[-2] == "~":
            node_name = node.split("~")[0]
        else:
            node_name = node
        # Check if resource belongs to current provider
        resource_name = helpers.get_no_module_name(node_name)
        is_provider_resource = any(
            resource_name.startswith(prefix) for prefix in provider_prefixes
        )
        if is_provider_resource:
            renamed_node = helpers.check_variant(
                node, tfdata["meta_data"].get(node_name), tfdata
            )
        else:
            renamed_node = False
        if (
            renamed_node
            and helpers.get_no_module_name(node).split(".")[0]
            not in SPECIAL_RESOURCES.keys()
        ):
            renamed_node = renamed_node + "." + node_title
            tfdata["graphdict"][renamed_node] = list(tfdata["graphdict"][node])
            del tfdata["graphdict"][node]
        else:
            renamed_node = node
        # Go through each connection and rename
        for resource in list(tfdata["graphdict"][renamed_node]):
            variant_suffix = ""
            if "~" in resource:
                if resource[-1].isdigit() and resource[-2] == "~":
                    connection_resource_name = resource.split("~")[0]
            else:
                connection_resource_name = resource
            # Check if connection resource belongs to current provider
            connection_name = helpers.get_no_module_name(connection_resource_name)
            is_provider_connection = any(
                connection_name.startswith(prefix) for prefix in provider_prefixes
            )
            if is_provider_connection:
                variant_suffix = helpers.check_variant(
                    resource, tfdata["meta_data"].get(connection_resource_name), tfdata
                )
                variant_label = resource.split(".")[1]
            # Build shared services group name based on provider
            shared_group_name = f"{provider}_group.shared_services"
            if (
                variant_suffix
                and helpers.get_no_module_name(resource).split(".")[0]
                not in SPECIAL_RESOURCES.keys()
                and not renamed_node.startswith(f"{provider}_group.shared")
                and (
                    shared_group_name not in tfdata["graphdict"]
                    or resource not in tfdata["graphdict"].get(shared_group_name, [])
                    or "~" in node
                )
                and resource.split(".")[0] != node.split(".")[0]
            ):
                new_list = list(tfdata["graphdict"][renamed_node])
                new_list.remove(resource)
                node_title = resource.split(".")[1]
                new_variant_name = variant_suffix + "." + variant_label
                new_list.append(new_variant_name)
                tfdata["graphdict"][renamed_node] = new_list
                tfdata["meta_data"][new_variant_name] = copy.deepcopy(
                    tfdata["meta_data"][resource]
                )
    return tfdata


def needs_multiple(resource: str, parent: str, tfdata: Dict[str, Any]) -> bool:
    """Determine if resource needs multiple numbered instances.

    Checks if a resource should be duplicated with numbered suffixes based
    on actual count values in metadata, parent counts, and resource type.

    Args:
        resource: Resource name to check
        parent: Parent resource name
        tfdata: Terraform data dictionary

    Returns:
        True if resource needs multiple instances
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    GROUP_NODES = constants["GROUP_NODES"]
    SPECIAL_RESOURCES = constants["SPECIAL_RESOURCES"]
    SHARED_SERVICES = constants["SHARED_SERVICES"]

    target_resource = (
        helpers.consolidated_node_check(resource, tfdata)
        if helpers.consolidated_node_check(resource, tfdata)
        and tfdata["meta_data"].get(resource)
        else resource
    )
    any_parent_has_count = helpers.any_parent_has_count(tfdata, resource)
    target_is_group = target_resource.split(".")[0] in GROUP_NODES
    target_has_count = (
        target_resource in tfdata["meta_data"]
        and tfdata["meta_data"][target_resource].get("count")
        and int(tfdata["meta_data"][target_resource].get("count")) >= 1
    )
    not_already_multiple = "~" not in target_resource
    no_special_handler = (
        resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
        or resource.split(".")[0] in GROUP_NODES
    )
    not_shared_service = resource.split(".")[0] not in SHARED_SERVICES
    if helpers.get_no_module_name(resource).split(".")[0] == "aws_security_group":
        security_group_with_count = (
            tfdata["original_metadata"][parent].get("count")
            and int(tfdata["original_metadata"][parent].get("count")) > 1
        )
    else:
        security_group_with_count = False
    has_variant = (
        helpers.check_variant(resource, tfdata["meta_data"][resource], tfdata)
        if resource in tfdata["meta_data"]
        else False
    )
    not_unique_resource = "aws_route_table." not in resource
    if (
        (
            (target_is_group and target_has_count)
            or security_group_with_count
            or (any_parent_has_count and (has_variant or target_has_count))
            or (target_has_count and any_parent_has_count)
        )
        and not_already_multiple
        and no_special_handler
        and not_shared_service
        and not_unique_resource
    ):
        return True
    return False


def add_multiples_to_parents(
    i: int, resource: str, multi_resources: list, tfdata: dict
):
    parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
    # Add numbered name to all original parents which may have been missed due to no count property
    for parent in parents_list:
        # Skip synthetic TerraVision nodes (tv_ prefix) - they represent
        # logical groupings (zones, regions) not resources to be numbered
        if parent.startswith("tv_"):
            continue
        if parent not in multi_resources:
            if "~" in parent:
                # We have a suffix so check it matches the i count
                existing_suffix = parent.split("~")[1]
                if existing_suffix == str(i + 1):
                    suffixed_name = resource + "~" + str(i + 1)
                else:
                    suffixed_name = resource + "~" + existing_suffix
            elif "~" not in resource:
                suffixed_name = resource + "~" + str(i + 1)
            else:
                suffixed_name = resource
            if (
                parent.split("~")[0] in tfdata["meta_data"].keys()
                and (tfdata["meta_data"][parent.split("~")[0]].get("count"))
                and not parent.startswith("aws_group.shared")
                and not suffixed_name in tfdata["graphdict"][parent]
                and not ("cluster" in suffixed_name and "cluster" in parent)
                and "aws_route_table." not in resource
            ):
                # Handle special case for security groups where if any parent has count>1, then create a numbered sg
                if (
                    helpers.any_parent_has_count(tfdata, resource)
                    and helpers.get_no_module_name(parent).split(".")[0]
                    == "aws_security_group"
                    and "~" not in parent
                ) or (
                    helpers.any_parent_has_count(tfdata, resource)
                    and helpers.get_no_module_name(parent).split(".")[0]
                    == "aws_security_group"
                    and "~" in parent
                    and helpers.check_list_for_dash(tfdata["graphdict"][parent])
                ):
                    if (
                        parent + "~" + str(i + 1) not in tfdata["graphdict"].keys()
                        and "~" not in parent
                    ):
                        tfdata["graphdict"][parent + "~" + str(i + 1)] = list(
                            tfdata["graphdict"][parent]
                        )
                    if (
                        tfdata["graphdict"].get(parent + "~" + str(i + 1))
                        and "~" not in parent
                    ):
                        if (
                            suffixed_name
                            not in tfdata["graphdict"][parent + "~" + str(i + 1)]
                            # and "aws_security_group" not in suffixed_name.split(".")[0]
                        ):
                            tfdata["graphdict"][parent + "~" + str(i + 1)].append(
                                suffixed_name
                            )
                        if resource in tfdata["graphdict"][parent + "~" + str(i + 1)]:
                            tfdata["graphdict"][parent + "~" + str(i + 1)].remove(
                                resource
                            )
                        tfdata["meta_data"][parent + "~" + str(i + 1)] = copy.deepcopy(
                            tfdata["meta_data"][parent]
                        )
                else:
                    if resource in tfdata["graphdict"][parent]:
                        tfdata["graphdict"][parent].remove(resource)
                    for sim in tfdata["graphdict"][parent]:
                        if sim.split("~")[0] == suffixed_name.split("~")[0]:
                            tfdata["graphdict"][parent].remove(sim)
                    tfdata["graphdict"][parent].append(suffixed_name)

    return tfdata


def cleanup_originals(
    multi_resources: List[str], tfdata: Dict[str, Any]
) -> Dict[str, Any]:
    """Remove original resource names after creating numbered instances.

    Cleans up base resource names that have been replaced with numbered
    instances (e.g., removes 'resource' after creating 'resource~1', 'resource~2').

    Args:
        multi_resources: List of resources with multiple instances
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with original names removed
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    SHARED_SERVICES = constants["SHARED_SERVICES"]

    # Now remove the original resource names
    for resource in multi_resources:
        if (
            helpers.list_of_dictkeys_containing(tfdata["graphdict"], resource)
            and not resource.split(".")[0] in SHARED_SERVICES
        ):
            del tfdata["graphdict"][resource]
        parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
        for parent in parents_list:
            if (
                resource in tfdata["graphdict"][parent]
                and not parent.startswith("aws_group.shared")
                and not "~" in parent
            ):
                tfdata["graphdict"][parent].remove(resource)
    # Delete any original security group nodes that have been replaced with numbered suffixes
    security_group_list = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_security_group") and "~" in k
    ]
    for security_group in security_group_list:
        check_original = security_group.split("~")[0]
        if check_original in tfdata["graphdict"].keys():
            del tfdata["graphdict"][check_original]
    return tfdata


def _load_handler_configs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Load provider-specific handler configurations.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        RESOURCE_HANDLER_CONFIGS dict
    """
    provider = get_primary_provider_or_default(tfdata)

    try:
        config_module = __import__(
            f"modules.config.resource_handler_configs_{provider}",
            fromlist=["RESOURCE_HANDLER_CONFIGS"],
        )
        return getattr(config_module, "RESOURCE_HANDLER_CONFIGS", {})
    except ImportError:
        return {}


def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Apply special processing for specific resource types.

    Executes config-driven transformations and additional handler functions.
    Supports hybrid approach with configurable execution order:
    - If 'transformations' exist: apply config-driven transformations
    - If 'additional_handler_function' exists: call Python function
    - 'handler_execution_order': "before" or "after" (default: "after")
      - "before": Run handler function BEFORE transformations
      - "after": Run handler function AFTER transformations (default)

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata after special processing
    """

    RESOURCE_HANDLER_CONFIGS = _load_handler_configs(tfdata)

    if not RESOURCE_HANDLER_CONFIGS:
        return tfdata

    resource_types = list(
        {helpers.get_no_module_name(k).split(".")[0] for k in tfdata["node_list"]}
    )

    for resource_pattern, config in RESOURCE_HANDLER_CONFIGS.items():
        matching = [s for s in resource_types if resource_pattern in s]

        if resource_pattern in resource_types or matching:
            # Get execution order preference (default: "after")
            execution_order = config.get("handler_execution_order", "after")

            has_transformations = "transformations" in config
            has_handler = "additional_handler_function" in config

            # Execute in configured order
            if execution_order == "before" and has_handler:
                # Step 1: Run handler function FIRST
                handler_module = resource_handlers.get_handler_module(tfdata)
                handler_func = getattr(
                    handler_module, config["additional_handler_function"]
                )
                tfdata = handler_func(tfdata)

                # Step 2: Apply transformations AFTER
                if has_transformations:
                    tfdata = apply_transformation_pipeline(
                        tfdata, config["transformations"]
                    )
            else:
                # Default: transformations first, then handler
                # Step 1: Apply config-driven transformations if present
                if has_transformations:
                    tfdata = apply_transformation_pipeline(
                        tfdata, config["transformations"]
                    )

                # Step 2: Apply additional handler function if present
                if has_handler:
                    handler_module = resource_handlers.get_handler_module(tfdata)
                    handler_func = getattr(
                        handler_module, config["additional_handler_function"]
                    )
                    tfdata = handler_func(tfdata)

    return tfdata


def dict_generator(
    indict: Any, pre: Optional[List[Any]] = None
) -> Generator[List[Any], None, None]:
    """Recursively traverse dictionary and yield all paths to leaf values.

    Generator that walks through nested dictionaries and lists, yielding
    the path to each leaf value as a list.

    Args:
        indict: Dictionary or value to traverse
        pre: Accumulated path prefix (used in recursion)

    Yields:
        List representing path to each leaf value
    """
    pre = pre[:] if pre else []
    if isinstance(indict, dict):
        for key, value in indict.items():
            if isinstance(value, dict):
                for d in dict_generator(value, pre + [key]):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in dict_generator(v, pre + [key]):
                        yield d
            else:
                yield pre + [key, value]
    else:
        yield pre + [indict]


# Loop through every connected node that has a count >0 and add suffix ~i where i is the source node suffix
def add_number_suffix(
    i: int, check_multiple_resource: str, tfdata: Dict[str, Any]
) -> List[str]:
    """Add numbered suffix to resource connections.

    Creates numbered versions of connections (e.g., resource~1, resource~2)
    for resources with count > 1.

    Args:
        i: Suffix number to add
        check_multiple_resource: Resource name to process
        tfdata: Terraform data dictionary

    Returns:
        List of connections with appropriate numbered suffixes
    """
    if not helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], check_multiple_resource
    ):
        return list()
    # Loop through each connection for this target resource

    new_list = list(tfdata["graphdict"][check_multiple_resource])
    for resource in list(tfdata["graphdict"][check_multiple_resource]):
        matching_resource_list = helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], resource
        )
        for res in matching_resource_list:
            if (
                "~" in res
                and res.split("~")[1] == str(i)  # we have matching seq number suffix
                and res not in new_list
                and (
                    needs_multiple(
                        helpers.get_no_module_name(res),
                        check_multiple_resource,
                        tfdata,
                    )
                    or res in tfdata["graphdict"].keys()
                )
                and res not in tfdata["graphdict"][check_multiple_resource]
                and res not in new_list
            ):
                new_list.append(res)
                new_list.remove(resource)
    return new_list


def extend_sg_groups(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Extend security groups to match numbered resource instances.

    Creates numbered security group instances to match numbered resources
    they're associated with.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with extended security groups
    """
    list_of_sgs = [
        s
        for s in tfdata["graphdict"]
        if helpers.get_no_module_name(s).startswith("aws_security_group")
    ]
    for sg in list_of_sgs:
        expanded = False
        for connection in list(tfdata["graphdict"][sg]):
            if "~" in connection and "~" not in sg:
                expanded = True
                suffixed_sg = sg + "~" + connection.split("~")[1]
                tfdata["graphdict"][suffixed_sg] = list([connection])
                tfdata["graphdict"][sg].remove(connection)
        if expanded:
            also_connected = helpers.list_of_parents(tfdata["graphdict"], sg)
            for node in also_connected:
                if "~" in node:
                    suffixed_sg = sg + "~" + node.split("~")[1]
                    if sg in tfdata["graphdict"][node]:
                        tfdata["graphdict"][node].remove(sg)
                        tfdata["graphdict"][node].append(suffixed_sg)
                    # check if other multiples of the node also have the relationship, if not, add it
                    if "~1" in node:
                        i = 2
                        next_node = node.split("~")[0] + "~" + str(i)
                        next_sg = sg + "~" + str(i)
                        while (
                            next_node in tfdata["graphdict"].keys()
                            and next_sg in tfdata["graphdict"].keys()
                        ):
                            if not next_sg in tfdata["graphdict"][next_node]:
                                tfdata["graphdict"][next_node].append(next_sg)
                            i = i + 1
                            next_node = node.split("~")[0] + "~" + str(i)
                            next_sg = sg + "~" + str(i)
            del tfdata["graphdict"][sg]

    return tfdata


def add_multiples_to_parents(
    i: int, resource: str, multi_resources: list, tfdata: dict
):
    parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
    # Add numbered name to all original parents which may have been missed due to no count property
    for parent in parents_list:
        # Skip synthetic TerraVision nodes (tv_ prefix) - they represent
        # logical groupings (zones, regions) not resources to be numbered
        if parent.startswith("tv_"):
            continue
        if parent not in multi_resources:
            if "~" in parent:
                # We have a suffix so check it matches the i count
                existing_suffix = parent.split("~")[1]
                if existing_suffix == str(i + 1):
                    suffixed_name = resource + "~" + str(i + 1)
                else:
                    suffixed_name = resource + "~" + existing_suffix
            else:
                # For subnets without ~ suffix: only add the instance matching the subnet's position
                if "aws_subnet" in parent:
                    # Get all subnets sorted to determine position
                    all_subnets = sorted(
                        [k for k in tfdata["graphdict"].keys() if "aws_subnet" in k]
                    )
                    try:
                        subnet_position = all_subnets.index(parent) + 1
                        # Only add if this numbered instance matches the subnet's position
                        if subnet_position == i + 1:
                            suffixed_name = resource + "~" + str(i + 1)
                        else:
                            # Skip this subnet - it should get a different numbered instance
                            continue
                    except (ValueError, IndexError):
                        # Fallback: add instance to this subnet
                        suffixed_name = resource + "~" + str(i + 1)
                else:
                    # Non-subnet parent: add numbered instance normally
                    suffixed_name = resource + "~" + str(i + 1)
            if (
                parent.split("~")[0] in tfdata["meta_data"].keys()
                and (
                    not tfdata["meta_data"][parent.split("~")[0]].get("count")
                    or tfdata["meta_data"][parent.split("~")[0]].get("count") == 1
                )
                and not parent.startswith("aws_group.shared")
                and not suffixed_name in tfdata["graphdict"][parent]
                and not ("cluster" in suffixed_name and "cluster" in parent)
                and "aws_route_table." not in resource
            ):
                tfdata["graphdict"][parent].append(suffixed_name)
                if resource in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].remove(resource)
    return tfdata


def _parse_count_value(value) -> int:
    """Parse a count-like value to integer, handling both string and numeric types.

    Args:
        value: The value to parse (may be int, float, or string with quotes)

    Returns:
        Integer count value, or 1 if parsing fails
    """
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        return int(value.replace('"', "").strip())
    return 1


def _get_instance_count(metadata: Dict[str, Any]) -> int:
    """Determine the number of instances for a resource from its metadata.

    Checks count, max_capacity, and desired_count attributes in priority order.

    Args:
        metadata: Resource metadata dictionary

    Returns:
        Number of instances to create (minimum 1)
    """
    for attr in ("count", "max_capacity", "desired_count"):
        value = metadata.get(attr)
        if value:
            return _parse_count_value(value)
    return 1


def handle_count_resources(
    multi_resources: List[str], tfdata: Dict[str, Any]
) -> Dict[str, Any]:
    """Create multiple node instances for resources with count > 1.

    Generates numbered resource instances (resource~1, resource~2, etc.)
    for resources with count, desired_count, or max_capacity attributes.

    Args:
        multi_resources: List of resources that need multiple instances
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with numbered resource instances
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    SHARED_SERVICES = constants["SHARED_SERVICES"]

    # Process each resource with count attribute
    for resource in multi_resources:
        # Determine number of instances to create
        max_i = _get_instance_count(tfdata["meta_data"][resource])

        # Create numbered instances
        for i in range(max_i):
            # Get connections with numbered suffixes
            resource_i = add_number_suffix(i + 1, resource, tfdata)
            not_shared_service = resource.split(".")[0] not in SHARED_SERVICES

            if not_shared_service:
                # Create numbered node instance
                tfdata["graphdict"][resource + "~" + str(i + 1)] = resource_i
                tfdata["meta_data"][resource + "~" + str(i + 1)] = copy.deepcopy(
                    tfdata["meta_data"][resource]
                )
                tfdata = add_multiples_to_parents(i, resource, multi_resources, tfdata)

                # Create numbered instances for connections if needed
                for numbered_node in resource_i:
                    original_name = numbered_node.split("~")[0]
                    # Skip synthetic TerraVision nodes (tv_ prefix) - they represent
                    # logical groupings (zones, regions) not resources to be numbered
                    is_synthetic_node = original_name.startswith("tv_")
                    if (
                        "~" in numbered_node
                        and helpers.list_of_dictkeys_containing(
                            tfdata["graphdict"], original_name
                        )
                        and original_name not in multi_resources
                        and not helpers.consolidated_node_check(original_name, tfdata)
                        and not is_synthetic_node
                    ):
                        # Handle first instance
                        if i == 0:
                            if (
                                original_name in tfdata["graphdict"].keys()
                                and original_name + "~1"
                                not in tfdata["graphdict"].keys()
                            ):
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][original_name]
                                )
                                tfdata = add_multiples_to_parents(
                                    i, original_name, multi_resources, tfdata
                                )
                                del tfdata["graphdict"][original_name]
                        else:
                            if (original_name + "~" + str(i)) in tfdata[
                                "graphdict"
                            ] and numbered_node not in tfdata["graphdict"]:
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][original_name + "~" + str(i)]
                                )
                            elif tfdata["graphdict"].get(
                                original_name + "~" + str(i + 1)
                            ):
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][
                                        original_name + "~" + str(i + 1)
                                    ]
                                )
                            tfdata = add_multiples_to_parents(
                                i, original_name, multi_resources, tfdata
                            )
    return tfdata


def handle_singular_references(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle connections to single instances of numbered resources.

    Ensures numbered nodes connect to appropriately numbered instances
    of their dependencies.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with corrected singular references
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    SKIP_SINGULAR_EXPANSION = constants.get("SKIP_SINGULAR_EXPANSION", [])

    for node, connections in dict(tfdata["graphdict"]).items():
        for c in list(connections):
            if "~" in node and not "~" in c:
                suffix = node.split("~")[1]
                suffixed_node = f"{c}~{suffix}"
                if suffixed_node in tfdata["graphdict"]:
                    if suffixed_node not in tfdata["graphdict"][node]:
                        tfdata["graphdict"][node].append(suffixed_node)
                    tfdata["graphdict"][node].remove(c)
            # If consolidated node, add all connections to node
            # Skip resources that are manually matched to subnets by suffix in their handlers
            # Also skip if node is a subnet - subnets should keep their specific numbered instances
            if (
                "~" in c
                and helpers.consolidated_node_check(node, tfdata)
                and "aws_subnet" not in node
            ):
                # Check if connection should skip automatic expansion
                should_skip = any(
                    skip_pattern in c for skip_pattern in SKIP_SINGULAR_EXPANSION
                )
                if should_skip:
                    continue

                for i in range(1, int(c.split("~")[1]) + 4):
                    suffixed_node = f"{c.split('~')[0]}~{i}"
                    if (
                        suffixed_node in tfdata["graphdict"]
                        and suffixed_node not in tfdata["graphdict"][node]
                    ):
                        tfdata["graphdict"][node].append(suffixed_node)
    return tfdata


def cleanup_cross_subnet_connections(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Remove connections between numbered and unnumbered resources in different subnets.

    Prevents messy diagram rendering where numbered resources (e.g., redis~1, redis~2, redis~3)
    in different subnets all connect to the same unnumbered resource (e.g., Lambda function)
    that's only deployed in some subnets.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with cross-subnet connections removed
    """
    # Get all subnets and build a map of which resources are in which subnet
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_subnet")
    resource_to_subnets = {}  # Maps resource name to list of subnets containing it

    for subnet in subnets:
        for resource in tfdata["graphdict"].get(subnet, []):
            if resource not in resource_to_subnets:
                resource_to_subnets[resource] = []
            resource_to_subnets[resource].append(subnet)

    # For each numbered resource, check its connections to unnumbered resources
    for resource_name, connections in list(tfdata["graphdict"].items()):
        if "~" not in resource_name:
            continue  # Skip unnumbered resources

        # Get the subnets this numbered resource is in
        source_subnets = resource_to_subnets.get(resource_name, [])
        if not source_subnets:
            continue

        # Check each connection
        for connection in list(connections):
            # Skip if the target is also numbered (those connections are handled elsewhere)
            if "~" in connection:
                continue

            # Skip if the connection is a special node (groups, shared services, etc.)
            if connection.startswith("aws_group.") or connection.startswith("aws_az."):
                continue

            # Get the subnets the target resource is in
            target_subnets = resource_to_subnets.get(connection, [])

            # If the numbered resource and unnumbered resource don't share any common subnet,
            # remove the connection
            if target_subnets and not set(source_subnets) & set(target_subnets):
                tfdata["graphdict"][resource_name].remove(connection)

    return tfdata


def create_multiple_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Main function to create multiple resource instances.

    Orchestrates the creation of numbered resource instances for all
    resources with count/for_each attributes.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with all multiple resource instances created
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    SHARED_SERVICES = constants["SHARED_SERVICES"]

    # Identify resources with count/for_each attributes
    # Skip synthetic TerraVision nodes (tv_ prefix) - they represent
    # logical groupings (zones, regions) not resources to be numbered
    multi_resources = [
        n
        for n in tfdata["graphdict"]
        if (
            "~" not in n
            and not n.startswith("tv_")  # Skip synthetic nodes
            and tfdata["meta_data"].get(n)
            and (
                tfdata["meta_data"][n].get("count")
                or tfdata["meta_data"][n].get("desired_count")
                or tfdata["meta_data"][n].get("max_capacity")
                or tfdata["meta_data"][n].get("for_each")
                or tfdata["meta_data"][n].get("target_size")  # GCP IGM target_size
            )
            and not helpers.consolidated_node_check(n, tfdata)
        )
    ]

    # Create numbered instances
    tfdata = handle_count_resources(multi_resources, tfdata)

    # Fix singular references to numbered nodes
    tfdata = handle_singular_references(tfdata)

    # Remove cross-subnet connections between numbered and unnumbered resources
    tfdata = cleanup_cross_subnet_connections(tfdata)

    # Clean up original resource names but preserve connections to numbered instances
    for resource in multi_resources:
        # Find all numbered instances of this resource
        numbered_instances = sorted(
            [k for k in tfdata["graphdict"].keys() if k.startswith(resource + "~")]
        )

        # If numbered instances exist, update original to point to them
        if numbered_instances and resource in tfdata["graphdict"]:
            tfdata["graphdict"][resource] = numbered_instances

            # Update any nodes that point to this resource to point to numbered instances instead
            for node in list(tfdata["graphdict"].keys()):
                if node != resource and resource in tfdata["graphdict"][node]:
                    tfdata["graphdict"][node].remove(resource)

                    # For subnets: only add the numbered instance matching the subnet's position
                    if "_subnet" in node:
                        # Get all subnets sorted to determine position
                        all_subnets = sorted(
                            [
                                k
                                for k in tfdata["graphdict"].keys()
                                if "_subnet" in k and "association" not in k
                            ]
                        )
                        try:
                            subnet_position = all_subnets.index(node) + 1
                            # Only add the instance matching this subnet's position
                            matching_inst = f"{resource}~{subnet_position}"
                            if matching_inst in numbered_instances:
                                if matching_inst not in tfdata["graphdict"][node]:
                                    tfdata["graphdict"][node].append(matching_inst)
                        except (ValueError, IndexError):
                            # Fallback: add all instances if position can't be determined
                            for inst in numbered_instances:
                                if inst not in tfdata["graphdict"][node]:
                                    tfdata["graphdict"][node].append(inst)
                    else:
                        # For non-subnet nodes: add all numbered instances
                        for inst in numbered_instances:
                            if inst not in tfdata["graphdict"][node]:
                                tfdata["graphdict"][node].append(inst)

            # Delete the original resource after updating references
            if resource.split(".")[0] not in SHARED_SERVICES:
                del tfdata["graphdict"][resource]

        # Remove original resource if not shared service and no numbered instances to link to
        elif (
            helpers.list_of_dictkeys_containing(tfdata["graphdict"], resource)
            and resource.split(".")[0] not in SHARED_SERVICES
        ):
            del tfdata["graphdict"][resource]

        # Remove from parent connections
        if resource not in tfdata["graphdict"]:
            parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
            for parent in parents_list:
                if (
                    resource in tfdata["graphdict"][parent]
                    and not parent.startswith("aws_group.shared")
                    and "~" not in parent
                ):
                    tfdata["graphdict"][parent].remove(resource)

    # Clean up original security group nodes
    security_group_list = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_security_group") and "~" in k
    ]
    for security_group in security_group_list:
        check_original = security_group.split("~")[0]
        if check_original in tfdata["graphdict"].keys():
            del tfdata["graphdict"][check_original]

    # Extend security groups for numbered instances
    tfdata = extend_sg_groups(tfdata)

    return tfdata
