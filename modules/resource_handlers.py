from ast import literal_eval
from contextlib import suppress

from modules.tf_function_handlers import tf_function_handlers
from sys import exit

import modules.helpers as helpers
import modules.annotations as annotations
import modules.cloud_config as cloud_config

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
            r for r in tfdata["graphdict"] if r.startswith("aws_appautoscaling_target")
        ]
        for asg in asg_resources:
            new_list = list()
            for check_service in scaler_links:
                possible_subnets = [
                    k for k in tfdata["graphdict"] if k.startswith("aws_subnet")
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
        for connection in tfdata["graphdict"][asg] :
            asg_target_parents = helpers.list_of_parents(tfdata["graphdict"],connection)
            subnets_to_change = [k for k in asg_target_parents if k.startswith("aws_subnet")]
            for subnet in subnets_to_change :
                tfdata["graphdict"][subnet].append(asg)
                tfdata["graphdict"][subnet].remove(connection)
            pass
    return tfdata

# Create link to CF if its domain name is referred to in other metadata
def handle_cloudfront_domains(origin_string: str, domain: str, mdata: dict) -> str:
    for key, value in mdata.items():
        for k, v in value.items():
            if domain in str(v) and not domain.startswith("aws_") and not key.startswith("aws_cloudfront") and not key.startswith("aws_route53"):
                o = origin_string.replace(domain, key)
                return origin_string.replace(domain, key)
    return origin_string


def aws_handle_cloudfront_pregraph(tfdata: dict):
    cf_data = [s for s in tfdata["meta_data"].keys() if "aws_cloudfront" in s]
    if cf_data:
        for cf_resource in cf_data:
            if "origin" in tfdata["meta_data"][cf_resource]:
                origin_source = tfdata["meta_data"][cf_resource]["origin"]
                if isinstance(origin_source, str) and (origin_source.startswith("{") or origin_source.startswith("[")):
                    origin_source = helpers.literal_eval(origin_source)
                if isinstance(origin_source, list)  :
                    origin_source = origin_source[0]    
                if isinstance(origin_source,dict):     
                    origin_domain = helpers.cleanup(
                        origin_source.get("domain_name")
                    ).strip()
                    if origin_domain:
                        tfdata["meta_data"][cf_resource][
                            "origin"
                        ] = handle_cloudfront_domains(
                            str(origin_source), origin_domain, tfdata["meta_data"]
                        )
    return tfdata


def aws_handle_subnet_azs(tfdata: dict):
    subnet_resources = [
        k
        for k, v in tfdata["meta_data"].items()
        if k.startswith("aws_subnet") and k not in tfdata["hidden"]
    ]
    # subnet_resources = [k for k,v in tfdata['meta_data'].items() if k not in tfdata['hidden'] and 'availability_zone' in v.keys() ]
    for subnet in subnet_resources:
        parents_list = helpers.list_of_parents(tfdata["graphdict"], subnet)
        for parent in parents_list:
            if subnet in tfdata["graphdict"][parent] :
                tfdata["graphdict"][parent].remove(subnet)
            if not tfdata["graphdict"].get("aws_az.az"):
                tfdata["graphdict"]["aws_az.az"] = [subnet]
                if tfdata["meta_data"][subnet].get("count"):
                    tfdata["meta_data"]["aws_az.az"] = {"count": ""}
                    tfdata["meta_data"]["aws_az.az"]["count"] = tfdata["meta_data"][
                        subnet
                    ]["count"]
            else:
                tfdata["graphdict"]["aws_az.az"].append(subnet)
            tfdata["graphdict"][parent].append("aws_az.az")
    return tfdata


def aws_handle_efs(tfdata: dict):
    parents = helpers.list_of_parents(tfdata["graphdict"], "aws_efs_file_system")
    do_replacements = False
    for parent_node in parents:
        if parent_node.startswith("aws_efs_mount_target"):
            do_replacements = True
            parent_mount_target = parent_node
    if do_replacements:
        for node in tfdata["graphdict"]:
            for connection in tfdata["graphdict"][node]:
                if connection.startswith("aws_efs_file") and not node.startswith(
                    "aws_efs"
                ):
                    # we have a mount target pointing to EFS file system so replace all references to efs_file_system directly
                    # to the mount target instead
                    if not parent_mount_target in tfdata["graphdict"][node]:
                        tfdata["graphdict"][node].remove(connection)
                        tfdata["graphdict"][node].append(parent_mount_target)
    return tfdata


def aws_handle_sg(tfdata: dict):
    bound_nodes = helpers.list_of_parents(tfdata["graphdict"], "aws_security_group")
    for target in bound_nodes:
        target_type = target.split(".")[0]
        # Look for any nodes with relationships to security groups and then reverse the relationship
        # putting the parent node into a cluster named after the security group
        if not target_type in GROUP_NODES:
            for connection in tfdata["graphdict"][target]:
                if connection.startswith("aws_security_group"):
                    newlist = list()
                    newlist.append(target)
                    tfdata["graphdict"][connection] = newlist
                    newlist = list(tfdata["graphdict"][target])
                    newlist.remove(connection)
                    tfdata["graphdict"][target] = newlist
        # Remove any security group relationships if they are associated with the VPC already
        # This will ensure only nodes that are protected with a security group are drawn with the red boundary
        if target_type == "aws_vpc":
            for connection in list(tfdata["graphdict"][target]):
                if connection.startswith("aws_security_group"):
                    tfdata["graphdict"][target].remove(connection)
        # Replace any references to nodes within the security group with the security group
        references = helpers.list_of_parents(tfdata["graphdict"], target)
        replacement_sg = [k for k in references if k.startswith("aws_security_group")]
        if replacement_sg:
            replacement_sg = replacement_sg[0]
        for node in references:
            if (
                target in tfdata["graphdict"][node]
                and not node.startswith("aws_security_group")
                and node.split(".")[0] in GROUP_NODES and not node.startswith('aws_vpc')
            ):
                tfdata["graphdict"][node].remove(target)
                tfdata["graphdict"][node].append(replacement_sg)
    # TODO: Merge any security groups which share the same identical connection
    list_of_sgs = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_security_group"
    )
    pass

    return tfdata


