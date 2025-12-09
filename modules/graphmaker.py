"""Graph maker module for TerraVision.

This module constructs the resource dependency graph from parsed Terraform data.
It handles relationship detection, node consolidation, resource variants, and
multiple resource instances (count/for_each). The graph structure is used for
diagram generation.
"""

import copy
from typing import Dict, List, Any, Tuple, Generator, Optional

import click

import modules.config_loader as config_loader
import modules.helpers as helpers
import modules.resource_handlers as resource_handlers
from modules.provider_detector import get_primary_provider_or_default


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

    return {
        'REVERSE_ARROW_LIST': getattr(config, f'{provider_upper}_REVERSE_ARROW_LIST', []),
        'IMPLIED_CONNECTIONS': getattr(config, f'{provider_upper}_IMPLIED_CONNECTIONS', {}),
        'GROUP_NODES': getattr(config, f'{provider_upper}_GROUP_NODES', []),
        'CONSOLIDATED_NODES': getattr(config, f'{provider_upper}_CONSOLIDATED_NODES', []),
        'NODE_VARIANTS': getattr(config, f'{provider_upper}_NODE_VARIANTS', []),
        'SPECIAL_RESOURCES': getattr(config, f'{provider_upper}_SPECIAL_RESOURCES', {}),
        'SHARED_SERVICES': getattr(config, f'{provider_upper}_SHARED_SERVICES', []),
        'AUTO_ANNOTATIONS': getattr(config, f'{provider_upper}_AUTO_ANNOTATIONS', []),
        'EDGE_NODES': getattr(config, f'{provider_upper}_EDGE_NODES', []),
        'FORCED_DEST': getattr(config, f'{provider_upper}_FORCED_DEST', []),
        'FORCED_ORIGIN': getattr(config, f'{provider_upper}_FORCED_ORIGIN', []),
    }


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
    FORCED_DEST = constants['FORCED_DEST']
    FORCED_ORIGIN = constants['FORCED_ORIGIN']
    AUTO_ANNOTATIONS = constants['AUTO_ANNOTATIONS']

    for n, connections in dict(tfdata["graphdict"]).items():
        node = helpers.get_no_module_name(n)
        reverse_dest = len([s for s in FORCED_DEST if node.startswith(s)]) > 0

        for c in list(connections):
            # Reverse if node is a forced destination
            if reverse_dest:
                if not tfdata["graphdict"].get(c):
                    tfdata["graphdict"][c] = list()
                tfdata["graphdict"][c].append(n)
                tfdata["graphdict"][n].remove(c)

            # Reverse if connection is a forced origin
            reverse_origin = (
                len(
                    [
                        s
                        for s in FORCED_ORIGIN
                        if helpers.get_no_module_name(c).startswith(s)
                        and node.split(".")[0] not in str(AUTO_ANNOTATIONS)
                    ]
                )
                > 0
            )
            if reverse_origin:
                tfdata["graphdict"][c].append(n)
                tfdata["graphdict"][node].remove(c)

    return tfdata


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
    IMPLIED_CONNECTIONS = constants['IMPLIED_CONNECTIONS']
    REVERSE_ARROW_LIST = constants['REVERSE_ARROW_LIST']

    nodes = tfdata["node_list"]
    hidden = tfdata["hidden"]
    connection_pairs: List[str] = list()
    matching: List[str] = list()

    # Scan each parameter for resource references
    for p in plist:
        param = str(p)
        matching = []

        # Handle list references (e.g., resource[0])
        if "[" in param and "[*]" not in param and param != "[]":
            matching = list(
                {
                    s
                    for s in nodes
                    if helpers.remove_numbered_suffix(s) in param.replace(".*", "")
                }
            )
        else:
            # Extract Terraform resource references from parameter
            extracted_resources_list = helpers.extract_terraform_resource(param)
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

        # Check for implied connections based on keywords
        found_connection = list(
            {s for s in IMPLIED_CONNECTIONS.keys() if s in str(param)}
        )
        if found_connection:
            for n in nodes:
                if (
                    helpers.get_no_module_name(n).startswith(
                        IMPLIED_CONNECTIONS[found_connection[0]]
                    )
                    and n not in matching
                ):
                    matching.append(n)

        # Process matched resources
        if matching:
            for matched_resource in matching:
                reverse = False
                # Skip hidden resources
                if (
                    matched_resource not in hidden
                    and resource_associated_with not in hidden
                ):
                    # Check if arrow direction should be reversed
                    reverse_origin_match = [
                        s for s in REVERSE_ARROW_LIST if s in str(param)
                    ]
                    if len(reverse_origin_match) > 0:
                        reverse = True
                        # Prevent double reversal if both sides match
                        reverse_dest_match = [
                            s
                            for s in REVERSE_ARROW_LIST
                            if s in resource_associated_with
                        ]
                        if len(reverse_dest_match) > 0:
                            if REVERSE_ARROW_LIST.index(
                                reverse_dest_match[0]
                            ) < REVERSE_ARROW_LIST.index(reverse_origin_match[0]):
                                reverse = False

                    # Match numbered nodes with same suffix
                    if "~" in matched_resource and "~" in resource_associated_with:
                        matched_resource_no = matched_resource.split("~")[1]
                        resource_associated_with_no = resource_associated_with.split(
                            "~"
                        )[1]
                        if matched_resource_no != resource_associated_with_no:
                            continue

                    # Add connection pair in appropriate direction
                    if reverse:
                        # Reversed: matched -> resource
                        if (
                            resource_associated_with
                            not in tfdata["graphdict"][matched_resource]
                            and matched_resource
                            not in tfdata["graphdict"][resource_associated_with]
                        ):
                            connection_pairs.append(matched_resource)
                            connection_pairs.append(resource_associated_with)
                    else:
                        # Normal: resource -> matched
                        if (
                            matched_resource
                            not in tfdata["graphdict"][resource_associated_with]
                            and matched_resource not in connection_pairs
                        ):
                            connection_pairs.append(resource_associated_with)
                            connection_pairs.append(matched_resource)

    return connection_pairs


