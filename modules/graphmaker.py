from math import e
from numpy import delete
import click
import modules.cloud_config as cloud_config
from modules.drawing import EDGE_NODES
import modules.helpers as helpers
import modules.resource_handlers as resource_handlers
import modules.interpreter as interpreter

REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AWS_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.AWS_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.AWS_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.AWS_SHARED_SERVICES
AUTO_ANNOTATIONS = cloud_config.AWS_AUTO_ANNOTATIONS
EDGE_NODES = cloud_config.AWS_EDGE_NODES
FORCED_DEST = cloud_config.AWS_FORCED_DEST
FORCED_ORIGIN = cloud_config.AWS_FORCED_ORIGIN


def supplement_graph_dict(tfdata, debug):
    # Load default variable values and user variable values
    tfdata = interpreter.get_variable_values(tfdata)
    # Create view of locals by module
    tfdata = interpreter.extract_locals(tfdata)
    # Create metadata view from nested TF file resource attributes
    tfdata = interpreter.get_metadata(tfdata)
    # Replace metadata (resource attributes) variables and locals with actual values
    tfdata = interpreter.handle_metadata_vars(tfdata)
    # Inject parent module variables that are referenced downstream in sub modules
    if "all_module" in tfdata.keys():
        tfdata = interpreter.inject_module_variables(tfdata)
    # Dump out findings after file scans are complete
    if debug:
        helpers.output_log(tfdata)
    # Append additional relationships to Graph Data Structure in the format {node: [connected_node1,connected_node2]}
    tfdata = add_relations(tfdata)
    return tfdata


def reverse_relations(tfdata: dict) -> dict:
    for node, connections in dict(tfdata["graphdict"]).items():
        reverse_dest = len([s for s in FORCED_DEST if node.startswith(s)]) > 0
        for c in list(connections):
            if reverse_dest:
                tfdata["graphdict"][c].append(node)
                tfdata["graphdict"][node].remove(c)
            reverse_origin = (
                len(
                    [
                        s
                        for s in FORCED_ORIGIN
                        if c.startswith(s)
                        and not node.split(".")[0] in str(AUTO_ANNOTATIONS)
                    ]
                )
                > 0
            )
            if reverse_origin:
                tfdata["graphdict"][c].append(node)
                tfdata["graphdict"][node].remove(c)
    return tfdata


# Function to check whether a particular resource mentions another known resource (relationship)
# Returns a list containing pairs of related nodes where index i an i+i are related
def check_relationship(
    resource_associated_with: str, plist: list, tfdata: dict
):  # -> list
    nodes = tfdata["node_list"]
    hidden = tfdata["hidden"]
    connection_pairs = list()
    # Check if an existing node name appears in parameters of current resource being checked to reduce search scope
    for param in plist:
        # List comprehension of unique nodes referenced in the parameter
        matching = list({s for s in nodes if s.split("-")[0] in param})
        # Check if there are any implied connections based on keywords in the param list
        found_connection = list({s for s in IMPLIED_CONNECTIONS.keys() if s in param})
        if found_connection:
            for n in nodes:
                if (
                    n.startswith(IMPLIED_CONNECTIONS[found_connection[0]])
                    and n not in matching
                ):
                    matching.append(n)
        if matching:
            for matched_resource in matching:
                reverse = False
                if (
                    matched_resource not in hidden
                    and resource_associated_with not in hidden
                ):
                    reverse_origin_match = [s for s in REVERSE_ARROW_LIST if s in param]
                    if len(reverse_origin_match) > 0:
                        reverse = True
                        # Don't reverse if the reverse relationship will occur twice on both sides
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
                    # Make sure numbered nodes are associated with a connection of the same number
                    if "-" in matched_resource and "-" in resource_associated_with:
                        matched_resource_no = matched_resource.split("-")[1]
                        resource_associated_with_no = resource_associated_with.split(
                            "-"
                        )[1]
                        if matched_resource_no != resource_associated_with_no:
                            continue
                    if reverse:
                        if (
                            resource_associated_with
                            not in tfdata["graphdict"][matched_resource]
                            and matched_resource
                            not in tfdata["graphdict"][resource_associated_with]
                        ):
                            connection_pairs.append(matched_resource)
                            connection_pairs.append(resource_associated_with)

                    else:
                        if (
                            matched_resource
                            not in tfdata["graphdict"][resource_associated_with]
                            and resource_associated_with
                            not in tfdata["graphdict"][matched_resource]
                        ):
                            connection_pairs.append(resource_associated_with)
                            connection_pairs.append(matched_resource)
    return connection_pairs


