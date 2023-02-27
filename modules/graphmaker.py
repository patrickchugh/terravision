from ast import literal_eval
from contextlib import suppress
import click
import json
from modules.tf_function_handlers import tf_function_handlers
from sys import exit
import sys
import modules.helpers as helpers
import modules.annotations as annotations
import modules.cloud_config as cloud_config
import modules.resource_handlers as resource_handlers

REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AWS_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.AWS_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.AWS_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.AWS_SHARED_SERVICES

# Make final graph structure to be used for drawing
def make_graph_dict(tfdata: dict):
    # Start with an empty connections list for all nodes/resources we know about
    graphdict = dict.fromkeys(tfdata["node_list"], [])
    num_resources = len(tfdata["node_list"])
    click.echo(
        click.style(
            f"\nComputing Relations between {num_resources - len(tfdata['hidden'])} out of {num_resources} resources...",
            fg="white",
            bold=True,
        )
    )
    # Determine relationship between resources and append to graphdict when found
    for param_list in dict_generator(tfdata["all_resource"]):
        for listitem in param_list:
            if isinstance(listitem, str):
                lisitem_tocheck = listitem
                matching_result = check_relationship(
                    lisitem_tocheck, param_list, tfdata["node_list"], tfdata["hidden"]
                )
                if matching_result:
                    for i in range(0, len(matching_result), 2):
                        a_list = list(graphdict[matching_result[i]])
                        if not matching_result[i + 1] in a_list:
                            a_list.append(matching_result[i + 1])
                        graphdict[matching_result[i]] = a_list
            if isinstance(listitem, list):
                for i in listitem:
                    matching_result = check_relationship(
                        i, param_list, tfdata["node_list"], tfdata["hidden"]
                    )
                    if matching_result:
                        a_list = list(graphdict[matching_result[0]])
                        if not matching_result[1] in a_list:
                            a_list.append(matching_result[1])
                        graphdict[matching_result[0]] = a_list
    # Hide nodes where count = 0
    for hidden_resource in tfdata["hidden"]:
        del graphdict[hidden_resource]
    for resource in graphdict:
        for hidden_resource in tfdata["hidden"]:
            if hidden_resource in graphdict[resource]:
                graphdict[resource].remove(hidden_resource)
    tfdata["graphdict"] = graphdict
    click.echo(click.style(f"\nUnprocessed Graph Dictionary:", fg="white", bold=True))
    print(json.dumps(tfdata["graphdict"], indent=4, sort_keys=True))
    # Handle consolidated nodes where nodes are grouped into one node
    tfdata = consolidate_nodes(tfdata)
    # Handle automatic and user annotations
    tfdata = annotations.add_annotations(tfdata)
    # Handle special relationships that require additional logic
    tfdata = handle_special_resources(tfdata)
    # Handle multiple resources created by count attribute
    tfdata = create_multiple_resources(tfdata)
    # Handle special node variants
    tfdata = handle_variants(tfdata)
    # Dump graphdict
    click.echo(click.style(f"\nFinal Graphviz Input Dictionary", fg="white", bold=True))
    tfdata["graphdict"] = helpers.sort_graphdict(tfdata["graphdict"])
    print(json.dumps(tfdata["graphdict"], indent=4, sort_keys=True))
    with open("data.json", "w") as f:
        json.dump(tfdata["graphdict"], f, indent=4, sort_keys=True)
    return tfdata


def consolidate_nodes(tfdata: dict):
    for resource in dict(tfdata["graphdict"]):
        consolidated_name = helpers.consolidated_node_check(resource)
        if consolidated_name:
            if not tfdata["graphdict"].get(consolidated_name):
                tfdata["graphdict"][consolidated_name] = list()
                if not tfdata["graphdict"].get(consolidated_name):
                    tfdata["meta_data"][consolidated_name] = dict()
            tfdata["meta_data"][consolidated_name] = dict(
                tfdata["meta_data"][consolidated_name] | tfdata["meta_data"][resource]
            )
            tfdata["graphdict"][consolidated_name] = list(
                set(tfdata["graphdict"][consolidated_name])
                | set(tfdata["graphdict"][resource])
            )
            del tfdata["graphdict"][resource]
            del tfdata["meta_data"][resource]
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


