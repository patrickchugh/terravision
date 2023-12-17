from debugpy import connect
import modules.cloud_config as cloud_config
import modules.helpers as helpers
from ast import literal_eval

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
        for connection in tfdata["graphdict"][asg]:
            asg_target_parents = helpers.list_of_parents(
                tfdata["graphdict"], connection
            )
            subnets_to_change = [
                k for k in asg_target_parents if k.startswith("aws_subnet")
            ]
            for subnet in subnets_to_change:
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
                and not key.startswith("aws_cloudfront")
                and not key.startswith("aws_route53")
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
                            if parent.split(".")[0] not in GROUP_NODES:
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
                        tfdata["meta_data"][cf_resource][
                            "origin"
                        ] = handle_cloudfront_domains(
                            str(origin_source), origin_domain, tfdata["meta_data"]
                        )
    return tfdata


def aws_handle_cloudfront_pregraph(tfdata: dict):
    tfdata = handle_cloudfront_lbs(tfdata)
    tfdata = handle_cf_origins(tfdata)

    return tfdata


def aws_handle_subnet_azs(tfdata: dict):
    subnet_resources = [
        k
        for k in tfdata["graphdict"]
        if k.startswith("aws_subnet") and k not in tfdata["hidden"]
    ]
    for subnet in subnet_resources:
        parents_list = helpers.list_of_parents(tfdata["graphdict"], subnet)
        for parent in parents_list:
            # Remove references to subnet and replace with AZ
            if subnet in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(subnet)
            az = "aws_az." + tfdata["original_metadata"][subnet].get(
                "availability_zone"
            )
            az = az.replace("-", "~")
            if not az in tfdata["graphdict"].keys():
                tfdata["graphdict"][az] = list()
                tfdata["meta_data"][az] = {"count": ""}
                tfdata["meta_data"][az]["count"] = tfdata["meta_data"][subnet]["count"]
            tfdata["graphdict"][az].append(subnet)
            if az not in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].append(az)
    return tfdata


def aws_handle_efs(tfdata: dict):
    efs_systems = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_file_system"
    )
    efs_mount_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_mount_target"
    )
    for efs in efs_systems:
        for connection in tfdata["graphdict"][efs]:
            if connection.startswith("aws_efs_mount_target"):
                target = connection
        for connection in list(tfdata["graphdict"][efs]):
            if (
                not connection.startswith("aws_efs_mount_target")
                and "~" not in connection
            ):
                tfdata["graphdict"][connection].append(target)
            elif "~" in connection:
                suffix = connection.split("~")[1]
                suffixed_name = "aws_efs_mount_target~" + suffix
                if suffixed_name in efs_mount_targets:
                    tfdata["graphdict"][connection].append(suffixed_name)
            tfdata["graphdict"][efs].remove(connection)
    return tfdata


def aws_handle_sg(tfdata: dict):
    all_sg_parents = helpers.list_of_parents(tfdata["graphdict"], "aws_security_group.")
    bound_nodes = [s for s in all_sg_parents if not s.startswith("aws_security_group")]
    for target in bound_nodes:
        target_type = target.split(".")[0]
        # Look for any nodes with relationships to security groups and then reverse the relationship
        # putting the parent node into a cluster named after the security group
        if not target_type in GROUP_NODES and target_type != "aws_security_group_rule":
            for connection in tfdata["graphdict"][target]:
                if (
                    connection.startswith("aws_security_group.")
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
                        tfdata["graphdict"][connection] = newlist
                    newlist = list(tfdata["graphdict"][target])
                    newlist.remove(connection)
                    tfdata["graphdict"][target] = newlist
                elif (
                    connection.startswith("aws_security_group.")
                    and connection in tfdata["graphdict"].keys()
                    and len(tfdata["graphdict"][connection]) == 0
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
        replacement_sg = [k for k in references if k.startswith("aws_security_group")]
        if replacement_sg:
            replacement_sg = replacement_sg[0]
            for node in references:
                if (
                    target in tfdata["graphdict"][node]
                    and not node.startswith("aws_security_group")
                    and node.split(".")[0] in GROUP_NODES
                    and not node.startswith("aws_vpc")
                ):
                    tfdata["graphdict"][node].remove(target)
                    tfdata["graphdict"][node].append(replacement_sg)
    # TODO: Merge any security groups which share the same identical connection
    # Handle subnets pointing to sg targets
    list_of_sgs = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_security_group"
    )
    for sg in list_of_sgs:
        for sg_connection in tfdata["graphdict"][sg]:
            parent_list = helpers.list_of_parents(tfdata["graphdict"], sg_connection)
            for parent in parent_list:
                if parent.startswith("aws_subnet"):
                    tfdata["graphdict"][parent].append(sg)
                    tfdata["graphdict"][parent].remove(sg_connection)
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
                tfdata["meta_data"][connection].get("count")
                and connection.split(".")[0] not in SHARED_SERVICES
            ):
                tfdata["meta_data"][renamed_node] = dict(
                    tfdata["meta_data"]["aws_lb.elb"]
                )
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
                if subnet.startswith("aws_subnet"):
                    tfdata["graphdict"][subnet].remove(dbsubnet)
                    az = helpers.list_of_parents(tfdata["graphdict"], subnet)[0]
                    vpc = helpers.list_of_parents(tfdata["graphdict"], az)[0]
                    if dbsubnet not in tfdata["graphdict"][vpc]:
                        tfdata["graphdict"][vpc].append(dbsubnet)
            for rds in tfdata["graphdict"][dbsubnet]:
                rds_references = helpers.list_of_parents(tfdata["graphdict"], rds)
                for check_sg in rds_references:
                    if check_sg.startswith("aws_security_group"):
                        tfdata["graphdict"][vpc].remove(dbsubnet)
                        tfdata["graphdict"][vpc].append(check_sg)
                        break
    return tfdata
    # db_subnet_list = helpers.find_resource_references(
    #     tfdata["graphdict"], "aws_db_subnet_group"
    # )
    # for subnet_reference in db_subnet_list:
    #     if subnet_reference.startswith("aws_rds"):
    #         tfdata["graphdict"][subnet_reference].append(subnet_reference)
    #         for check_subnet in tfdata["graphdict"][subnet_reference]:
    #             if check_subnet.startswith("aws_db_subnet"):
    #                 tfdata["graphdict"][subnet_reference].remove(check_subnet)
    #     else:
    #         for check_subnet in tfdata["graphdict"][subnet_reference]:
    #             if check_subnet.startswith("aws_db_subnet"):
    #                 tfdata["graphdict"][subnet_reference].remove(check_subnet)
    #                 find_rds = helpers.list_of_dictkeys_containing(
    #                     tfdata["graphdict"], "aws_rds_cluster"
    #                 )
    #                 tfdata["graphdict"][subnet_reference].append(find_rds[0])
    # db_subnet_nodes = helpers.list_of_dictkeys_containing(
    #     tfdata["graphdict"], "aws_db_subnet_group"
    # )
    # for dbs in db_subnet_nodes:
    #     del tfdata["graphdict"][dbs]


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
