"""AWS resource-specific handlers for Terraform graph processing.

Handles special cases for AWS resources including security groups, load balancers,
EFS, CloudFront, autoscaling, subnets, and other AWS-specific relationships.
"""
from typing import Dict, List, Any
import modules.cloud_config as cloud_config
import modules.helpers as helpers
from ast import literal_eval
import re
import copy

REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AWS_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.AWS_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.AWS_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.AWS_SHARED_SERVICES
DISCONNECT_SERVICES = cloud_config.AWS_DISCONNECT_LIST


def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle special resource cases and disconnections.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with special cases handled
    """
    # Handle cases where resources have transitive link via sqs policy
    tfdata["graphdict"] = link_sqs_queue_policy(tfdata["graphdict"])
    # Remove connections to services specified in disconnect services
    for r in tfdata["graphdict"]:
        for d in DISCONNECT_SERVICES:
            if d in r:
                tfdata["graphdict"][r] = []
    return tfdata


def aws_handle_autoscaling(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle AWS autoscaling group relationships and counts.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with autoscaling relationships configured
    """
    try:
        # Find autoscaling target connections
        scaler_links = next(
            v
            for k, v in tfdata["graphdict"].items()
            if "aws_appautoscaling_target" in k
        )
        # Get all autoscaling resources
        asg_resources = [
            r
            for r in tfdata["graphdict"]
            if helpers.get_no_module_name(r).startswith("aws_appautoscaling_target")
        ]
        # Process each autoscaling group
        for asg in asg_resources:
            new_list = list()
            for check_service in scaler_links:
                # Find all subnets in the graph
                possible_subnets = [
                    k
                    for k in tfdata["graphdict"]
                    if helpers.get_no_module_name(k).startswith("aws_subnet")
                ]
                # Check if service is in subnet (part of ASG)
                for sub in possible_subnets:
                    if check_service in tfdata["graphdict"][sub]:
                        new_list.append(sub)
                # Copy subnet count to ASG and service
                for subnet in new_list:
                    if not tfdata["meta_data"][asg].get("count"):
                        count_value = tfdata["meta_data"][subnet]["count"]
                        tfdata["meta_data"][asg]["count"] = (
                            int(count_value)
                            if isinstance(count_value, (int, str))
                            else count_value
                        )
                        tfdata["meta_data"][check_service]["count"] = (
                            int(count_value)
                            if isinstance(count_value, (int, str))
                            else count_value
                        )
    except:
        pass
    # Replace subnet references to ASG targets with ASG itself
    for asg in asg_resources:
        for connection in tfdata["graphdict"][asg]:
            asg_target_parents = helpers.list_of_parents(
                tfdata["graphdict"], connection
            )
            # Find subnets that reference this ASG target
            subnets_to_change = [
                k
                for k in asg_target_parents
                if helpers.get_no_module_name(k).startswith("aws_subnet")
            ]
            # Update subnet connections
            for subnet in subnets_to_change:
                if asg not in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].append(asg)
                tfdata["graphdict"][subnet].remove(connection)
    return tfdata


def handle_cloudfront_domains(origin_string: str, domain: str, mdata: Dict[str, Any]) -> str:
    """Link CloudFront to resources by matching domain names.
    
    Args:
        origin_string: Original origin configuration string
        domain: Domain name to search for
        mdata: Resource metadata dictionary
        
    Returns:
        Updated origin string with resource references
    """
    # Search metadata for domain references
    for key, value in mdata.items():
        for k, v in value.items():
            # Check if domain is referenced in non-CloudFront/Route53 resources
            if (
                domain in str(v)
                and not domain.startswith("aws_")
                and not helpers.get_no_module_name(key).startswith("aws_cloudfront")
                and not helpers.get_no_module_name(key).startswith("aws_route53")
            ):
                # Replace domain with resource reference
                return origin_string.replace(domain, key)
    return origin_string


