import modules.cloud_config as cloud_config
import modules.helpers as helpers
from ast import literal_eval
import re
from typing import Dict, List

REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AWS_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.AWS_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.AWS_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.AWS_SHARED_SERVICES


def aws_handle_autoscaling(tfdata: dict):
    try:
        # Check if any nodes in connection list are referenced by an autoscaling group
        scaler_links = next(
            v
            for k, v in tfdata["graphdict"].items()
            if "aws_appautoscaling_target" in k
        )
        asg_resources = [
            r
            for r in tfdata["graphdict"]
            if helpers.get_no_module_name(r).startswith("aws_appautoscaling_target")
        ]
        for asg in asg_resources:
            new_list = list()
            for check_service in scaler_links:
                possible_subnets = [
                    k
                    for k in tfdata["graphdict"]
                    if helpers.get_no_module_name(k).startswith("aws_subnet")
                ]
                for sub in possible_subnets:
                    if check_service in tfdata["graphdict"][sub]:
                        # this subnet is part of an autoscaling group so note it
                        new_list.append(sub)
                # Apply counts for subnets to the asg target
                for subnet in new_list:
                    if not tfdata["meta_data"][asg].get("count"):
                        tfdata["meta_data"][asg]["count"] = tfdata["meta_data"][subnet][
                            "count"
                        ]
                        tfdata["meta_data"][check_service]["count"] = tfdata[
                            "meta_data"
                        ][subnet]["count"]
    except:
        pass
    # Now replace any references within subnets to asg targets with the name of asg
    for asg in asg_resources:
        for connection in tfdata["graphdict"][asg]:
            asg_target_parents = helpers.list_of_parents(
                tfdata["graphdict"], connection
            )
            subnets_to_change = [
                k
                for k in asg_target_parents
                if helpers.get_no_module_name(k).startswith("aws_subnet")
            ]
            for subnet in subnets_to_change:
                if asg not in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].append(asg)
                tfdata["graphdict"][subnet].remove(connection)
            pass
    return tfdata


# Create link to CF if its domain name is referred to in other metadata
def handle_cloudfront_domains(origin_string: str, domain: str, mdata: dict) -> str:
    for key, value in mdata.items():
        for k, v in value.items():
            if (
                domain in str(v)
                and not domain.startswith("aws_")
                and not helpers.get_no_module_name(key).startswith("aws_cloudfront")
                and not helpers.get_no_module_name(key).startswith("aws_route53")
            ):
                o = origin_string.replace(domain, key)
                return origin_string.replace(domain, key)
    return origin_string


def handle_cloudfront_lbs(tfdata: dict) -> dict:
    cf_distros = [s for s in tfdata["graphdict"].keys() if "aws_cloudfront" in s]
    lbs = [s for s in tfdata["graphdict"].keys() if "aws_lb." in s]
    for node, connections in dict(tfdata["graphdict"]).items():
        for cf in cf_distros:
            if cf in connections:
                for lb in lbs:
                    if node in tfdata["graphdict"][lb]:
                        lb_parents = helpers.list_of_parents(tfdata["graphdict"], lb)
                        tfdata["graphdict"][cf].append(lb)
                        tfdata["graphdict"][node].remove(cf)
                        for parent in lb_parents:
                            if (
                                helpers.get_no_module_name(parent).split(".")[0]
                                not in GROUP_NODES
                            ):
                                tfdata["graphdict"][parent].remove(lb)
    return tfdata


def handle_cf_origins(tfdata: dict) -> dict:
    cf_data = [s for s in tfdata["meta_data"].keys() if "aws_cloudfront" in s]
    if cf_data:
        for cf_resource in cf_data:
            if "origin" in tfdata["meta_data"][cf_resource]:
                origin_source = tfdata["meta_data"][cf_resource]["origin"]
                if isinstance(origin_source, str) and (
                    origin_source.startswith("{") or origin_source.startswith("[")
                ):
                    origin_source = literal_eval(origin_source)
                if isinstance(origin_source, list):
                    origin_source = origin_source[0]
                if isinstance(origin_source, dict):
                    origin_domain = helpers.cleanup(
                        origin_source.get("domain_name")
                    ).strip()
                    if (
                        tfdata["meta_data"][cf_resource].get("viewer_certificate")
                        and "acm_certificate_arn"
                        in tfdata["meta_data"][cf_resource]["viewer_certificate"]
                    ):
                        tfdata["graphdict"][cf_resource].append(
                            "aws_acm_certificate.acm"
                        )
                    if origin_domain:
                        tfdata["meta_data"][cf_resource]["origin"] = (
                            handle_cloudfront_domains(
                                str(origin_source), origin_domain, tfdata["meta_data"]
                            )
                        )
    return tfdata