def handle_variants(tfdata: dict):
    # Loop through all top level nodes and rename if variants exist
    for node in dict(tfdata["graphdict"]):
        node_title = node.split(".")[1]
        node_name = node.split("-")[0]
        renamed_node = helpers.check_variant(node, tfdata["meta_data"][node_name])
        if renamed_node and node.split(".")[0] not in SPECIAL_RESOURCES.keys():
            renamed_node = renamed_node + "." + node_title
            tfdata["graphdict"][renamed_node] = list(tfdata["graphdict"][node])
            del tfdata["graphdict"][node]
        else:
            renamed_node = node
        # Go through each connection and rename
        for resource in list(tfdata["graphdict"][renamed_node]):
            variant_suffix = helpers.check_variant(
                resource, tfdata["meta_data"][resource.split("-")[0]]
            )
            variant_label = resource.split(".")[1]
            if (
                variant_suffix
                and resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
                and not renamed_node.startswith("aws_group.shared")
                and (
                    resource not in tfdata["graphdict"]["aws_group.shared_services"]
                    or "-" in node
                ) and resource.split('.')[0] != node.split('.')[0]
            ):
                new_list = list(tfdata["graphdict"][renamed_node])
                new_list.remove(resource)
                node_title = resource.split(".")[1]
                new_list.append(variant_suffix + "." + variant_label)
                tfdata["graphdict"][renamed_node] = new_list
    return tfdata


# Loop through every connected node that has a count >0 and add suffix -i where i is the source node prefix
def add_number_suffix(i: int, check_multiple_resource: str, tfdata: dict):
    if not tfdata["graphdict"].get(check_multiple_resource):
        return []
    # Loop through each connection for this target resource
    new_list = list(tfdata["graphdict"][check_multiple_resource])
    for resource in list(tfdata["graphdict"][check_multiple_resource]):
        if "-" in resource:
            continue
        if tfdata["meta_data"].get(resource):
            new_name = resource + "-" + str(i)
            if (
                needs_multiple(resource, tfdata)
                and new_name not in tfdata["graphdict"][check_multiple_resource]
            ):
                new_list.append(new_name)
                new_list.remove(resource)
    return new_list


def needs_multiple(resource: str, tfdata):
    target_resource = (
        helpers.consolidated_node_check(resource)
        if helpers.consolidated_node_check(resource)
        else resource
    )
    parents_list = helpers.list_of_parents(tfdata["graphdict"], target_resource)
    any_parent_has_count = False
    # Check if any of the parents of the connections have a count property
    for parent in parents_list:
        if (
            tfdata["meta_data"].get(parent) and tfdata["meta_data"][parent].get("count")
        ) or "-" in parent:
            any_parent_has_count = True
    target_is_group = target_resource.split(".")[0] in GROUP_NODES
    target_has_count = (
        tfdata["meta_data"][target_resource].get("count")
        and tfdata["meta_data"][target_resource].get("count") > 1
    )
    not_already_multiple = "-" not in target_resource
    no_special_handler = (
        resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
        or resource.split(".")[0] in GROUP_NODES
    )
    not_shared_service = resource.split(".")[0] not in SHARED_SERVICES
    not_consolidated_node = False if helpers.consolidated_node_check(resource) else True
    parent_type_same = resource.split('.')[0] in resource.split('.')[0]
    if (
        ((target_is_group and target_has_count) or any_parent_has_count)
        and not_already_multiple
        and no_special_handler
        and not_shared_service
    ):
        return True
    return False