def handle_cloudfront_lbs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Connect CloudFront distributions to load balancers.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with CloudFront-LB connections
    """
    # Find CloudFront distributions and load balancers
    cf_distros = [s for s in tfdata["graphdict"].keys() if "aws_cloudfront" in s]
    lbs = [s for s in tfdata["graphdict"].keys() if "aws_lb." in s]
    # Connect CloudFront to LBs when node connects to both
    for node, connections in dict(tfdata["graphdict"]).items():
        for cf in cf_distros:
            if cf in connections:
                for lb in lbs:
                    # If node connects to LB, link CF directly to LB
                    if node in tfdata["graphdict"][lb]:
                        lb_parents = helpers.list_of_parents(tfdata["graphdict"], lb)
                        tfdata["graphdict"][cf].append(lb)
                        tfdata["graphdict"][node].remove(cf)
                        # Remove LB from non-group parents
                        for parent in lb_parents:
                            if (
                                helpers.get_no_module_name(parent).split(".")[0]
                                not in GROUP_NODES
                            ):
                                tfdata["graphdict"][parent].remove(lb)
    return tfdata


def handle_cf_origins(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process CloudFront origin configurations and ACM certificates.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with CloudFront origins configured
    """
    # Find all CloudFront resources
    cf_data = [s for s in tfdata["meta_data"].keys() if "aws_cloudfront" in s]
    if cf_data:
        for cf_resource in cf_data:
            # Process origin configuration
            if "origin" in tfdata["meta_data"][cf_resource]:
                origin_source = tfdata["meta_data"][cf_resource]["origin"]
                # Parse string representation of dict/list
                if isinstance(origin_source, str) and (
                    origin_source.startswith("{") or origin_source.startswith("[")
                ):
                    origin_source = literal_eval(origin_source)
                # Extract first origin if list
                if isinstance(origin_source, list):
                    origin_source = origin_source[0]
                # Process origin dict
                if isinstance(origin_source, dict):
                    origin_domain = helpers.cleanup(
                        origin_source.get("domain_name")
                    ).strip()
                    # Link to ACM certificate if present
                    if (
                        tfdata["meta_data"][cf_resource].get("viewer_certificate")
                        and "acm_certificate_arn"
                        in tfdata["meta_data"][cf_resource]["viewer_certificate"]
                    ):
                        tfdata["graphdict"][cf_resource].append(
                            "aws_acm_certificate.acm"
                        )
                    # Link origin domain to resources
                    if origin_domain:
                        tfdata["meta_data"][cf_resource]["origin"] = (
                            handle_cloudfront_domains(
                                str(origin_source), origin_domain, tfdata["meta_data"]
                            )
                        )
    return tfdata


def aws_handle_cloudfront_pregraph(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-process CloudFront resources before graph generation.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with CloudFront pre-processing complete
    """
    tfdata = handle_cloudfront_lbs(tfdata)
    tfdata = handle_cf_origins(tfdata)

    return tfdata


def _add_suffix(s: str) -> str:
    """Add numeric suffix based on last character.
    
    Args:
        s: String to add suffix to
        
    Returns:
        String with numeric suffix if last char is alphabetic
    """
    if s and s[-1].isalpha():
        return s + "~" + str(ord(s[-1].lower()) - ord("a") + 1)
    return s


def aws_handle_subnet_azs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Create availability zone nodes and link to subnets.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with AZ nodes created
    """
    # Find all subnet resources (excluding hidden)
    subnet_resources = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_subnet")
        and k not in tfdata["hidden"]
    ]
    # Process each subnet to create AZ nodes
    for subnet in subnet_resources:
        parents_list = helpers.list_of_parents(tfdata["graphdict"], subnet)
        for parent in parents_list:
            # Remove direct subnet reference from parent
            if subnet in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(subnet)
            # Build AZ node name from subnet metadata
            az = "aws_az.availability_zone_" + str(
                tfdata["original_metadata"][subnet].get("availability_zone")
            )
            az = az.replace("-", "_")
            region = tfdata["original_metadata"][subnet].get("region")
            # Replace placeholder with actual region
            if region:
                az = az.replace("True", region)
            else:
                az = az.replace(".True", ".availability_zone")
            az = _add_suffix(az)
            # Create AZ node if it doesn't exist
            if az not in tfdata["graphdict"].keys():
                tfdata["graphdict"][az] = list()
                tfdata["meta_data"][az] = {"count": ""}
                tfdata["meta_data"][az]["count"] = str(
                    tfdata["meta_data"][subnet].get("count")
                )
            # Link AZ to subnet if parent is VPC
            if "aws_vpc" in parent:
                tfdata["graphdict"][az].append(subnet)
            # Link parent to AZ
            if az not in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].append(az)
    return tfdata


