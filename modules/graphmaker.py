from math import e
import click
import re
import json
import modules.cloud_config as cloud_config
import modules.helpers as helpers
import modules.resource_handlers as resource_handlers
from typing import Dict, List

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


def reverse_relations(tfdata: dict) -> dict:
    for n, connections in dict(tfdata["graphdict"]).items():
        node = helpers.get_no_module_name(n)
        reverse_dest = len([s for s in FORCED_DEST if node.startswith(s)]) > 0
        for c in list(connections):
            if reverse_dest:
                if not tfdata["graphdict"].get(c):
                    tfdata["graphdict"][c] = list()
                tfdata["graphdict"][c].append(n)
                tfdata["graphdict"][n].remove(c)
            reverse_origin = (
                len(
                    [
                        s
                        for s in FORCED_ORIGIN
                        if helpers.get_no_module_name(c).startswith(s)
                        and not node.split(".")[0] in str(AUTO_ANNOTATIONS)
                    ]
                )
                > 0
            )
            if reverse_origin:
                tfdata["graphdict"][c].append(n)
                tfdata["graphdict"][node].remove(c)
    return tfdata


# Function to check whether a particular resource mentions another known resource (relationship)
# Returns a list containing pairs of related nodes where index i an i+i are related
def check_relationship(
    resource_associated_with: str, plist: list, tfdata: dict
) -> list:
    nodes = tfdata["node_list"]
    hidden = tfdata["hidden"]
    connection_pairs = list()
    # Check if an existing node name appears in parameters of current resource being checked to reduce search scope
    for param in plist:
        # List comprehension of unique nodes referenced in the parameter
        if "[" in str(param):
            matching = list(
                {
                    s
                    for s in nodes
                    if helpers.remove_numbered_suffix(s) in str(param).replace(".*", "")
                }
            )
        else:
            if helpers.extract_terraform_resource(str(param)):
                matching = list(
                    {
                        s
                        for s in nodes
                        if helpers.extract_terraform_resource(str(param)) in s
                        or helpers.cleanup_curlies(str(param)) in s
                    }
                )
            else:
                matching = []
        # Check if there are any implied connections based on keywords in the param list
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
        if matching:
            for matched_resource in matching:
                reverse = False
                if (
                    matched_resource not in hidden
                    and resource_associated_with not in hidden
                ):
                    reverse_origin_match = [
                        s for s in REVERSE_ARROW_LIST if s in str(param)
                    ]
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
                    if "~" in matched_resource and "~" in resource_associated_with:
                        matched_resource_no = matched_resource.split("~")[1]
                        resource_associated_with_no = resource_associated_with.split(
                            "~"
                        )[1]
                        if matched_resource_no != resource_associated_with_no:
                            continue
                    # Reverse match order for certain resources
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
            nodename = node.split("~")[0]
            if "[" in nodename:
                nodename = nodename.split("[")[0]
        else:
            nodename = node

        if (
            helpers.get_no_module_name(nodename).startswith("random")
            or helpers.get_no_module_name(node).startswith("aws_security_group")
            or helpers.get_no_module_name(node).startswith("null")
        ):
            continue
        if nodename not in tfdata["meta_data"].keys():
            dg = dict_generator(tfdata["original_metadata"][node])
            tfdata["meta_data"][node] = tfdata["original_metadata"][node]
        else:
            dg = dict_generator(tfdata["meta_data"][nodename])
        for param_item_list in dg:
            matching_result = check_relationship(
                node,
                param_item_list,
                tfdata,
            )
            if matching_result and len(matching_result) >= 2:
                for i in range(0, len(matching_result), 2):
                    origin = matching_result[i]
                    dest = matching_result[i + 1]
                    c_list = list(graphdict[origin])
                    if not dest in c_list and not helpers.get_no_module_name(
                        origin
                    ).startswith("aws_security_group"):
                        click.echo(f"   {origin} --> {dest}")
                        c_list.append(dest)
                        if (
                            "~" in origin
                            and "~" in dest
                            and dest.split("~")[0] in c_list
                        ):
                            c_list.remove(dest.split("~")[0])
                    graphdict[origin] = c_list
    # Hide nodes where specified
    for hidden_resource in tfdata["hidden"]:
        del graphdict[hidden_resource]
    for resource in graphdict:
        for hidden_resource in tfdata["hidden"]:
            if hidden_resource in graphdict[resource]:
                graphdict[resource].remove(hidden_resource)
    tfdata["graphdict"] = graphdict
    tfdata["original_graphdict_with_relations"] = graphdict
    return tfdata