def aws_handle_sharedgroup(tfdata: dict):
    graphcopy = dict(tfdata["graphdict"])
    for node in graphcopy:
        substring_match = [s for s in SHARED_SERVICES if s in node]
        if substring_match:
            if not tfdata["graphdict"].get("aws_group.shared_services"):
                tfdata["graphdict"]["aws_group.shared_services"] = []
                tfdata["meta_data"]["aws_group.shared_services"] = {}
            tfdata["graphdict"]["aws_group.shared_services"].append(node)
    if tfdata["graphdict"].get("aws_group.shared_services") :
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


def aws_handle_lb(tfdata: dict):
    found_lbs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_lb")
    for lb in found_lbs:
        lb_type = helpers.check_variant(lb, tfdata["meta_data"][lb])
        renamed_node = lb_type + "." + "elb"
        for connection in list(tfdata["graphdict"][lb]):
            if not tfdata["graphdict"].get(renamed_node):
                tfdata["graphdict"][renamed_node] = list()
            tfdata["graphdict"][renamed_node].append(connection)
            tfdata["meta_data"][renamed_node] = dict(
                tfdata["meta_data"]["aws_lb.elb"]
            )
            if tfdata["meta_data"][connection].get("count"):
                if tfdata["meta_data"][connection].get("count") > 1:
                    tfdata["meta_data"][renamed_node]["count"] = int(
                        tfdata["meta_data"][connection]["count"]
                    )
            tfdata["graphdict"][lb].remove(connection)
            parents = helpers.list_of_parents(tfdata['graphdict'],lb)
            for p in parents :
                p_type = p.split('.')[0] 
                if p_type in GROUP_NODES and p_type not in SHARED_SERVICES and p_type != 'aws_vpc':
                    tfdata["graphdict"][p].append(renamed_node)
                    tfdata["graphdict"][p].remove(lb)
    tfdata["graphdict"][lb].append(renamed_node)
    
    return tfdata


def aws_handle_dbsubnet(tfdata: dict):
    db_subnet_list = helpers.find_resource_references(
        tfdata["graphdict"], "aws_db_subnet_group"
    )
    for subnet_reference in db_subnet_list:
        if subnet_reference.startswith("aws_rds"):
            tfdata["graphdict"][subnet_reference].append(subnet_reference)
            for check_subnet in tfdata["graphdict"][subnet_reference]:
                if check_subnet.startswith("aws_db_subnet"):
                    tfdata["graphdict"][subnet_reference].remove(check_subnet)
        else:
            for check_subnet in tfdata["graphdict"][subnet_reference]:
                if check_subnet.startswith("aws_db_subnet"):
                    tfdata["graphdict"][subnet_reference].remove(check_subnet)
                    find_rds = helpers.list_of_dictkeys_containing(
                        tfdata["graphdict"], "aws_rds_cluster"
                    )
                    tfdata["graphdict"][subnet_reference].append(find_rds[0])
    db_subnet_nodes = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_db_subnet_group"
    )
    for dbs in db_subnet_nodes:
        del tfdata["graphdict"][dbs]
    return tfdata