def aws_handle_efs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle EFS mount target and file system relationships.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with EFS relationships configured
    """
    # Find all EFS file systems and mount targets
    efs_systems = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_file_system"
    )
    efs_mount_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_mount_target"
    )
    # Link mount targets to file systems
    for target in efs_mount_targets:
        for fs in efs_systems:
            if fs not in tfdata["graphdict"][target]:
                tfdata["graphdict"][target].append(fs)
            # Clean up file system connections
            for fs_connection in tfdata["graphdict"][fs]:
                if helpers.get_no_module_name(fs_connection).startswith(
                    "aws_efs_mount_target"
                ):
                    # Remove mount target from file system
                    tfdata["graphdict"][fs].remove(fs_connection)
                else:
                    # Move other connections to file system
                    tfdata["graphdict"][fs_connection].append(fs)
                    tfdata["graphdict"][fs].remove(fs_connection)
    # Replace EFS file system references with mount target
    for node, connections in dict(tfdata["graphdict"]).items():
        if helpers.consolidated_node_check(node):
            for connection in connections:
                if helpers.get_no_module_name(connection).startswith(
                    "aws_efs_file_system"
                ):
                    # Use first mount target as replacement
                    target = efs_mount_targets[0].split("~")[0]
                    target = helpers.remove_brackets_and_numbers(target)
                    tfdata["graphdict"][node].remove(connection)
                    tfdata["graphdict"][node].append(target)
    return tfdata


def handle_indirect_sg_rules(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle indirect security group associations via SG rules.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with indirect SG rules resolved
    """
    # Find all security groups
    sglist = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_security_group."
    )
    # Process each security group
    for sg in sglist:
        for sg_connection in tfdata["graphdict"][sg]:
            # Check if connection is a security group rule
            if helpers.get_no_module_name(sg_connection).startswith(
                "aws_security_group_rule"
            ):
                # Find the actual resource the rule connects to
                matched_resource = helpers.find_resource_containing(
                    tfdata["graphdict"].keys(), sg_connection
                )
                # Replace rule with actual resource connection
                if matched_resource and len(tfdata["graphdict"][matched_resource]) > 0:
                    tfdata["graphdict"][sg].remove(sg_connection)
                    tfdata["graphdict"][sg].append(
                        tfdata["graphdict"][matched_resource][0]
                    )
    return tfdata


