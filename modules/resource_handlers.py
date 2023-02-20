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
    return tfdata


def handle_cloudfront_domains(origin_string: str, domain: str, mdata: dict) -> str:
    for key, value in mdata.items():
        for k, v in value.items():
            if domain in str(v) and not domain.startswith("aws_"):
                o = origin_string.replace(domain, key)
                return origin_string.replace(domain, key)
    return origin_string


def aws_handle_cloudfront(tfdata: dict):
    cf_data = [s for s in tfdata["meta_data"].keys() if "aws_cloudfront" in s]
    if cf_data:
        for cf_resource in cf_data:
            if "origin" in tfdata["meta_data"][cf_resource]:
                origin_source = tfdata["meta_data"][cf_resource]["origin"]
                if isinstance(origin_source, str) and origin_source.startswith("{"):
                    origin_source = helpers.literal_eval(origin_source)
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
                    if not parent_mount_target in tfdata["graphdict"][node] :
                        tfdata["graphdict"][node].remove(connection)
                        tfdata["graphdict"][node].append(parent_mount_target)
    return tfdata


def aws_handle_sg(tfdata:dict) :
    bound_nodes = helpers.list_of_parents(tfdata["graphdict"], "aws_security_group")
    for target in bound_nodes :
        target_type =  target.split('.')[0] 
        # Look for any nodes with relationships to security groups and then reverse the relationship
        # effectively putting the node into a cluster representing the security group
        if not target_type in GROUP_NODES :
            for connection in tfdata['graphdict'][target] :
                if connection.startswith('aws_security_group') :
                    newlist = list()
                    newlist.append(target)
                    tfdata['graphdict'][connection] = newlist
                    newlist = list(tfdata['graphdict'][target])
                    newlist.remove(connection)
                    tfdata['graphdict'][target] = newlist
        # Remove any security group relationships if they are associated with the VPC already
        # This will ensure only nodes that are protected with a security group are drawn with the red boundary

    return tfdata

def aws_handle_sharedgroup(tfdata: dict) :
    graphcopy = dict(tfdata['graphdict'])
    for node in graphcopy :
        substring_match = [s for s in SHARED_SERVICES if s in node]
        if substring_match :
            if not tfdata['graphdict'].get('aws_group.shared_services') :
                tfdata['graphdict']['aws_group.shared_services'] = []
                tfdata['meta_data']['aws_group.shared_services'] = {}
            tfdata['graphdict']['aws_group.shared_services'].append(node)
    for service in list(tfdata['graphdict']['aws_group.shared_services']) :
        if helpers.consolidated_node_check(service) and 'cluster' not in service :
            tfdata['graphdict']['aws_group.shared_services'] = list(map(lambda x: x.replace(service, helpers.consolidated_node_check(service)), tfdata['graphdict']['aws_group.shared_services']))
    return tfdata


def aws_handle_lb(tfdata:dict):
    lb_type = helpers.check_variant('aws_lb.elb', tfdata['meta_data']['aws_lb.elb']) 
    renamed_node = lb_type + '.' + 'elb'
    for connection in list(tfdata['graphdict']['aws_lb.elb']) :
        if connection.startswith('aws_security_group') :
            tfdata['graphdict'][connection] = ['aws_lb.elb']
        else :
            if not tfdata['graphdict'].get(renamed_node) :
                tfdata['graphdict'][renamed_node] = list()
            tfdata['graphdict'][renamed_node].append(connection)
            tfdata['meta_data'][renamed_node] = dict(tfdata['meta_data']['aws_lb.elb'])
            if tfdata['meta_data'][connection].get('count')  :
                if tfdata['meta_data'][connection].get('count') > 1 :
                    tfdata['meta_data'][renamed_node]['count'] = int(tfdata['meta_data'][connection]['count'])
            tfdata['graphdict']['aws_lb.elb'].remove(connection)
    tfdata['graphdict']['aws_lb.elb'].append(renamed_node)
    return tfdata