def add_relations(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Build final graph structure by detecting resource relationships.

    Scans resource metadata to find references between resources and adds
    connections to the graph. Handles hidden nodes and security groups specially.

    Args:
        tfdata: Terraform data dictionary with node_list and meta_data

    Returns:
        Updated tfdata with complete graphdict including all relationships
    """
    # Deep copy to prevent mutation leakage
    graphdict = copy.deepcopy(tfdata["graphdict"])
    created_resources = len(tfdata["node_list"])
    click.echo(
        click.style(
            f"\nChecking for additional links between {created_resources} resources..",
            fg="white",
            bold=True,
        )
    )

    # Scan each node for relationships
    for node in tfdata["node_list"]:
        # Determine base node name
        if node not in tfdata["meta_data"].keys():
            nodename = node.split("~")[0]
            if "[" in nodename:
                nodename = nodename.split("[")[0]
        else:
            nodename = node

        # Skip certain resource types
        if (
            helpers.get_no_module_name(nodename).startswith("random")
            or helpers.get_no_module_name(node).startswith("aws_security_group")
            or helpers.get_no_module_name(node).startswith("null")
        ):
            continue

        # Get metadata generator for parameter scanning
        if nodename not in tfdata["meta_data"].keys():
            dg = dict_generator(tfdata["original_metadata"][node])
            tfdata["meta_data"][node] = copy.deepcopy(tfdata["original_metadata"][node])
        else:
            dg = dict_generator(tfdata["meta_data"][nodename])

        # Check each parameter for relationships
        for param_item_list in dg:
            matching_result = check_relationship(
                node,
                param_item_list,
                tfdata,
            )
            # Process connection pairs
            if matching_result and len(matching_result) >= 2:
                for i in range(0, len(matching_result), 2):
                    origin = matching_result[i]
                    dest = matching_result[i + 1]
                    c_list = list(graphdict[origin])
                    # Add connection if not exists and not security group
                    if dest not in c_list and not helpers.get_no_module_name(
                        origin
                    ).startswith("aws_security_group"):
                        click.echo(f"   {origin} --> {dest}")
                        c_list.append(dest)
                        # Replace unnumbered with numbered version
                        if (
                            "~" in origin
                            and "~" in dest
                            and dest.split("~")[0] in c_list
                        ):
                            c_list.remove(dest.split("~")[0])
                    graphdict[origin] = c_list

    # Remove hidden nodes from graph
    for hidden_resource in tfdata["hidden"]:
        del graphdict[hidden_resource]
    for resource in graphdict:
        for hidden_resource in tfdata["hidden"]:
            if hidden_resource in graphdict[resource]:
                graphdict[resource].remove(hidden_resource)

    tfdata["graphdict"] = graphdict
    # Store immutable snapshot for reference
    tfdata["original_graphdict_with_relations"] = copy.deepcopy(graphdict)

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
        consolidated_name = helpers.consolidated_node_check(resource)
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
            tfdata["graphdict"][consolidated_name] = list(
                set(tfdata["graphdict"][consolidated_name])
                | set(tfdata["graphdict"][resource])
            )
            del tfdata["graphdict"][resource]
            # del tfdata["meta_data"][res]
            connected_resource = consolidated_name
        else:
            connected_resource = resource
        for index, connection in enumerate(tfdata["graphdict"][connected_resource]):
            if helpers.consolidated_node_check(connection):
                consolidated_connection = helpers.consolidated_node_check(connection)
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
    SPECIAL_RESOURCES = constants['SPECIAL_RESOURCES']

    # Get provider config and prefixes
    provider = get_primary_provider_or_default(tfdata)
    config = _get_provider_config(tfdata)
    provider_prefixes = config.PROVIDER_PREFIX  # List of prefixes (e.g., ["azurerm_", "azuread_"])

    # Loop through all top level nodes and rename if variants exist
    for node in dict(tfdata["graphdict"]):
        node_title = helpers.get_no_module_name(node).split(".")[1]
        if node[-1].isdigit() and node[-2] == "~":
            node_name = node.split("~")[0]
        else:
            node_name = node
        # Check if resource belongs to current provider
        resource_name = helpers.get_no_module_name(node_name)
        is_provider_resource = any(resource_name.startswith(prefix) for prefix in provider_prefixes)
        if is_provider_resource:
            renamed_node = helpers.check_variant(
                node, tfdata["meta_data"].get(node_name)
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
            is_provider_connection = any(connection_name.startswith(prefix) for prefix in provider_prefixes)
            if is_provider_connection:
                variant_suffix = helpers.check_variant(
                    resource, tfdata["meta_data"].get(connection_resource_name)
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
    GROUP_NODES = constants['GROUP_NODES']
    SPECIAL_RESOURCES = constants['SPECIAL_RESOURCES']
    SHARED_SERVICES = constants['SHARED_SERVICES']

    target_resource = (
        helpers.consolidated_node_check(resource)
        if helpers.consolidated_node_check(resource)
        and tfdata["meta_data"].get(resource)
        else resource
    )
    any_parent_has_count = helpers.any_parent_has_count(tfdata, resource)
    target_is_group = target_resource.split(".")[0] in GROUP_NODES
    target_has_count = (
        tfdata["meta_data"][target_resource].get("count")
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
    has_variant = helpers.check_variant(resource, tfdata["meta_data"][resource])
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
    SHARED_SERVICES = constants['SHARED_SERVICES']

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


# Handle resources which require pre/post-processing before/after being added to graphdict
def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Apply special processing for specific resource types.

    Delegates to resource-specific handlers for resources that need
    custom processing (e.g., VPCs, subnets, security groups).

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata after special processing
    """
    # Load provider-specific constants
    constants = _load_config_constants(tfdata)
    SPECIAL_RESOURCES = constants['SPECIAL_RESOURCES']

    resource_types = list(
        {helpers.get_no_module_name(k).split(".")[0] for k in tfdata["node_list"]}
    )
    for resource_prefix, handler in SPECIAL_RESOURCES.items():
        matching_substring = [s for s in resource_types if resource_prefix in s]
        if resource_prefix in resource_types or matching_substring:
            tfdata = getattr(resource_handlers, handler)(tfdata)
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
        if parent not in multi_resources:
            if "~" in parent:
                # We have a suffix so check it matches the i count
                existing_suffix = parent.split("~")[1]
                if existing_suffix == str(i + 1):
                    suffixed_name = resource + "~" + str(i + 1)
                else:
                    suffixed_name = resource + "~" + existing_suffix
            else:
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
    SHARED_SERVICES = constants['SHARED_SERVICES']

    # Process each resource with count attribute
    for resource in multi_resources:
        # Determine number of instances to create
        if tfdata["meta_data"][resource].get("count"):
            max_i = int(tfdata["meta_data"][resource].get("count"))
        elif tfdata["meta_data"][resource].get("max_capacity"):
            max_i = int(
                tfdata["meta_data"][resource].get("max_capacity").replace('"', "")
            )
        elif tfdata["meta_data"][resource].get("desired_count"):
            max_i = int(
                tfdata["meta_data"][resource].get("desired_count").replace('"', "")
            )
        else:
            max_i = 1

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
                    if (
                        "~" in numbered_node
                        and helpers.list_of_dictkeys_containing(
                            tfdata["graphdict"], original_name
                        )
                        and original_name not in multi_resources
                        and not helpers.consolidated_node_check(original_name)
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
    for node, connections in dict(tfdata["graphdict"]).items():
        for c in list(connections):
            if "~" in node and not "~" in c:
                suffix = node.split("~")[1]
                suffixed_node = f"{c}~{suffix}"
                if suffixed_node in tfdata["graphdict"]:
                    tfdata["graphdict"][node].append(suffixed_node)
                    tfdata["graphdict"][node].remove(c)
            # If cosolidated node, add all connections to node
            if "~" in c and (helpers.consolidated_node_check(node) or "~" not in node):
                for i in range(1, int(c.split("~")[1]) + 4):
                    suffixed_node = f"{c.split('~')[0]}~{i}"
                    if (
                        suffixed_node in tfdata["graphdict"]
                        and suffixed_node not in tfdata["graphdict"][node]
                    ):
                        tfdata["graphdict"][node].append(suffixed_node)
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
    SHARED_SERVICES = constants['SHARED_SERVICES']

    # Identify resources with count/for_each attributes
    multi_resources = [
        n
        for n in tfdata["graphdict"]
        if (
            "~" not in n
            and tfdata["meta_data"].get(n)
            and (
                tfdata["meta_data"][n].get("count")
                or tfdata["meta_data"][n].get("desired_count")
                or tfdata["meta_data"][n].get("max_capacity")
                or tfdata["meta_data"][n].get("for_each")
            )
            and not helpers.consolidated_node_check(n)
        )
    ]

    # Create numbered instances
    tfdata = handle_count_resources(multi_resources, tfdata)

    # Fix singular references to numbered nodes
    tfdata = handle_singular_references(tfdata)

    # Clean up original resource names
    for resource in multi_resources:
        # Remove original resource if not shared service
        if (
            helpers.list_of_dictkeys_containing(tfdata["graphdict"], resource)
            and resource.split(".")[0] not in SHARED_SERVICES
        ):
            del tfdata["graphdict"][resource]

        # Remove from parent connections
        parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
        for parent in parents_list:
            if (
                resource in tfdata["graphdict"][parent]
                and not parent.startswith("aws_group.shared")
                and "~" not in parent
                and not tfdata["meta_data"][resource].get("count")
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