def handle_sg_relationships(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process security group relationships and reverse connections.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with SG relationships configured
    """
    # Find all resources that reference security groups
    all_sg_parents = helpers.list_of_parents(
        tfdata["graphdict"], "aws_security_group.*"
    )
    # Filter to non-SG resources
    bound_nodes = [
        s
        for s in all_sg_parents
        if not helpers.get_no_module_name(s).startswith("aws_security_group")
    ]
    # Process each resource bound to a security group
    for target in bound_nodes:
        target_type = helpers.get_no_module_name(target).split(".")[0]
        # Reverse SG relationships for non-group nodes
        if target_type not in GROUP_NODES and target_type != "aws_security_group_rule":
            sg_to_purge = list()
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
                            unique_name = connection + "_" + target.split(".")[-1]
                            tfdata["graphdict"][unique_name] = newlist
                            tfdata["graphdict"][connection]
                            tfdata["meta_data"][unique_name] = copy.deepcopy(
                                tfdata["meta_data"][connection]
                            )
                            sg_to_purge.append(connection)
                        else:
                            tfdata["graphdict"][connection] = newlist
                    newlist = list(tfdata["graphdict"][target])
                    if connection in newlist:
                        newlist.remove(connection)
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
        for purge in sg_to_purge:
            if purge in references:
                references.remove(purge)
        replacement_sgs = [
            k
            for k in references
            if helpers.get_no_module_name(k).startswith("aws_security_group")
        ]
        if replacement_sgs:
            for replaced_group in replacement_sgs:
                for node in references:
                    if (
                        target in tfdata["graphdict"][node]
                        and not helpers.get_no_module_name(node).startswith(
                            "aws_security_group"
                        )
                        and helpers.get_no_module_name(node).split(".")[0]
                        in GROUP_NODES
                        and not helpers.get_no_module_name(node).startswith("aws_vpc")
                        and replaced_group not in tfdata["graphdict"][node]
                    ):
                        tfdata["graphdict"][node].remove(target)
                        tfdata["graphdict"][node].append(replaced_group)
    return tfdata


def duplicate_sg_connections(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle duplicate security group connections.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with duplicate SG connections resolved
    """
    results = helpers.find_common_elements(tfdata["graphdict"], "aws_security_group.")
    for i in range(0, len(results)):
        sg2 = results[i][1]
        common = results[i][2]
        if common in tfdata["graphdict"][sg2]:
            tfdata["graphdict"][sg2].remove(common)
            tfdata["graphdict"][sg2].append(common + str(i))
    return tfdata


def aws_handle_sg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Main handler for AWS security group processing.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with all SG relationships configured
    """
    # Handle indirect association to resources via SG rule
    tfdata = handle_indirect_sg_rules(tfdata)
    # Main handler for SG relationships
    tfdata = handle_sg_relationships(tfdata)
    # Link subnets to security groups
    list_of_sgs = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_security_group."
    )
    for sg in list_of_sgs:
        for sg_connection in tfdata["graphdict"][sg]:
            parent_list = helpers.list_of_parents(tfdata["graphdict"], sg_connection)
            # Add SG to parent subnets
            for parent in parent_list:
                if (
                    helpers.get_no_module_name(parent).startswith("aws_subnet")
                    and sg not in tfdata["graphdict"][parent]
                    and sg + "~1" not in parent_list
                ):
                    tfdata["graphdict"][parent].append(sg)
                    if sg_connection in tfdata["graphdict"][parent]:
                        tfdata["graphdict"][parent].remove(sg_connection)
    # Remove SGs from VPC level (they belong in subnets)
    for sg in list_of_sgs:
        parent_list = helpers.list_of_parents(tfdata["graphdict"], sg)
        for parent in parent_list:
            if (
                helpers.get_no_module_name(parent).startswith("aws_vpc")
                and sg in tfdata["graphdict"][parent]
            ):
                tfdata["graphdict"][parent].remove(sg)
    # Remove orphan security groups with no connections
    for sg in list_of_sgs:
        if len(tfdata["graphdict"][sg]) == 0:
            del tfdata["graphdict"][sg]
    return tfdata


def aws_handle_sharedgroup(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group shared AWS services into a shared services group.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with shared services grouped
    """
    graphcopy = dict(tfdata["graphdict"])
    # Find all shared services and group them
    for node in graphcopy:
        substring_match = [s for s in SHARED_SERVICES if s in node]
        if substring_match:
            # Create shared services group if needed
            if not tfdata["graphdict"].get("aws_group.shared_services"):
                tfdata["graphdict"]["aws_group.shared_services"] = []
                tfdata["meta_data"]["aws_group.shared_services"] = {}
            # Add node to shared services group
            if node not in tfdata["graphdict"]["aws_group.shared_services"]:
                tfdata["graphdict"]["aws_group.shared_services"].append(node)
    # Replace consolidated nodes with their consolidated names
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


def aws_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle load balancer type variants and connections.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with LB variants configured
    """
    # Find all load balancers
    found_lbs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_lb")
    for lb in found_lbs:
        # Determine LB type (ALB, NLB, etc.)
        lb_type = helpers.check_variant(lb, tfdata["meta_data"][lb])
        renamed_node = lb_type + "." + "elb"
        # Initialize renamed node metadata
        if not tfdata["meta_data"].get(renamed_node):
            tfdata["meta_data"][renamed_node] = copy.deepcopy(tfdata["meta_data"][lb])
        for connection in list(tfdata["graphdict"][lb]):
            if not tfdata["graphdict"].get(renamed_node):
                tfdata["graphdict"][renamed_node] = list()
            c_type = connection.split(".")[0]
            if c_type not in SHARED_SERVICES:
                tfdata["graphdict"][renamed_node].append(connection)
                tfdata["graphdict"][lb].remove(connection)
            if (
                tfdata["meta_data"].get(connection)
                and tfdata["meta_data"][connection].get("count")
                or tfdata["meta_data"][connection].get("desired_count")
            ) and connection.split(".")[0] not in SHARED_SERVICES:
                # Sets LB count to the max of the count of any dependencies
                if int(tfdata["meta_data"][connection]["count"]) > int(
                    tfdata["meta_data"][renamed_node]["count"]
                ):
                    tfdata["meta_data"][renamed_node]["count"] = int(
                        tfdata["meta_data"][connection]["count"]
                    )
                    plist = helpers.list_of_parents(tfdata["graphdict"], renamed_node)
                    for p in plist:
                        tfdata["meta_data"][p]["count"] = int(
                            tfdata["meta_data"][connection]["count"]
                        )
            parents = helpers.list_of_parents(tfdata["graphdict"], lb)
            # Replace any parent references to original LB instance to the renamed node with LB type
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


def aws_handle_dbsubnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle RDS database subnet group relationships.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with DB subnet groups configured
    """
    # Find all DB subnet groups
    db_subnet_list = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_db_subnet_group"
    )
    for dbsubnet in db_subnet_list:
        db_grouping = helpers.list_of_parents(tfdata["graphdict"], dbsubnet)
        if db_grouping:
            # Move DB subnet group from subnet to VPC level
            for subnet in db_grouping:
                if helpers.get_no_module_name(subnet).startswith("aws_subnet"):
                    tfdata["graphdict"][subnet].remove(dbsubnet)
                    # Navigate up to VPC through AZ
                    az = helpers.list_of_parents(tfdata["graphdict"], subnet)[0]
                    vpc = helpers.list_of_parents(tfdata["graphdict"], az)[0]
                    if dbsubnet not in tfdata["graphdict"][vpc]:
                        tfdata["graphdict"][vpc].append(dbsubnet)
            # If RDS has security group, use that instead
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