def consolidate_nodes(tfdata: dict):
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
            resdata = tfdata["meta_data"].get(res)
        else:
            resdata = tfdata["meta_data"][resource]
        consolidated_name = helpers.consolidated_node_check(resource)
        if consolidated_name:
            if not tfdata["meta_data"].get(consolidated_name):
                tfdata["graphdict"][consolidated_name] = list()
                tfdata["meta_data"][consolidated_name] = dict()
            tfdata["meta_data"][consolidated_name] = dict(
                tfdata["meta_data"][consolidated_name] | resdata
            )
            # Don't over-ride count values with 0 when merging
            if consolidated_name not in tfdata["graphdict"].keys():
                tfdata["graphdict"][consolidated_name] = list()
            tfdata["graphdict"][consolidated_name]
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


def match_resources(tfdata: dict) -> dict:
    """
    Match resources based on their suffix pattern (~N) and indirect dependencies to their corresponding parents.
    """
    tfdata["graphdict"] = match_az_to_subnets(tfdata["graphdict"])
    tfdata["graphdict"] = link_ec2_to_iam_roles(tfdata["graphdict"])
    tfdata["graphdict"] = split_nat_gateways(tfdata["graphdict"])
    return tfdata


def split_nat_gateways(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Split NAT gateways into multiple instances and update subnet references.
    """
    result = dict(terraform_data)
    suffix_pattern = r"~(\d+)$"

    # Find NAT gateways and count related subnets
    nat_gateways = [
        k for k in terraform_data.keys() if "aws_nat_gateway" in k and "~" not in k
    ]

    for nat_gw in nat_gateways:
        # Find public subnets that reference this NAT gateway
        subnet_suffixes = set()
        for resource, deps in terraform_data.items():
            if "public_subnets" in resource and "~" in resource:
                match = re.search(suffix_pattern, resource)
                if match and nat_gw in deps:
                    subnet_suffixes.add(match.group(1))

        # Create numbered NAT gateways
        for suffix in subnet_suffixes:
            nat_gw_numbered = f"{nat_gw}~{suffix}"
            result[nat_gw_numbered] = list(terraform_data[nat_gw])

        # Remove original NAT gateway if we created numbered ones
        if subnet_suffixes:
            del result[nat_gw]

    # Update subnet references to use numbered NAT gateways
    for resource, deps in result.items():
        if "public_subnets" in resource and "~" in resource:
            match = re.search(suffix_pattern, resource)
            if match:
                suffix = match.group(1)
                new_deps = []
                for dep in deps:
                    if "aws_nat_gateway" in dep and "~" not in dep:
                        new_deps.append(f"{dep}~{suffix}")
                    else:
                        new_deps.append(dep)
                result[resource] = new_deps

    return result


def link_ec2_to_iam_roles(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Add EC2 instances as dependencies to IAM roles when connected through instance profiles.
    """
    result = dict(terraform_data)

    # Find IAM roles that connect to instance profiles
    profile_to_role = {}
    for resource, deps in terraform_data.items():
        if "aws_iam_role" in resource:
            for dep in deps:
                if "aws_iam_instance_profile" in dep:
                    profile_to_role[dep] = resource

    # Find instance profiles that connect to EC2 instances and add EC2 to IAM role deps
    for resource, deps in terraform_data.items():
        if "aws_iam_instance_profile" in resource and resource in profile_to_role:
            iam_role = profile_to_role[resource]
            for dep in deps:
                if "aws_instance" in dep and dep not in result[iam_role]:
                    result[iam_role].append(dep)

    return result


def match_az_to_subnets(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Transform Terraform resource associations to match availability zones
    with their corresponding subnets based on suffix pattern (~N).

    Args:
        terraform_data: Dictionary of Terraform resources and their associations

    Returns:
        Complete dictionary with AZ resources updated and all other resources intact
    """
    result = dict(terraform_data)

    # Pattern to extract suffix from resource names
    suffix_pattern = r"~(\d+)$"

    # Find all availability zones
    az_resources = [
        key
        for key in terraform_data.keys()
        if key.startswith("aws_az.availability_zone")
    ]

    for az in az_resources:
        # Extract suffix from AZ name
        az_match = re.search(suffix_pattern, az)
        if not az_match:
            continue

        az_suffix = az_match.group(1)

        # Get all dependencies of this AZ
        az_dependencies = terraform_data.get(az, [])

        # Filter subnets that have matching suffix
        matched_subnets = []
        for dep in az_dependencies:
            if "subnet" in dep.lower():
                dep_match = re.search(suffix_pattern, dep)
                if dep_match and dep_match.group(1) == az_suffix:
                    matched_subnets.append(dep)

        # Update only the AZ entries with matched subnets
        result[az] = matched_subnets

    return result


def handle_variants(tfdata: dict):
    # Loop through all top level nodes and rename if variants exist
    for node in dict(tfdata["graphdict"]):
        node_title = helpers.get_no_module_name(node).split(".")[1]
        if node[-1].isdigit() and node[-2] == "~":
            node_name = node.split("~")[0]
        else:
            node_name = node
        if helpers.get_no_module_name(node_name).startswith("aws"):
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
                    resource_name = resource.split("~")[0]
            else:
                resource_name = resource
            if helpers.get_no_module_name(resource_name).startswith("aws"):
                variant_suffix = helpers.check_variant(
                    resource, tfdata["meta_data"].get(resource_name)
                )
                variant_label = resource.split(".")[1]
            if (
                variant_suffix
                and helpers.get_no_module_name(resource).split(".")[0]
                not in SPECIAL_RESOURCES.keys()
                and not renamed_node.startswith("aws_group.shared")
                and (
                    resource not in tfdata["graphdict"]["aws_group.shared_services"]
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
                tfdata["meta_data"][new_variant_name] = tfdata["meta_data"][resource]
    return tfdata


def needs_multiple(resource: str, parent: str, tfdata):
    target_resource = (
        helpers.consolidated_node_check(resource)
        if helpers.consolidated_node_check(resource)
        else resource
    )
    any_parent_has_count = helpers.any_parent_has_count(tfdata, resource)
    target_is_group = target_resource.split(".")[0] in GROUP_NODES
    target_has_count = "~" in target_resource
    not_already_multiple = "~" not in target_resource
    no_special_handler = (
        resource.split(".")[0] not in SPECIAL_RESOURCES.keys()
        or resource.split(".")[0] in GROUP_NODES
    )
    not_shared_service = resource.split(".")[0] not in SHARED_SERVICES
    security_group_with_count = (
        "~" in parent and resource.split(".")[0] == "aws_security_group"
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
                        tfdata["meta_data"][parent + "~" + str(i + 1)] = tfdata[
                            "meta_data"
                        ][parent]
                else:
                    if resource in tfdata["graphdict"][parent]:
                        tfdata["graphdict"][parent].remove(resource)
                    for sim in tfdata["graphdict"][parent]:
                        if sim.split("~")[0] == suffixed_name.split("~")[0]:
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
def handle_special_resources(tfdata: dict):
    resource_types = list(
        {helpers.get_no_module_name(k).split(".")[0] for k in tfdata["node_list"]}
    )
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


# Loop through every connected node that has a count >0 and add suffix ~i where i is the source node suffix
def add_number_suffix(i: int, check_multiple_resource: str, tfdata: dict):
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


def extend_sg_groups(tfdata: dict) -> dict:
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


def handle_count_resources(multi_resources: list, tfdata: dict):
    # Loop nodes and for each one, create multiple nodes for the resource and its connections where needed
    for resource in multi_resources:
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
        for i in range(max_i):
            # Get connections replaced with numbered suffixes
            resource_i = add_number_suffix(i + 1, resource, tfdata)
            not_shared_service = not resource.split(".")[0] in SHARED_SERVICES
            if not_shared_service:
                # Create a top level node with number suffix and connect to numbered connections
                tfdata["graphdict"][resource + "~" + str(i + 1)] = resource_i
                tfdata["meta_data"][resource + "~" + str(i + 1)] = tfdata["meta_data"][
                    resource
                ]
                tfdata = add_multiples_to_parents(i, resource, multi_resources, tfdata)
                # Check if numbered connection node exists as a top level node in graphdict and create if necessary
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


# Handle cases where a connection to only one of n numbered node exists
def handle_singular_references(tfdata: dict) -> dict:
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


def create_multiple_resources(tfdata):
    # Get a list of all potential resources with a count type attribute
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
    # Handle creation of multiple sgs where needed
    tfdata = extend_sg_groups(tfdata)
    return tfdata