def aws_handle_cloudfront_pregraph(tfdata: dict):
    tfdata = handle_cloudfront_lbs(tfdata)
    tfdata = handle_cf_origins(tfdata)

    return tfdata


def _add_suffix(s):
    if s and s[-1].isalpha():
        return s + "~" + str(ord(s[-1].lower()) - ord("a") + 1)
    return s


def aws_handle_subnet_azs(tfdata: dict):
    subnet_resources = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_subnet")
        and k not in tfdata["hidden"]
    ]
    for subnet in subnet_resources:
        parents_list = helpers.list_of_parents(tfdata["graphdict"], subnet)
        for parent in parents_list:
            # Remove references to subnet and replace with AZ
            if subnet in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(subnet)
            az = "aws_az.availability_zone_" + str(
                tfdata["original_metadata"][subnet].get("availability_zone")
            )
            az = az.replace("-", "_")
            region = tfdata["original_metadata"][subnet].get("region")
            if region:
                az = az.replace("True", region)
            else:
                az = az.replace(".True", ".availability_zone")
            az = _add_suffix(az)
            if not az in tfdata["graphdict"].keys():
                tfdata["graphdict"][az] = list()
                tfdata["meta_data"][az] = {"count": ""}
                tfdata["meta_data"][az]["count"] = str(
                    tfdata["meta_data"][subnet].get("count")
                )
            if "aws_vpc" in parent:
                tfdata["graphdict"][az].append(subnet)
            if az not in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].append(az)
    return tfdata


# Add relationships between all EFS mount targets and the EFS file system service
def aws_handle_efs(tfdata: dict) -> dict:
    efs_systems = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_file_system"
    )
    efs_mount_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_mount_target"
    )
    for target in efs_mount_targets:
        for fs in efs_systems:
            if fs not in tfdata["graphdict"][target]:
                tfdata["graphdict"][target].append(fs)
            # Remove any references to the mount target from EFS resource
            for fs_connection in tfdata["graphdict"][fs]:
                if helpers.get_no_module_name(fs_connection).startswith(
                    "aws_efs_mount_target"
                ):
                    tfdata["graphdict"][fs].remove(fs_connection)
                else:
                    tfdata["graphdict"][fs_connection].append(fs)
                    tfdata["graphdict"][fs].remove(fs_connection)
    # Replace any references to the EFS service with mount target
    for node, connections in dict(tfdata["graphdict"]).items():
        if helpers.consolidated_node_check(node):
            for connection in connections:
                if helpers.get_no_module_name(connection).startswith(
                    "aws_efs_file_system"
                ):
                    target = efs_mount_targets[0].split("~")[0]
                    target = helpers.remove_brackets_and_numbers(target)
                    tfdata["graphdict"][node].remove(connection)
                    tfdata["graphdict"][node].append(target)
    return tfdata


def handle_indirect_sg_rules(tfdata: dict) -> dict:
    sglist = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_security_group."
    )
    for sg in sglist:
        for sg_connection in tfdata["graphdict"][sg]:
            if helpers.get_no_module_name(sg_connection).startswith(
                "aws_security_group_rule"
            ):
                matched_resource = helpers.find_resource_containing(
                    tfdata["graphdict"].keys(), sg_connection
                )
                if matched_resource and len(tfdata["graphdict"][matched_resource]) > 0:
                    tfdata["graphdict"][sg].remove(sg_connection)
                    tfdata["graphdict"][sg].append(
                        tfdata["graphdict"][matched_resource][0]
                    )
    return tfdata