def aws_handle_vpcendpoints(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Move VPC endpoints into VPC parent.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with VPC endpoints moved
    """
    # Find all VPC endpoints
    vpc_endpoints = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_vpc_endpoint"
    )
    # Get the VPC node
    vpc = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_vpc.")[0]
    # Move endpoints into VPC and remove as separate nodes
    for vpc_endpoint in vpc_endpoints:
        tfdata["graphdict"][vpc].append(vpc_endpoint)
        del tfdata["graphdict"][vpc_endpoint]
    return tfdata


def aws_handle_ecs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle ECS service configurations.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with ECS configured
    """
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


def random_string_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Remove random string resources from graph.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with random strings removed
    """
    randoms = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "random_string.")
    for r in randoms:
        del tfdata["graphdict"][r]
    return tfdata


def match_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Match resources based on suffix patterns and dependencies.
    
    Args:
        tfdata: Terraform data dictionary
        
    Returns:
        Updated tfdata with resources matched
    """
    # Match AZs to subnets by suffix
    tfdata["graphdict"] = match_az_to_subnets(tfdata["graphdict"])
    # Match security groups to subnets by suffix
    tfdata["graphdict"] = match_sg_to_subnets(tfdata["graphdict"])
    # Link EC2 instances to IAM roles
    tfdata["graphdict"] = link_ec2_to_iam_roles(tfdata["graphdict"])
    # Split NAT gateways per subnet
    tfdata["graphdict"] = split_nat_gateways(tfdata["graphdict"])
    # Remove generic subnet references
    tfdata["graphdict"] = _remove_consolidated_subnet_refs(tfdata["graphdict"])
    return tfdata


def _remove_consolidated_subnet_refs(graphdict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Remove generic consolidated subnet references from VPC.
    
    Args:
        graphdict: Resource graph dictionary
        
    Returns:
        Updated graphdict with consolidated subnets removed
    """

    # Remove generic subnet references from VPCs
    for resource in list(graphdict.keys()):
        if "aws_vpc" in resource:
            # Keep only numbered subnets and non-subnet resources
            graphdict[resource] = [
                conn
                for conn in graphdict[resource]
                if not ("aws_subnet" in conn and "~" not in conn and "[" not in conn)
            ]

    return graphdict


def split_nat_gateways(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Split NAT gateways into numbered instances per subnet.
    
    Args:
        terraform_data: Resource graph dictionary
        
    Returns:
        Updated graph with numbered NAT gateways
    """
    result = dict(terraform_data)
    suffix_pattern = r"~(\d+)$"

    # Find unnumbered NAT gateways
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
    """Link EC2 instances to IAM roles via instance profiles.
    
    Args:
        terraform_data: Resource graph dictionary
        
    Returns:
        Updated graph with EC2-IAM links
    """
    result = dict(terraform_data)

    # Map instance profiles to IAM roles
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


def link_sqs_queue_policy(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Link SQS queues to resources via queue policies.
    
    Args:
        terraform_data: Resource graph dictionary
        
    Returns:
        Updated graph with SQS queue links
    """
    result = dict(terraform_data)

    # Map queue policies to SQS queues
    policy_to_queue = {}
    for resource, deps in terraform_data.items():
        if "aws_sqs_queue" in resource:
            for dep in deps:
                if "aws_sqs_queue_policy" in dep:
                    policy_to_queue[dep] = resource

    # Find queue policies that connect to resources and add SQS queue to those resource deps
    for resource, deps in terraform_data.items():
        for dep in deps:
            if "aws_sqs_queue_policy." in dep:
                sqs_queue = policy_to_queue[dep]
                if sqs_queue not in result[resource]:
                    result[resource].append(sqs_queue)
    return result


def match_az_to_subnets(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Match availability zones to subnets by suffix pattern.

    Args:
        terraform_data: Resource graph dictionary

    Returns:
        Updated graph with AZ-subnet matches
    """
    result = dict(terraform_data)

    # Pattern to extract suffix from resource names
    suffix_pattern = r"~(\d+)$"

    # Find all availability zone resources
    az_resources = [
        key
        for key in terraform_data.keys()
        if key.startswith("aws_az.availability_zone")
    ]

    # Match each AZ to subnets with same suffix
    for az in az_resources:
        # Extract numeric suffix from AZ name
        az_match = re.search(suffix_pattern, az)
        if not az_match:
            continue

        az_suffix = az_match.group(1)

        # Get all dependencies of this AZ
        az_dependencies = terraform_data.get(az, [])

        # Filter subnets with matching suffix
        matched_subnets = []
        for dep in az_dependencies:
            if "subnet" in dep.lower():
                dep_match = re.search(suffix_pattern, dep)
                if dep_match and dep_match.group(1) == az_suffix:
                    matched_subnets.append(dep)

        # Update AZ with only matched subnets
        result[az] = matched_subnets

    return result


def match_sg_to_subnets(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Match security groups to subnets by suffix pattern.
    
    Args:
        terraform_data: Resource graph dictionary
        
    Returns:
        Updated graph with SG-subnet matches
    """
    result = dict(terraform_data)
    suffix_pattern = r"~(\d+)$"

    # Group subnets by base name and collect SGs
    subnet_groups = {}
    for key in terraform_data.keys():
        if "aws_subnet" in key.lower():
            # Extract base name without suffix
            base_name = re.sub(r"\[\d+\]~\d+$", "", key)
            if base_name not in subnet_groups:
                subnet_groups[base_name] = {"subnets": [], "sg_bases": set()}
            subnet_groups[base_name]["subnets"].append(key)

            # Collect SG base names from subnet dependencies
            for dep in terraform_data.get(key, []):
                if "aws_security_group" in dep:
                    sg_base = re.sub(r"~\d+$", "", dep)
                    subnet_groups[base_name]["sg_bases"].add(sg_base)

    # Ensure all subnets have SGs with matching suffix
    for base_name, group_data in subnet_groups.items():
        for subnet in group_data["subnets"]:
            # Extract subnet suffix
            subnet_match = re.search(suffix_pattern, subnet)
            if subnet_match:
                subnet_suffix = subnet_match.group(1)
                # Add all SGs with matching suffix
                for sg_base in group_data["sg_bases"]:
                    sg_with_suffix = f"{sg_base}~{subnet_suffix}"
                    if (
                        sg_with_suffix in terraform_data
                        and sg_with_suffix not in result[subnet]
                    ):
                        result[subnet].append(sg_with_suffix)

    return result