# Make final graph structure to be used for drawing
def add_relations(tfdata: dict):
    # Start with an existing connections list for all nodes/resources we know about
    graphdict = dict(tfdata["graphdict"])
    created_resources = len(tfdata["node_list"])
    click.echo(
        click.style(
            f"\nChecking for additional links between {created_resources} resources..",
            fg="white",
            bold=True,
        )
    )
    # Determine relationship between resources and append to graphdict when found
    for node in tfdata["node_list"]:
        if node not in tfdata["meta_data"].keys():
            nodename = node.split("-")[0]
        else:
            nodename = node
        if nodename.startswith("random") or node.startswith("aws_security_group"):
            continue
        for param_item_list in dict_generator(tfdata["meta_data"][nodename]):
            matching_result = check_relationship(
                node,
                param_item_list,
                tfdata,
            )
            if matching_result:
                for i in range(0, len(matching_result), 2):
                    origin = matching_result[i]
                    dest = matching_result[i + 1]
                    c_list = list(graphdict[origin])
                    if not dest in c_list and not origin.startswith(
                        "aws_security_group"
                    ):
                        click.echo(f"   {origin} --> {dest}")
                        c_list.append(dest)
                        if (
                            "-" in origin
                            and "-" in dest
                            and dest.split("-")[0] in c_list
                        ):
                            c_list.remove(dest.split("-")[0])
                    graphdict[origin] = c_list
    # Hide nodes where specified
    for hidden_resource in tfdata["hidden"]:
        del graphdict[hidden_resource]
    for resource in graphdict:
        for hidden_resource in tfdata["hidden"]:
            if hidden_resource in graphdict[resource]:
                graphdict[resource].remove(hidden_resource)
    tfdata["graphdict"] = graphdict
    return tfdata


def consolidate_nodes(tfdata: dict):
    for resource in dict(tfdata["graphdict"]):
        if resource not in tfdata["meta_data"].keys():
            res = resource.split("-")[0]
        else:
            res = resource
        consolidated_name = helpers.consolidated_node_check(resource)
        if consolidated_name:
            if not tfdata["graphdict"].get(consolidated_name):
                tfdata["graphdict"][consolidated_name] = list()
                tfdata["meta_data"][consolidated_name] = dict()
            original_count = tfdata["meta_data"][res].get("count")
            merged_count = tfdata["meta_data"][consolidated_name].get("count")
            if original_count and not merged_count:
                saved_count = original_count
            tfdata["meta_data"][consolidated_name] = dict(
                tfdata["meta_data"][consolidated_name] | tfdata["meta_data"][res]
            )
            # Don't over-ride count values with 0 when merging
            tfdata["graphdict"][consolidated_name] = list(
                set(tfdata["graphdict"][consolidated_name])
                | set(tfdata["graphdict"][resource])
            )
            del tfdata["graphdict"][resource]
            del tfdata["meta_data"][res]
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
        if resource.startswith("null_resource"):
            del tfdata["graphdict"][resource]
    tfdata["graphdict"] = tfdata["graphdict"]
    return tfdata