def create_multiple_resources(tfdata):
    # Get a list of all potential resources with a positive count attribute
    multi_resources = [
        k
        for k, v in tfdata["meta_data"].items()
        if "count" in v
        and isinstance(tfdata["meta_data"][k]["count"], int)
        and tfdata["meta_data"][k]["count"] > 1
    ]
    # Loop and for each one, create multiple nodes for the resource and any connections it has
    for resource in multi_resources:
        for i in range(tfdata["meta_data"][resource]["count"]):
            parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
            resource_i = add_number_suffix(i + 1, resource, tfdata)
            if resource_i:
                tfdata["graphdict"][resource + "-" + str(i + 1)] = resource_i
                tfdata["meta_data"][resource + "-" + str(i + 1)] = tfdata["meta_data"][
                    resource
                ]
                # Add numbered name to all original parents
                for parent in parents_list:
                    suffixed_name = resource + "-" + str(i + 1)
                    if (
                        tfdata["meta_data"].get(parent)
                        and (
                            not tfdata["meta_data"][parent].get("count")
                            or tfdata["meta_data"][parent].get("count") == 1
                        )
                        and not parent.startswith("aws_group.shared")
                    ):
                        tfdata["graphdict"][parent].append(suffixed_name)
                # Check if numbered suffix node exists as a node on its own in graphdict and create if necessary
                for numbered_node in resource_i:
                    original_name = numbered_node.split("-")[0]
                    if (
                        "-" in numbered_node
                        and helpers.list_of_dictkeys_containing(
                            tfdata["graphdict"], original_name
                        )
                        and original_name not in multi_resources and
                        not helpers.consolidated_node_check(original_name)
                    ):
                        if i == 0:
                            if tfdata["graphdict"].get(original_name):
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][original_name]
                                )
                                del tfdata["graphdict"][original_name]
                        else:
                            if tfdata["graphdict"].get(original_name + "-" + str(i)):
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][original_name + "-" + str(i)]
                                )
                            else:
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][original_name]
                                )
        if tfdata["graphdict"].get(resource):
            del tfdata["graphdict"][resource]
    # Now remove the original resource names
    for resource in multi_resources:
        parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
        for parent in parents_list:
            if (
                resource in tfdata["graphdict"][parent]
                and not parent.startswith("aws_group.shared")
                and not "-" in parent
            ):
                tfdata["graphdict"][parent].remove(resource)
    return tfdata


def handle_special_resources(tfdata: dict):
    resource_types = [k.split(".")[0] for k in tfdata["node_list"]]
    for resource_prefix, handler in SPECIAL_RESOURCES.items():
        matching_substring = [s for s in resource_types if resource_prefix in s]
        if resource_prefix in resource_types or matching_substring:
            tfdata = getattr(resource_handlers, handler)(tfdata)
    return tfdata


# Generator function to crawl entire dict and load all dict and list values
def dict_generator(indict, pre=None):
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


# Function to check whether a particular resource mentions another known resource (relationship)
def check_relationship(
    listitem: str, plist: list, nodes: list, hidden: dict
):  # -> list
    connection_list = []
    resource_name = helpers.cleanup(listitem)
    resource_associated_with = plist[1] + "." + plist[2]
    # Check if an existing node name appears in parameters of current resource being checked
    matching = [s for s in nodes if s in resource_name]
    # Check if there are any implied connections based on keywords in the param list
    if not matching:
        found_connection = [s for s in IMPLIED_CONNECTIONS.keys() if s in resource_name]
        if found_connection:
            for n in nodes:
                if n.startswith(IMPLIED_CONNECTIONS[found_connection[0]]):
                    matching = [n]
    if matching:
        for matched_resource in matching:
            reverse = False
            matched_type = matched_resource.split(".")[0]
            if (
                matched_resource not in hidden
                and resource_associated_with not in hidden
            ):
                reverse_origin_match = [
                    s for s in REVERSE_ARROW_LIST if s in resource_name
                ]
                if len(reverse_origin_match) > 0:
                    reverse = True
                    reverse_dest_match = [
                        s for s in REVERSE_ARROW_LIST if s in resource_associated_with
                    ]
                    if len(reverse_dest_match) > 0:
                        if REVERSE_ARROW_LIST.index(
                            reverse_dest_match[0]
                        ) < REVERSE_ARROW_LIST.index(reverse_origin_match[0]):
                            reverse = False
                if reverse:
                    connection_list.append(matched_resource)
                    connection_list.append(resource_associated_with)
                    # Output relationship to console log in reverse order for certain group nodes
                    click.echo(
                        f"   {matched_resource} --> {resource_associated_with} (Reversed)"
                    )
                else:  # Exception Ignore outgoing connections mentioned in depends on
                    if listitem in plist:
                        i = plist.index(listitem)
                        if plist[3] == "depends_on":
                            continue
                    connection_list.append(resource_associated_with)
                    connection_list.append(matched_resource)
                    click.echo(f"   {resource_associated_with} --> {matched_resource}")
    return connection_list