def handle_sg_relationships(tfdata: dict) -> dict:
    all_sg_parents = helpers.list_of_parents(
        tfdata["graphdict"], "aws_security_group.*"
    )
    bound_nodes = [
        s
        for s in all_sg_parents
        if not helpers.get_no_module_name(s).startswith("aws_security_group")
    ]
    for target in bound_nodes:
        target_type = helpers.get_no_module_name(target).split(".")[0]
        # Look for any nodes related to security groups and reverse the relationship, making child as parent
        if not target_type in GROUP_NODES and target_type != "aws_security_group_rule":
            duplicate_sg_connections = False
            for connection in tfdata["graphdict"][target]:
                if (
                    helpers.get_no_module_name(connection).startswith(
                        "aws_security_group."
                    )
                    and connection in tfdata["graphdict"].keys()
                    and tfdata["graphdict"][connection]
                ):
                    newlist = list([target])
                    # Create numbered security group if connection has -[1..3] suffix
                    if "~" in target:
                        suffix = target.split("~")[1]
                        suffixed_name = connection + "~" + suffix
                        tfdata["graphdict"][suffixed_name] = newlist
                    else:
                        if len(tfdata["graphdict"][connection]) > 0:
                            tfdata["graphdict"][
                                connection + "_" + target.split(".")[-1]
                            ] = newlist
                            duplicate_sg_connections = True
                        else:
                            tfdata["graphdict"][connection] = newlist
                    newlist = list(tfdata["graphdict"][target])
                    newlist.remove(connection)
                    if duplicate_sg_connections:
                        for e in tfdata["graphdict"][target]:
                            if e == connection:
                                tfdata["graphdict"][target].remove(e)
                                tfdata["graphdict"][target].append(
                                    connection + "_" + target.split(".")[-1]
                                )
                    tfdata["graphdict"][target] = newlist
                elif (
                    helpers.get_no_module_name(connection).startswith(
                        "aws_security_group."
                    )
                    and connection in tfdata["graphdict"].keys()
                    and len(tfdata["graphdict"][connection]) == 0
                    and target not in tfdata["graphdict"][connection]
                ):
                    tfdata["graphdict"][target].remove(connection)
                    tfdata["graphdict"][connection].append(target)
        # Remove Security Group Rules from associations with the security group
        # This will ensure only nodes that are protected with a security group are drawn with the red boundary
        if target_type == "aws_security_group_rule":
            for connection in list(tfdata["graphdict"][target]):
                if (
                    connection in tfdata["graphdict"].keys()
                    and len(tfdata["graphdict"][connection]) == 0
                ):
                    del tfdata["graphdict"][connection]
                plist = helpers.list_of_parents(tfdata["graphdict"], connection)
                for p in plist:
                    tfdata["graphdict"][p].remove(connection)
        # Replace any references to nodes within the security group with the security group
        references = helpers.list_of_parents(tfdata["graphdict"], target)
        replacement_sg = [
            k
            for k in references
            if helpers.get_no_module_name(k).startswith("aws_security_group")
        ]
        if replacement_sg:
            replacement_sg = replacement_sg[0]
            for node in references:
                if (
                    target in tfdata["graphdict"][node]
                    and not helpers.get_no_module_name(node).startswith(
                        "aws_security_group"
                    )
                    and helpers.get_no_module_name(node).split(".")[0] in GROUP_NODES
                    and not helpers.get_no_module_name(node).startswith("aws_vpc")
                    and replacement_sg not in tfdata["graphdict"][node]
                ):
                    tfdata["graphdict"][node].remove(target)
                    tfdata["graphdict"][node].append(replacement_sg)
    return tfdata


def duplicate_sg_connections(tfdata: dict) -> dict:
    results = helpers.find_common_elements(tfdata["graphdict"], "aws_security_group.")
    for i in range(0, len(results)):
        sg2 = results[i][1]
        common = results[i][2]
        if common in tfdata["graphdict"][sg2]:
            tfdata["graphdict"][sg2].remove(common)
            tfdata["graphdict"][sg2].append(common + str(i))
    return tfdata


def aws_handle_sg(tfdata: dict) -> dict:
    # Handle indirect association to resources via SG rule
    tfdata = handle_indirect_sg_rules(tfdata)
    # Main handler for SG relationships
    tfdata = handle_sg_relationships(tfdata)
    # Handle subnets pointing to sg targets
    list_of_sgs = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_security_group."
    )
    for sg in list_of_sgs:
        for sg_connection in tfdata["graphdict"][sg]:
            parent_list = helpers.list_of_parents(tfdata["graphdict"], sg_connection)
            for parent in parent_list:
                if (
                    helpers.get_no_module_name(parent).startswith("aws_subnet")
                    and sg not in tfdata["graphdict"][parent]
                    and sg + "~1" not in parent_list
                ):
                    tfdata["graphdict"][parent].append(sg)
                    tfdata["graphdict"][parent].remove(sg_connection)
    # Delete SGs within VPCs
    for sg in list_of_sgs:
        parent_list = helpers.list_of_parents(tfdata["graphdict"], sg)
        for parent in parent_list:
            if helpers.get_no_module_name(parent).startswith("aws_vpc"):
                tfdata["graphdict"][parent].remove(sg)
    # Merge any security groups which share the same identical connection
    tfdata = duplicate_sg_connections(tfdata)
    # Remove orhpan security groups
    for sg in list_of_sgs:
        if len(tfdata["graphdict"][sg]) == 0:
            del tfdata["graphdict"][sg]
    return tfdata