def handle_variants(tfdata: dict):
    # Loop through all top level nodes and rename if variants exist
    for node in dict(tfdata["graphdict"]):
        node_title = node.split(".")[1]
        if node[-1].isdigit() and node[-2] == "-":
            node_name = node.split("-")[0]
        else:
            node_name = node
        if node_name.startswith("aws"):
            renamed_node = helpers.check_variant(
                node, tfdata["meta_data"].get(node_name)
            )
        else:
            renamed_node = False
        if renamed_node and node.split(".")[0] not in SPECIAL_RESOURCES.keys():
            renamed_node = renamed_node + "." + node_title
            tfdata["graphdict"][renamed_node] = list(tfdata["graphdict"][node])
            del tfdata["graphdict"][node]
        else:
            renamed_node = node
        # Go through each connection and rename
        for resource in list(tfdata["graphdict"][renamed_node]):
            if "-" in resource:
                if resource[-1].isdigit() and resource[-2] == "-":
                    resource_name = resource.split("-")[0]
            else:
                resource_name = resource
                variant_suffix = ""
            if resource_name.startswith("aws"):
                variant_suffix = helpers.check_variant(
                    resource, tfdata["meta_data"].get(resource_name)
                )
                variant_label = resource.split(".")[1]
            if (
                variant_suffix
                and resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
                and not renamed_node.startswith("aws_group.shared")
                and (
                    resource not in tfdata["graphdict"]["aws_group.shared_services"]
                    or "-" in node
                )
                and resource.split(".")[0] != node.split(".")[0]
            ):
                new_list = list(tfdata["graphdict"][renamed_node])
                new_list.remove(resource)
                node_title = resource.split(".")[1]
                new_list.append(variant_suffix + "." + variant_label)
                tfdata["graphdict"][renamed_node] = new_list
    return tfdata


def needs_multiple(resource: str, parent: str, tfdata):
    target_resource = (
        helpers.consolidated_node_check(resource)
        if helpers.consolidated_node_check(resource)
        else resource
    )
    any_parent_has_count = helpers.any_parent_has_count(tfdata, resource)
    target_is_group = target_resource.split(".")[0] in GROUP_NODES
    target_has_count = "-" in target_resource
    not_already_multiple = "-" not in target_resource
    no_special_handler = (
        resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
        or resource.split(".")[0] in GROUP_NODES
    )
    not_shared_service = resource.split(".")[0] not in SHARED_SERVICES
    security_group_with_count = (
        "-" in parent and resource.split(".")[0] == "aws_security_group"
    )
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
            if "-" in parent:
                # We have a suffix so check it matches the i count
                existing_suffix = parent.split("-")[1]
                if existing_suffix == str(i + 1):
                    suffixed_name = resource + "-" + str(i + 1)
                else:
                    suffixed_name = resource + "-" + existing_suffix
            elif "-" not in resource:
                suffixed_name = resource + "-" + str(i + 1)
            else:
                suffixed_name = resource
            if (
                parent.split("-")[0] in tfdata["meta_data"].keys()
                and (tfdata["meta_data"][parent.split("-")[0]].get("count"))
                and not parent.startswith("aws_group.shared")
                and not suffixed_name in tfdata["graphdict"][parent]
                and not ("cluster" in suffixed_name and "cluster" in parent)
                and "aws_route_table." not in resource
            ):
                # Handle special case for security groups where if any parent has count>1, then create a numbered sg
                if (
                    helpers.any_parent_has_count(tfdata, resource)
                    and parent.split(".")[0] == "aws_security_group"
                    and "-" not in parent
                ) or (
                    helpers.any_parent_has_count(tfdata, resource)
                    and parent.split(".")[0] == "aws_security_group"
                    and "-" in parent
                    and helpers.check_list_for_dash(tfdata["graphdict"][parent])
                ):
                    if (
                        parent + "-" + str(i + 1) not in tfdata["graphdict"].keys()
                        and "-" not in parent
                    ):
                        tfdata["graphdict"][parent + "-" + str(i + 1)] = list(
                            tfdata["graphdict"][parent]
                        )
                    if (
                        tfdata["graphdict"].get(parent + "-" + str(i + 1))
                        and "-" not in parent
                    ):
                        if (
                            suffixed_name
                            not in tfdata["graphdict"][parent + "-" + str(i + 1)]
                            # and "aws_security_group" not in suffixed_name.split(".")[0]
                        ):
                            tfdata["graphdict"][parent + "-" + str(i + 1)].append(
                                suffixed_name
                            )
                        if resource in tfdata["graphdict"][parent + "-" + str(i + 1)]:
                            tfdata["graphdict"][parent + "-" + str(i + 1)].remove(
                                resource
                            )
                        tfdata["meta_data"][parent + "-" + str(i + 1)] = tfdata[
                            "meta_data"
                        ][parent]
                else:
                    if resource in tfdata["graphdict"][parent]:
                        tfdata["graphdict"][parent].remove(resource)
                    for sim in tfdata["graphdict"][parent]:
                        if sim.split("-")[0] == suffixed_name.split("-")[0]:
                            tfdata["graphdict"][parent].remove(sim)
                    tfdata["graphdict"][parent].append(suffixed_name)

    return tfdata


def cleanup_originals(multi_resources: list, tfdata: dict):
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
                and not "-" in parent
            ):
                tfdata["graphdict"][parent].remove(resource)
    # Delete any original security group nodes that have been replaced with numbered suffixes
    security_group_list = [
        k
        for k in tfdata["graphdict"]
        if k.startswith("aws_security_group") and "-" in k
    ]
    for security_group in security_group_list:
        check_original = security_group.split("-")[0]
        if check_original in tfdata["graphdict"].keys():
            del tfdata["graphdict"][check_original]
    return tfdata


# Handle resources which require pre/post-processing before/after being added to graphdict
def handle_special_resources(tfdata: dict):
    resource_types = list({k.split(".")[0] for k in tfdata["node_list"]})
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


# Loop through every connected node that has a count >0 and add suffix -i where i is the source node prefix
def add_number_suffix(i: int, check_multiple_resource: str, tfdata: dict):
    if not helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], check_multiple_resource
    ):
        return list()
    # Loop through each connection for this target resource
    new_list = list(tfdata["graphdict"][check_multiple_resource])
    for resource in list(tfdata["graphdict"][check_multiple_resource]):
        if "-" in resource:
            continue
        if tfdata["meta_data"].get(resource):
            new_name = resource + "-" + str(i)
            if (
                needs_multiple(resource, check_multiple_resource, tfdata)
                and new_name not in tfdata["graphdict"][check_multiple_resource]
                and new_name not in new_list
            ) or new_name in tfdata["graphdict"].keys():
                new_list.append(new_name)
                new_list.remove(resource)
    return new_list