def aws_handle_sharedgroup(tfdata: dict):
    graphcopy = dict(tfdata["graphdict"])
    for node in graphcopy:
        substring_match = [s for s in SHARED_SERVICES if s in node]
        if substring_match:
            if not tfdata["graphdict"].get("aws_group.shared_services"):
                tfdata["graphdict"]["aws_group.shared_services"] = []
                tfdata["meta_data"]["aws_group.shared_services"] = {}
            if node not in tfdata["graphdict"]["aws_group.shared_services"]:
                tfdata["graphdict"]["aws_group.shared_services"].append(node)
    if tfdata["graphdict"].get("aws_group.shared_services"):
        for service in list(tfdata["graphdict"]["aws_group.shared_services"]):
            if helpers.consolidated_node_check(service) and "cluster" not in service:
                tfdata["graphdict"]["aws_group.shared_services"] = list(
                    map(
                        lambda x: x.replace(
                            service, helpers.consolidated_node_check(service)
                        ),
                        tfdata["graphdict"]["aws_group.shared_services"],
                    )
                )
    return tfdata


# Check type of LB and create variant node. Replace all parent connections with new node
def aws_handle_lb(tfdata: dict):
    found_lbs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_lb")
    for lb in found_lbs:
        lb_type = helpers.check_variant(lb, tfdata["meta_data"][lb])
        renamed_node = lb_type + "." + "elb"
        for connection in list(tfdata["graphdict"][lb]):
            if not tfdata["graphdict"].get(renamed_node):
                tfdata["graphdict"][renamed_node] = list()
            tfdata["graphdict"][renamed_node].append(connection)
            if (
                tfdata["meta_data"].get(connection)
                and tfdata["meta_data"][connection].get("count")
                or tfdata["meta_data"][connection].get("desired_count")
            ) and connection.split(".")[0] not in SHARED_SERVICES:
                # Sets LB count to the max of the count of any dependencies
                tfdata["meta_data"][renamed_node] = dict(
                    tfdata["meta_data"]["aws_lb.elb"]
                )
                if (
                    tfdata["meta_data"][connection]["count"]
                    > tfdata["meta_data"][renamed_node]["count"]
                ):
                    tfdata["meta_data"][renamed_node]["count"] = int(
                        tfdata["meta_data"][connection]["count"]
                    )

            tfdata["graphdict"][lb].remove(connection)
            parents = helpers.list_of_parents(tfdata["graphdict"], lb)
            for p in parents:
                p_type = p.split(".")[0]
                if (
                    p_type in GROUP_NODES
                    and p_type not in SHARED_SERVICES
                    and p_type != "aws_vpc"
                ):
                    tfdata["graphdict"][p].append(renamed_node)
                    tfdata["graphdict"][p].remove(lb)
        tfdata["graphdict"][lb].append(renamed_node)
    return tfdata


def aws_handle_dbsubnet(tfdata: dict):
    db_subnet_list = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_db_subnet_group"
    )
    for dbsubnet in db_subnet_list:
        db_grouping = helpers.list_of_parents(tfdata["graphdict"], dbsubnet)
        if db_grouping:
            for subnet in db_grouping:
                if helpers.get_no_module_name(subnet).startswith("aws_subnet"):
                    tfdata["graphdict"][subnet].remove(dbsubnet)
                    az = helpers.list_of_parents(tfdata["graphdict"], subnet)[0]
                    vpc = helpers.list_of_parents(tfdata["graphdict"], az)[0]
                    if dbsubnet not in tfdata["graphdict"][vpc]:
                        tfdata["graphdict"][vpc].append(dbsubnet)
            for rds in tfdata["graphdict"][dbsubnet]:
                rds_references = helpers.list_of_parents(tfdata["graphdict"], rds)
                for check_sg in rds_references:
                    if helpers.get_no_module_name(check_sg).startswith(
                        "aws_security_group"
                    ):
                        tfdata["graphdict"][vpc].remove(dbsubnet)
                        tfdata["graphdict"][vpc].append(check_sg)
                        break
    return tfdata


def aws_handle_vpcendpoints(tfdata: dict):
    vpc_endpoints = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_vpc_endpoint"
    )
    vpc = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_vpc.")[0]
    for vpc_endpoint in vpc_endpoints:
        tfdata["graphdict"][vpc].append(vpc_endpoint)
        del tfdata["graphdict"][vpc_endpoint]
    return tfdata


def aws_handle_ecs(tfdata: dict):
    # eks_nodes = helpers.list_of_parents(tfdata["graphdict"], "aws_eks_cluster")
    ecs_nodes = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_ecs_service"
    )
    # for ecs in ecs_nodes:
    #     tfdata["meta_data"][ecs]["count"] = 3
    # ecs_nodes = helpers.list_of_parents(tfdata["graphdict"], "aws_ek_cluster")
    # for eks in eks_nodes:
    #     del tfdata["graphdict"][eks]
    return tfdata


def random_string_handler(tfdata: dict):
    randoms = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "random_string.")
    for r in randoms:
        del tfdata["graphdict"][r]
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