def needs_multiple(resource: str, parent: str, tfdata):
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
        and tfdata["meta_data"][target_resource].get("count") >= 1
    )
    not_already_multiple = "-" not in target_resource
    no_special_handler = (
        resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
        or resource.split(".")[0] in GROUP_NODES
    )
    not_shared_service = resource.split(".")[0] not in SHARED_SERVICES
    if resource.split(".")[0] == "aws_security_group":
        security_group_with_count = (
            tfdata["original_metadata"][parent].get("count")
            and tfdata["original_metadata"][parent].get("count") > 1
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


def extend_sg_groups(tfdata: dict) -> dict:
    list_of_sgs = [s for s in tfdata["graphdict"] if s.startswith("aws_security_group")]
    for sg in list_of_sgs:
        expanded = False
        for connection in list(tfdata["graphdict"][sg]):
            if "-" in connection and "-" not in sg:
                expanded = True
                suffixed_sg = sg + "-" + connection.split("-")[1]
                tfdata["graphdict"][suffixed_sg] = list([connection])
                tfdata["graphdict"][sg].remove(connection)
        if expanded:
            also_connected = helpers.list_of_parents(tfdata["graphdict"], sg)
            for node in also_connected:
                if "-" in node:
                    suffixed_sg = sg + "-" + node.split("-")[1]
                    tfdata["graphdict"][node].remove(sg)
                    tfdata["graphdict"][node].append(suffixed_sg)
                    # check if other multiples of the node also have the relationship, if not, add it
                    if "-1" in node:
                        i = 2
                        next_node = node.split("-")[0] + "-" + str(i)
                        next_sg = sg + "-" + str(i)
                        while (
                            next_node in tfdata["graphdict"].keys()
                            and next_sg in tfdata["graphdict"].keys()
                        ):
                            if not next_sg in tfdata["graphdict"][next_node]:
                                tfdata["graphdict"][next_node].append(next_sg)
                            i = i + 1
                            next_node = node.split("-")[0] + "-" + str(i)
                            next_sg = sg + "-" + str(i)
            del tfdata["graphdict"][sg]

    return tfdata


def add_multiples_to_parents(
    i: int, resource: str, multi_resources: list, tfdata: dict
):
    parents_list = helpers.list_of_parents(tfdata["graphdict"], resource)
    # Add numbered name to all original parents which may have been missed due to no count property
    for parent in parents_list:
        if parent not in multi_resources:
            if "-" in parent:
                # We have a suffix so check it matches the i count
                existing_suffix = parent.split("-")[1]
                if existing_suffix == str(i + 1):
                    suffixed_name = resource + "-" + str(i + 1)
                else:
                    suffixed_name = resource + "-" + existing_suffix
            else:
                suffixed_name = resource + "-" + str(i + 1)
            if (
                parent.split("-")[0] in tfdata["meta_data"].keys()
                and (
                    not tfdata["meta_data"][parent.split("-")[0]].get("count")
                    or tfdata["meta_data"][parent.split("-")[0]].get("count") == 1
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


def handle_count_resources(multi_resources: list, tfdata: dict):
    # Loop nodes and for each one, create multiple nodes for the resource and its connections where needed
    for resource in multi_resources:
        for i in range(tfdata["meta_data"][resource]["count"]):
            # Get connections replaced with numbered suffixes
            resource_i = add_number_suffix(i + 1, resource, tfdata)
            not_shared_service = not resource.split(".")[0] in SHARED_SERVICES
            if not_shared_service:
                # Create a top level node with number suffix and connect to numbered connections
                tfdata["graphdict"][resource + "-" + str(i + 1)] = resource_i
                tfdata["meta_data"][resource + "-" + str(i + 1)] = tfdata["meta_data"][
                    resource
                ]
                tfdata = add_multiples_to_parents(i, resource, multi_resources, tfdata)
                # Check if numbered connection node exists as a top level node in graphdict and create if necessary
                for numbered_node in resource_i:
                    original_name = numbered_node.split("-")[0]
                    if (
                        "-" in numbered_node
                        and helpers.list_of_dictkeys_containing(
                            tfdata["graphdict"], original_name
                        )
                        and original_name not in multi_resources
                        and not helpers.consolidated_node_check(original_name)
                    ):
                        if i == 0:
                            if (
                                original_name in tfdata["graphdict"].keys()
                                and original_name + "-1"
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
                            if (original_name + "-" + str(i)) in tfdata[
                                "graphdict"
                            ] and numbered_node not in tfdata["graphdict"]:
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][original_name + "-" + str(i)]
                                )
                            else:
                                tfdata["graphdict"][numbered_node] = list(
                                    tfdata["graphdict"][
                                        original_name + "-" + str(i + 1)
                                    ]
                                )
                            tfdata = add_multiples_to_parents(
                                i, original_name, multi_resources, tfdata
                            )
    return tfdata


def handle_singular_references(tfdata: dict) -> dict:
    for node, connections in dict(tfdata["graphdict"]).items():
        for c in list(connections):
            if "-" in node and not "-" in c:
                suffix = node.split("-")[1]
                suffixed_node = f"{c}-{suffix}"
                if suffixed_node in tfdata["graphdict"]:
                    tfdata["graphdict"][node].append(suffixed_node)
                    tfdata["graphdict"][node].remove(c)

    return tfdata


def create_multiple_resources(tfdata):
    # Get a list of all potential resources with a >1 count attribute
    multi_resources = [
        n
        for n in tfdata["graphdict"]
        if (
            "-" not in n
            and tfdata["meta_data"].get(n)
            and tfdata["meta_data"][n].get("count")
        )
    ]
    # Create multiple nodes for count resources as necessary
    tfdata = handle_count_resources(multi_resources, tfdata)
    # Replace links to single nodes with multi nodes if they exist
    tfdata = handle_singular_references(tfdata)
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
                and not "-" in parent
            ):
                tfdata["graphdict"][parent].remove(resource)
    # Delete any original security group nodes that have been replaced with numbered suffixes
    security_group_list = [
        k
        for k in tfdata["graphdict"]
        if k.startswith("aws_security_group") and "-" in k
    ]
    for security_group in security_group_list:
        check_original = security_group.split("-")[0]
        if check_original in tfdata["graphdict"].keys():
            del tfdata["graphdict"][check_original]
    # Handle creation of multiple sgs where needed
    tfdata = extend_sg_groups(tfdata)
    return tfdata
