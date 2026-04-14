"""AWS resource-specific handlers for Terraform graph processing.

Handles special cases for AWS resources including security groups, load balancers,
EFS, CloudFront, autoscaling, subnets, and other AWS-specific relationships.
"""

from typing import Dict, List, Any
import modules.config.cloud_config_aws as cloud_config
import modules.helpers as helpers
import modules.resource_transformers as transformers
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
    for r in sorted(tfdata["graphdict"].keys()):
        for d in DISCONNECT_SERVICES:
            if d in r:
                tfdata["graphdict"][r] = []

    return tfdata


def aws_handle_autoscaling(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle AWS autoscaling relationships and counts.

    Part 1: Copies subnet count metadata to autoscaling targets and their ECS services
    Part 2: Redirects subnet→service connections to subnet→ASG

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with autoscaling configured
    """
    # Get all autoscaling resources
    asg_resources = [
        r
        for r in tfdata["graphdict"]
        if helpers.get_no_module_name(r).startswith("aws_appautoscaling_target")
    ]

    if not asg_resources:
        return tfdata

    # Get services connected to ASG (children)
    try:
        scaler_links = next(
            v
            for k, v in tfdata["graphdict"].items()
            if "aws_appautoscaling_target" in k
        )
    except StopIteration:
        return tfdata

    # Find all subnets
    possible_subnets = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_subnet")
    ]

    # Part 1: Count propagation
    for asg in asg_resources:
        # Skip if ASG already has count
        if tfdata["meta_data"].get(asg, {}).get("count"):
            continue

        # Find subnets that have services as children (shared with ASG)
        for service in scaler_links:
            for subnet in possible_subnets:
                if service in tfdata["graphdict"].get(subnet, []):
                    # Copy subnet count to ASG and service
                    count_value = tfdata["meta_data"].get(subnet, {}).get("count")
                    if count_value is not None:
                        # Copy to ASG
                        if asg not in tfdata["meta_data"]:
                            tfdata["meta_data"][asg] = {}
                        tfdata["meta_data"][asg]["count"] = (
                            int(count_value)
                            if isinstance(count_value, (int, str))
                            else count_value
                        )

                        # Copy to services (not policies)
                        if "policy" not in service.lower():
                            if service not in tfdata["meta_data"]:
                                tfdata["meta_data"][service] = {}
                            tfdata["meta_data"][service]["count"] = (
                                int(count_value)
                                if isinstance(count_value, (int, str))
                                else count_value
                            )
                    break  # Found subnet for this service, move to next service

    # Part 2: Connection redirection (subnet→service becomes subnet→ASG)
    for asg in asg_resources:
        for connection in sorted(tfdata["graphdict"].get(asg, [])):
            # Find subnets that have this service as child
            asg_target_parents = helpers.list_of_parents(
                tfdata["graphdict"], connection
            )
            subnets_to_change = [
                k
                for k in asg_target_parents
                if helpers.get_no_module_name(k).startswith("aws_subnet")
            ]

            # Redirect subnet→service to subnet→ASG
            for subnet in subnets_to_change:
                if asg not in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].append(asg)
                helpers.safe_remove_connection(tfdata, subnet, connection)

    return tfdata


def handle_cloudfront_domains(
    origin_string: str, domain: str, mdata: Dict[str, Any]
) -> str:
    """Link CloudFront to resources by matching domain names.

    Args:
        origin_string: Original origin configuration string
        domain: Domain name to search for
        mdata: Resource metadata dictionary

    Returns:
        Updated origin string with resource references
    """
    # Check if domain is a module output reference (e.g., module.s3_bucket.output_name)
    if "module." in domain:
        # Extract module name and find matching resources
        module_pattern = r"module\.([^.]+)\.(.+)"
        match = re.match(module_pattern, domain)
        if match:
            module_name = match.group(1)
            # Find S3 bucket resources that match the module name
            for key in mdata.keys():
                if module_name in key and "aws_s3_bucket" in key:
                    return origin_string.replace(domain, key)

    # Search metadata for domain references
    for key, value in mdata.items():
        for _, v in value.items():
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


def handle_cf_origins(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process CloudFront origin configurations.

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
                    # Link origin domain to resources
                    if origin_domain:
                        tfdata["meta_data"][cf_resource]["origin"] = (
                            handle_cloudfront_domains(
                                str(origin_source), origin_domain, tfdata["meta_data"]
                            )
                        )
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


def generate_az_node_name(subnet_name: str, subnet_metadata: Dict[str, Any]) -> str:
    """Generate availability zone node name from subnet metadata.

    This is a helper function for the insert_intermediate_node transformer.

    Args:
        subnet_name: Name of the subnet resource (unused - required for transformer signature)
        subnet_metadata: Metadata dictionary for the subnet

    Returns:
        Generated AZ node name
    """
    _ = subnet_name  # Unused but required by transformer signature

    # Prefer availability_zone_id when available (more specific than availability_zone)
    az_value = subnet_metadata.get("availability_zone", "unknown")
    az_id = subnet_metadata.get("availability_zone_id", "")
    region = subnet_metadata.get("region")

    # Boolean True means "computed after apply" in Terraform plan — not a real value
    _is_computed = lambda v: v is True or str(v) == "True"

    if az_id and not _is_computed(az_id):
        # Use availability_zone_id directly - it's already unique per AZ
        az = "aws_az.availability_zone_" + str(az_id)
        az = az.replace("-", "_")
        # Don't add suffix - the zone ID is already unique
    elif az_value and not _is_computed(az_value):
        # Use availability_zone value and add suffix for zone letter
        az = "aws_az.availability_zone_" + str(az_value)
        az = az.replace("-", "_")
        az = _add_suffix(az)
    else:
        # No real AZ info - use region if available, else "unknown"
        fallback = region if region else "unknown"
        az = "aws_az.availability_zone_" + str(fallback)
        az = az.replace("-", "_")
        az = _add_suffix(az)

    return az


def aws_prepare_subnet_az_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare AZ metadata for subnets before transformers run.

    This function runs BEFORE transformations (handler_execution_order: "before")
    to copy availability_zone and region data from original_metadata to meta_data
    so that the generic insert_intermediate_node transformer can use them.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with AZ metadata prepared
    """
    # Find all subnet resources (excluding hidden)
    subnet_resources = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("aws_subnet")
        and k not in tfdata.get("hidden", [])
    ]

    # Copy necessary metadata from original_metadata to meta_data
    # so that generate_az_node_name can access it
    for subnet in subnet_resources:
        original_meta = tfdata.get("original_metadata", {}).get(subnet, {})

        # Ensure meta_data exists for this subnet
        if subnet not in tfdata["meta_data"]:
            tfdata["meta_data"][subnet] = {}

        # Copy availability_zone, availability_zone_id, and region for AZ name generation
        if "availability_zone" in original_meta:
            tfdata["meta_data"][subnet]["availability_zone"] = original_meta[
                "availability_zone"
            ]
        if "availability_zone_id" in original_meta:
            tfdata["meta_data"][subnet]["availability_zone_id"] = original_meta[
                "availability_zone_id"
            ]
        if "region" in original_meta:
            tfdata["meta_data"][subnet]["region"] = original_meta["region"]

    # Blank-node filling is deferred until the end of match_resources so that
    # we only fill subnets that are *still* empty after all placement logic
    # (place_resources_in_subnets, NAT expansion, LB expansion, etc.) runs.

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
            for fs_connection in sorted(list(tfdata["graphdict"][fs])):
                if helpers.get_no_module_name(fs_connection).startswith(
                    "aws_efs_mount_target"
                ):
                    # Remove mount target from file system
                    helpers.safe_remove_connection(tfdata, fs, fs_connection)
                else:
                    # Move other connections to file system
                    tfdata["graphdict"][fs_connection].append(fs)
                    helpers.safe_remove_connection(tfdata, fs, fs_connection)
    # Replace EFS file system references with mount target
    for node in sorted(tfdata["graphdict"].keys()):
        connections = tfdata["graphdict"][node]
        if helpers.consolidated_node_check(node, tfdata):
            for connection in list(connections):
                if helpers.get_no_module_name(connection).startswith(
                    "aws_efs_file_system"
                ):
                    # Use first mount target as replacement
                    target = efs_mount_targets[0].split("~")[0]
                    target = helpers.remove_brackets_and_numbers(target)
                    helpers.safe_remove_connection(tfdata, node, connection)
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
    for sg in sorted(sglist):
        for sg_connection in sorted(list(tfdata["graphdict"][sg])):
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
                    helpers.safe_remove_connection(tfdata, sg, sg_connection)
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
    # Filter to non-SG resources and sort for deterministic order
    bound_nodes = sorted(
        [
            s
            for s in all_sg_parents
            if not helpers.get_no_module_name(s).startswith("aws_security_group")
        ]
    )
    # Process each resource bound to a security group
    for target in bound_nodes:
        target_type = helpers.get_no_module_name(target).split(".")[0]
        sg_to_purge = list()
        # Reverse SG relationships for non-group nodes
        if target_type not in GROUP_NODES and target_type != "aws_security_group_rule":
            for connection in sorted(list(tfdata["graphdict"][target])):
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
                            if connection in tfdata["meta_data"]:
                                tfdata["meta_data"][unique_name] = copy.deepcopy(
                                    tfdata["meta_data"][connection]
                                )
                            sg_to_purge.append(connection)
                            # Remove target from original SG connections since
                            # the unique copy now owns this relationship
                            helpers.safe_remove_connection(tfdata, connection, target)
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
                    helpers.safe_remove_connection(tfdata, target, connection)
                    tfdata["graphdict"][connection].append(target)
        # Remove Security Group Rules from associations with the security group
        # This will ensure only nodes that are protected with a security group are drawn with the red boundary
        if target_type == "aws_security_group_rule":
            for connection in sorted(list(tfdata["graphdict"][target])):
                if (
                    connection in tfdata["graphdict"].keys()
                    and len(tfdata["graphdict"][connection]) == 0
                ):
                    helpers.delete_node(
                        tfdata, connection, remove_from_connections=False
                    )
                plist = helpers.list_of_parents(tfdata["graphdict"], connection)
                for p in plist:
                    helpers.safe_remove_connection(tfdata, p, connection)
        # Replace any references to nodes within the security group with the security group
        references = sorted(list(helpers.list_of_parents(tfdata["graphdict"], target)))
        if sg_to_purge:
            for purge in sg_to_purge:
                if purge in references:
                    references.remove(purge)
        replacement_sgs = sorted(
            [
                k
                for k in references
                if helpers.get_no_module_name(k).startswith("aws_security_group")
            ]
        )
        if replacement_sgs:
            for replaced_group in replacement_sgs:
                for node in sorted(references):
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
        if helpers.safe_remove_connection(tfdata, sg2, common):
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
        for sg_connection in sorted(list(tfdata["graphdict"][sg])):
            parent_list = sorted(
                helpers.list_of_parents(tfdata["graphdict"], sg_connection)
            )
            # Add SG to parent subnets
            for parent in parent_list:
                if (
                    helpers.get_no_module_name(parent).startswith("aws_subnet")
                    and sg not in tfdata["graphdict"][parent]
                    and sg + "~1" not in parent_list
                ):
                    tfdata["graphdict"][parent].append(sg)
                    helpers.safe_remove_connection(tfdata, parent, sg_connection)
    # Remove SGs from VPC level (they belong in subnets)
    for sg in list_of_sgs:
        parent_list = sorted(helpers.list_of_parents(tfdata["graphdict"], sg))
        for parent in parent_list:
            if (
                helpers.get_no_module_name(parent).startswith("aws_vpc")
                and sg in tfdata["graphdict"][parent]
            ):
                helpers.safe_remove_connection(tfdata, parent, sg)
    # Remove orphan security groups with no connections or parents
    for sg in sorted(list_of_sgs):
        if sg in tfdata["graphdict"] and len(tfdata["graphdict"][sg]) == 0:
            helpers.delete_node(tfdata, sg)
        if (
            helpers.list_of_parents(tfdata["graphdict"], sg, True) == []
            and sg in tfdata["graphdict"]
        ):
            helpers.delete_node(tfdata, sg)
    return tfdata


def aws_handle_sharedgroup(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group shared AWS services into a shared services group.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with shared services grouped
    """
    # Find all shared services and group them
    for node in sorted(tfdata["graphdict"].keys()):
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
        for service in sorted(list(tfdata["graphdict"]["aws_group.shared_services"])):
            if (
                helpers.consolidated_node_check(service, tfdata)
                and "cluster" not in service
            ):
                tfdata["graphdict"]["aws_group.shared_services"] = list(
                    map(
                        lambda x: x.replace(
                            service, helpers.consolidated_node_check(service, tfdata)
                        ),
                        tfdata["graphdict"]["aws_group.shared_services"],
                    )
                )
    # Add default IAM service node
    if not tfdata["graphdict"].get("aws_group.shared_services"):
        tfdata["graphdict"]["aws_group.shared_services"] = []
        tfdata["meta_data"]["aws_group.shared_services"] = {}

    return tfdata


def aws_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle load balancer type variants and connections.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with LB variants configured
    """
    # Find all load balancers
    found_lbs = sorted(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_lb.")
    )
    for lb in found_lbs:
        # Determine LB type (ALB, NLB, etc.)
        if lb not in tfdata["meta_data"]:
            continue

        lb_type = helpers.check_variant(lb, tfdata["meta_data"][lb], tfdata)
        renamed_node = str(lb_type) + "." + "elb"

        # Initialize renamed node metadata
        if not tfdata["meta_data"].get(renamed_node) and lb in tfdata["meta_data"]:
            tfdata["meta_data"][renamed_node] = copy.deepcopy(tfdata["meta_data"][lb])

        # CRITICAL: Create renamed node in graphdict BEFORE processing connections
        # Otherwise, if lb has no connections, renamed_node is never created
        if not tfdata["graphdict"].get(renamed_node):
            tfdata["graphdict"][renamed_node] = list()

        for connection in sorted(list(tfdata["graphdict"][lb])):
            c_type = connection.split(".")[0]
            if c_type not in SHARED_SERVICES:
                tfdata["graphdict"][renamed_node].append(connection)
                helpers.safe_remove_connection(tfdata, lb, connection)

            if (
                tfdata["meta_data"].get(connection)
                and (
                    tfdata["meta_data"][connection].get("count")
                    or tfdata["meta_data"][connection].get("desired_count")
                )
            ) and connection.split(".")[0] not in SHARED_SERVICES:
                # Sets LB count to the max of the count of any dependencies
                conn_count = tfdata["meta_data"][connection].get("count")
                if (
                    conn_count
                    and tfdata["meta_data"].get(renamed_node)
                    and tfdata["meta_data"][renamed_node].get("count")
                    and int(conn_count)
                    > int(tfdata["meta_data"][renamed_node]["count"])
                ):
                    tfdata["meta_data"][renamed_node]["count"] = int(conn_count)
                    plist = sorted(
                        helpers.list_of_parents(tfdata["graphdict"], renamed_node)
                    )
                    for p in plist:
                        if p in tfdata["meta_data"]:
                            tfdata["meta_data"][p]["count"] = int(
                                tfdata["meta_data"][connection]["count"]
                            )
            parents = sorted(helpers.list_of_parents(tfdata["graphdict"], lb))
            # Replace any parent references to original LB instance to the renamed node with LB type
            for p in parents:
                p_type = p.split(".")[0]
                if (
                    p_type in GROUP_NODES
                    and p_type not in SHARED_SERVICES
                    and p_type != "aws_vpc"
                ):
                    tfdata["graphdict"][p].append(renamed_node)
                    # Defensive check: only remove if lb is actually in parent
                    # (SG handler may have already modified structure for multi-subnet LBs)
                    helpers.safe_remove_connection(tfdata, p, lb)
                elif p_type not in GROUP_NODES and p_type not in SHARED_SERVICES:
                    # Remove backward connections from compute resources (Fargate, EC2, etc.) to LB
                    # Traffic should flow LB → ALB → Compute, not Compute → LB
                    helpers.safe_remove_connection(tfdata, p, lb)
        # ELB service points TO ALB instances (correct direction)
        if lb not in tfdata["graphdict"]:
            tfdata["graphdict"][lb] = list()
        if renamed_node not in tfdata["graphdict"][lb]:
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
                    helpers.safe_remove_connection(tfdata, subnet, dbsubnet)
                    # Navigate up to VPC through AZ
                    az = helpers.list_of_parents(tfdata["graphdict"], subnet)[0]
                    vpc = helpers.list_of_parents(tfdata["graphdict"], az)[0]
                    if dbsubnet not in tfdata["graphdict"][vpc]:
                        tfdata["graphdict"][vpc].append(dbsubnet)
            # If RDS has security group, use that instead
            for rds in sorted(tfdata["graphdict"][dbsubnet]):
                rds_references = helpers.list_of_parents(tfdata["graphdict"], rds)
                for check_sg in rds_references:
                    if helpers.get_no_module_name(check_sg).startswith(
                        "aws_security_group"
                    ):
                        helpers.safe_remove_connection(tfdata, vpc, dbsubnet)
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
        helpers.delete_node(tfdata, vpc_endpoint, remove_from_connections=False)
    return tfdata


def aws_handle_ecs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle ECS service configurations.

    Only processes EC2-based ECS services to link them with autoscaling targets.
    Fargate services are skipped as they are serverless and handled well by the
    generic pipeline (shown in subnets like Lambda functions).

    EC2-based ECS requires special handling to show the infrastructure layer
    (autoscaling groups, capacity providers, EC2 instances).

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with EC2 ECS services linked to autoscaling targets
    """
    # ASG expansion is now handled by the aws_autoscaling_group config handler
    # which calls expand_autoscaling_groups_to_subnets directly.
    return tfdata


def aws_handle_lambda_event_source_mapping(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Lambda event source mappings by creating direct event source → Lambda connections.

    Event source mappings (aws_lambda_event_source_mapping) are configuration resources that
    connect event sources (SQS, Kinesis, DynamoDB Streams) to Lambda functions. This handler
    creates direct connections and removes the intermediary mapping node.

    Pattern:
        Before: event_source_mapping → sqs_queue, event_source_mapping → lambda_function
        After: sqs_queue → lambda_function (event_source_mapping removed)

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with direct event source → Lambda connections
    """
    # Create direct connections from SQS to Lambda
    tfdata = transformers.link_peers_via_intermediary(
        tfdata,
        intermediary_pattern="aws_lambda_event_source_mapping",
        source_pattern="aws_sqs_queue",
        target_pattern="aws_lambda_function",
        remove_intermediary=True,
    )

    # Create direct connections from Kinesis to Lambda
    tfdata = transformers.link_peers_via_intermediary(
        tfdata,
        intermediary_pattern="aws_lambda_event_source_mapping",
        source_pattern="aws_kinesis_stream",
        target_pattern="aws_lambda_function",
        remove_intermediary=True,
    )

    # Create direct connections from DynamoDB to Lambda
    tfdata = transformers.link_peers_via_intermediary(
        tfdata,
        intermediary_pattern="aws_lambda_event_source_mapping",
        source_pattern="aws_dynamodb_table",
        target_pattern="aws_lambda_function",
        remove_intermediary=True,
    )

    return tfdata


def expand_autoscaling_groups_to_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Expand autoscaling groups, autoscaling policies and launch templates into numbered instances per subnet.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with numbered autoscaling groups, launch templates, and policies
    """
    autoscaling_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_autoscaling_group"
    )
    subnets = sorted(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_subnet")
    )

    for asg in list(autoscaling_groups):
        if "~" in asg:
            continue

        vpc_zone_identifier = (
            tfdata["meta_data"].get(asg, {}).get("vpc_zone_identifier", [])
        )
        if isinstance(vpc_zone_identifier, str):
            vpc_zone_identifier = [vpc_zone_identifier]

        matching_subnets = sorted(
            [
                s
                for s in subnets
                if any(
                    tfdata["meta_data"].get(s, {}).get("id", "") in str(sid)
                    for sid in vpc_zone_identifier
                )
            ]
        )

        if len(matching_subnets) <= 1:
            continue

        children = tfdata["graphdict"].get(asg, [])
        launch_templates = [r for r in children if "aws_launch_template" in r]
        policies = [r for r in children if "aws_autoscaling_policy" in r]
        ecs_clusters = [r for r in tfdata["graphdict"] if "aws_ecs_cluster" in r]

        for i in range(1, len(matching_subnets) + 1):
            numbered_asg = f"{asg}~{i}"
            tfdata["graphdict"][numbered_asg] = []
            tfdata["meta_data"][numbered_asg] = copy.deepcopy(
                tfdata["meta_data"].get(asg, {})
            )

            for lt in launch_templates:
                numbered_lt = f"{lt}~{i}"
                tfdata["graphdict"][numbered_lt] = list(tfdata["graphdict"].get(lt, []))
                tfdata["meta_data"][numbered_lt] = copy.deepcopy(
                    tfdata["meta_data"].get(lt, {})
                )
                tfdata["graphdict"][numbered_asg].append(numbered_lt)

            for policy in policies:
                numbered_policy = f"{policy}~{i}"
                tfdata["graphdict"][numbered_policy] = list(
                    tfdata["graphdict"].get(policy, [])
                )
                tfdata["meta_data"][numbered_policy] = copy.deepcopy(
                    tfdata["meta_data"].get(policy, {})
                )
                tfdata["graphdict"][numbered_asg].append(numbered_policy)

            tfdata["graphdict"][matching_subnets[i - 1]].append(numbered_asg)

        for subnet in subnets:
            helpers.safe_remove_connection(tfdata, subnet, asg)
        helpers.delete_node(
            tfdata, asg, remove_from_connections=False, delete_meta_data=True
        )

        for lt in launch_templates:
            # Update parents that reference this launch template to point to numbered copies
            numbered_lts = [f"{lt}~{j}" for j in range(1, len(matching_subnets) + 1)]
            parents = helpers.list_of_parents(tfdata["graphdict"], lt)
            for parent in parents:
                if parent == asg or parent.startswith(f"{asg}~"):
                    continue  # ASG connections already handled above
                helpers.safe_remove_connection(tfdata, parent, lt)
                for numbered_lt in numbered_lts:
                    if numbered_lt not in tfdata["graphdict"].get(parent, []):
                        tfdata["graphdict"][parent].append(numbered_lt)
            helpers.delete_node(tfdata, lt, remove_from_connections=False)

        for policy in policies:
            helpers.delete_node(tfdata, policy, remove_from_connections=False)

        for cluster in ecs_clusters:
            helpers.delete_node(tfdata, cluster, remove_from_connections=False)

    return tfdata


def is_eks_auto_mode(tfdata: Dict[str, Any], cluster: str) -> bool:
    """Check if EKS cluster has auto mode enabled.

    Args:
        tfdata: Terraform data dictionary
        cluster: Cluster resource name

    Returns:
        True if auto mode is enabled
    """
    metadata = tfdata.get("meta_data", {}).get(cluster, {})
    compute_config = metadata.get("compute_config", {})

    # Convert string representation to list/dict if needed
    if isinstance(compute_config, str):
        if compute_config in ("[]", "{}"):
            return False
        try:
            compute_config = literal_eval(compute_config)
        except:
            return False

    # Handle list of configs (take first element)
    if isinstance(compute_config, list):
        compute_config = compute_config[0] if compute_config else {}

    if isinstance(compute_config, dict):
        if compute_config.get("node_pools"):
            return "system" in compute_config["node_pools"]
        return compute_config.get("enabled") == True
    return False


def aws_handle_eks(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle EKS cluster and node group configurations.

    Creates EKS service groups, expands node groups, and links control plane to workers.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with EKS clusters and node groups configured
    """
    # Process EKS resources in order
    tfdata = handle_eks_cluster_grouping(tfdata)
    tfdata = expand_eks_auto_mode_clusters(tfdata)
    tfdata = link_eks_control_plane_to_nodes(tfdata)
    tfdata = match_node_groups_to_subnets(tfdata)
    tfdata = match_fargate_profiles_to_subnets(tfdata)
    tfdata = link_node_groups_to_worker_nodes(tfdata)
    return tfdata


def expand_eks_auto_mode_clusters(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Create numbered instances of EKS clusters with auto mode enabled.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with numbered auto cluster instances
    """
    # Find EKS clusters with auto mode enabled
    eks_clusters = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_cluster"
    )

    auto_cluster = None
    for cluster in eks_clusters:
        if is_eks_auto_mode(tfdata, cluster):
            auto_cluster = cluster
            break

    if not auto_cluster:
        return tfdata

    parents = helpers.list_of_parents(tfdata["graphdict"], auto_cluster)
    subnets = [p for p in parents if "aws_subnet" in p]

    if len(subnets) <= 1:
        return tfdata

    counter = 1
    for subnet in sorted(subnets):
        numbered = f"{auto_cluster}_{counter}"
        tfdata["graphdict"][numbered] = []
        tfdata["meta_data"][numbered] = copy.deepcopy(tfdata["meta_data"][auto_cluster])

        managed_group = f"aws_group.aws_managed_ec2_{counter}"
        tfdata["graphdict"][managed_group] = [numbered]
        tfdata["meta_data"][managed_group] = {}

        tfdata["graphdict"][subnet] = [
            managed_group if x == auto_cluster else x
            for x in tfdata["graphdict"][subnet]
        ]
        counter += 1

    eks_service = "aws_eks_service.eks"
    tfdata["graphdict"][eks_service] = []
    tfdata["meta_data"][eks_service] = {}
    for i in range(1, counter):
        tfdata["graphdict"][eks_service].append(f"{auto_cluster}_{i}")

    cluster_name = auto_cluster.split(".")[-1]
    eks_group = f"aws_account.eks_control_plane_{cluster_name}"

    # Redirect all parent connections to expanded nodes (except eks_group)
    for parent in parents:
        if (
            parent != eks_group
            and parent in tfdata["graphdict"]
            and auto_cluster in tfdata["graphdict"][parent]
        ):
            idx = tfdata["graphdict"][parent].index(auto_cluster)
            helpers.safe_remove_connection(tfdata, parent, auto_cluster)
            for i in range(1, counter):
                tfdata["graphdict"][parent].insert(idx, f"{auto_cluster}_{i}")

    # Handle eks_group separately - point to eks_service
    if (
        eks_group in tfdata["graphdict"]
        and auto_cluster in tfdata["graphdict"][eks_group]
    ):
        helpers.safe_remove_connection(tfdata, eks_group, auto_cluster)
        tfdata["graphdict"][eks_group].append(eks_service)

    helpers.delete_node(tfdata, auto_cluster, delete_meta_data=True)

    return tfdata


def handle_eks_cluster_grouping(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Create EKS service group and move control plane into it.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with EKS service groups created
    """
    # Find all EKS clusters
    eks_clusters = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_cluster"
    )

    if not eks_clusters:
        return tfdata

    # Check if any node groups or Fargate profiles exist
    has_node_groups = bool(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_eks_node_group")
    )
    has_fargate = bool(
        helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "aws_eks_fargate_profile"
        )
    )

    # Create EKS service group for each cluster
    for cluster in eks_clusters:
        cluster_name = cluster.split(".")[-1]
        eks_group_name = f"aws_account.eks_control_plane_{cluster_name}"

        # Create EKS service group
        if eks_group_name not in tfdata["graphdict"]:
            tfdata["graphdict"][eks_group_name] = []
            tfdata["meta_data"][eks_group_name] = {
                "type": "eks_service",
                "name": f"EKS Service - {cluster_name}",
            }

        # Move control plane into EKS service group
        if cluster not in tfdata["graphdict"][eks_group_name]:
            tfdata["graphdict"][eks_group_name].append(cluster)

        # Skip removing from subnets if cluster has auto mode enabled
        if is_eks_auto_mode(tfdata, cluster):
            continue

        # Only remove cluster from subnets if node groups or Fargate profiles exist
        if has_node_groups or has_fargate:
            for node in sorted(tfdata["graphdict"].keys()):
                node_type = helpers.get_no_module_name(node).split(".")[0]
                if node_type in ["aws_vpc", "aws_subnet", "aws_az"]:
                    helpers.safe_remove_connection(tfdata, node, cluster)
        else:
            # For Karpenter (no node groups/Fargate), expand cluster into numbered instances per subnet
            subnets_with_cluster = sorted(
                [
                    node
                    for node in tfdata["graphdict"].keys()
                    if "aws_subnet" in node and cluster in tfdata["graphdict"][node]
                ]
            )

            if len(subnets_with_cluster) > 1:
                for i, subnet in enumerate(subnets_with_cluster, start=1):
                    numbered_cluster = f"{cluster}~{i}"
                    tfdata["graphdict"][numbered_cluster] = []
                    tfdata["meta_data"][numbered_cluster] = copy.deepcopy(
                        tfdata["meta_data"][cluster]
                    )

                    helpers.safe_remove_connection(tfdata, subnet, cluster)
                    tfdata["graphdict"][subnet].append(numbered_cluster)

                # Update EKS group to link to cluster via existing cluster node
                helpers.safe_remove_connection(tfdata, eks_group_name, cluster)

                # Link numbered clusters to existing cluster node
                tfdata["graphdict"][cluster] = []
                for i in range(1, len(subnets_with_cluster) + 1):
                    tfdata["graphdict"][cluster].append(f"{cluster}~{i}")

                # Add cluster to EKS group
                tfdata["graphdict"][eks_group_name].append(cluster)

                # Detect Karpenter usage
                karpenter_roles = [
                    k
                    for k in tfdata["graphdict"].keys()
                    if "aws_iam_role" in k and "karpenter" in k.lower()
                ]
                karpenter_queues = [
                    k
                    for k in tfdata["graphdict"].keys()
                    if "aws_sqs_queue" in k and "karpenter" in k.lower()
                ]
                has_karpenter_tags = any(
                    "karpenter.sh/discovery"
                    in str(tfdata["meta_data"].get(s, {}).get("tags", ""))
                    for s in subnets_with_cluster
                )

                if karpenter_roles or karpenter_queues or has_karpenter_tags:
                    # Create numbered Karpenter nodes in each subnet FIRST
                    for i in range(1, len(subnets_with_cluster) + 1):
                        karpenter_node = f"tv_karpenter.karpenter~{i}"
                        tfdata["graphdict"][karpenter_node] = [f"{cluster}~{i}"]
                        tfdata["meta_data"][karpenter_node] = {"label": "Karpenter"}
                        # Add Karpenter to subnet
                        tfdata["graphdict"][subnets_with_cluster[i - 1]].append(
                            karpenter_node
                        )

                    # Link IAM roles with instance profiles to numbered clusters
                    for role in sorted(karpenter_roles):
                        if "aws_iam_instance_profile" in str(
                            tfdata["graphdict"].get(role, [])
                        ):
                            for i in range(1, len(subnets_with_cluster) + 1):
                                tfdata["graphdict"][role].append(f"{cluster}~{i}")

                    # Link SQS queues to numbered Karpenter nodes (only if they connect to CloudWatch event targets)
                    for queue in sorted(karpenter_queues):
                        if "aws_cloudwatch_event_target" in str(
                            tfdata["original_graphdict"].get(queue, [])
                        ):
                            for i in range(1, len(subnets_with_cluster) + 1):
                                tfdata["graphdict"][queue].append(
                                    f"tv_karpenter.karpenter~{i}"
                                )

    return tfdata


def link_eks_control_plane_to_nodes(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Expand node groups and link control plane to them.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with node groups expanded and linked
    """
    # Find EKS clusters and node groups
    eks_clusters = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_cluster"
    )
    eks_node_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_node_group"
    )

    for cluster in eks_clusters:
        cluster_name = (
            cluster.split(".")[-1].split("~")[0]
            if "~" in cluster
            else cluster.split(".")[-1]
        )

        # Link cluster to all node groups (numbered or not)
        for node_group in eks_node_groups:
            # Verify this node group belongs to this cluster
            if node_group in tfdata["meta_data"]:
                cluster_ref = tfdata["meta_data"][node_group].get("cluster_name", "")
                base_cluster = cluster.split("~")[0] if "~" in cluster else cluster
                if (
                    base_cluster in str(cluster_ref)
                    or cluster_name in str(cluster_ref)
                    or str(cluster_ref) in ["True", "", "None"]
                ):
                    # Add connection from cluster to node group
                    if node_group not in tfdata["graphdict"][cluster]:
                        tfdata["graphdict"][cluster].append(node_group)

    return tfdata


def match_node_groups_to_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Match node groups to subnets using sorted order.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with node groups matched to subnets
    """
    # Find all node groups and subnets
    eks_node_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_node_group"
    )
    subnets = sorted(
        helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_subnet")
    )
    private_subnets = sorted([s for s in subnets if "private" in s.lower()])

    # Process each unnumbered node group
    for node_group in list(eks_node_groups):
        if "~" in node_group:
            continue

        # Get subnet references from metadata
        subnet_ids = tfdata["meta_data"].get(node_group, {}).get("subnet_ids", [])
        if isinstance(subnet_ids, str):
            subnet_ids = [subnet_ids]

        # Find matching subnets
        matching_subnets = []
        if subnet_ids and subnet_ids != []:
            for subnet in subnets:
                subnet_id = tfdata["meta_data"].get(subnet, {}).get("id", "")
                if any(subnet_id in str(sid) for sid in subnet_ids):
                    matching_subnets.append(subnet)
        else:
            # Fallback: use private subnets if no subnet_ids in metadata
            matching_subnets = private_subnets

        # Sort for deterministic assignment
        matching_subnets = sorted(matching_subnets)

        # Create numbered instances if multiple subnets
        if len(matching_subnets) > 1:
            # Create numbered node groups
            for i in range(1, len(matching_subnets) + 1):
                numbered_node_group = f"{node_group}~{i}"

                if numbered_node_group not in tfdata["graphdict"]:
                    tfdata["graphdict"][numbered_node_group] = list(
                        tfdata["graphdict"].get(node_group, [])
                    )
                    tfdata["meta_data"][numbered_node_group] = copy.deepcopy(
                        tfdata["meta_data"].get(node_group, {})
                    )

            # Add each numbered node group to its corresponding subnet only
            for i, subnet in enumerate(matching_subnets, start=1):
                numbered_node_group = f"{node_group}~{i}"
                if numbered_node_group not in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].append(numbered_node_group)

            # Remove original from all subnets
            for subnet in subnets:
                helpers.safe_remove_connection(tfdata, subnet, node_group)

            # Delete original
            helpers.delete_node(
                tfdata, node_group, remove_from_connections=False, delete_meta_data=True
            )

        elif len(matching_subnets) == 1:
            subnet = matching_subnets[0]
            if node_group not in tfdata["graphdict"][subnet]:
                tfdata["graphdict"][subnet].append(node_group)

    # Link numbered node groups to control plane
    eks_clusters = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_cluster"
    )
    all_node_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_node_group"
    )

    for cluster in eks_clusters:
        cluster_name = (
            cluster.split(".")[-1].split("~")[0]
            if "~" in cluster
            else cluster.split(".")[-1]
        )
        for node_group in all_node_groups:
            if node_group in tfdata["meta_data"]:
                cluster_ref = tfdata["meta_data"][node_group].get("cluster_name", "")
                base_cluster = cluster.split("~")[0] if "~" in cluster else cluster
                if (
                    base_cluster in str(cluster_ref)
                    or cluster_name in str(cluster_ref)
                    or str(cluster_ref) in ["True", "", "None"]
                ):
                    if node_group not in tfdata["graphdict"].get(cluster, []):
                        tfdata["graphdict"][cluster].append(node_group)

    return tfdata


def link_node_groups_to_worker_nodes(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Link node groups to EC2 instances or Auto Scaling Groups.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with worker nodes linked to node groups
    """
    # Find node groups and potential worker nodes
    eks_node_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_node_group"
    )
    ec2_instances = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_instance"
    )
    auto_scaling_groups = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_autoscaling_group"
    )

    for node_group in eks_node_groups:
        node_group_name = (
            node_group.split(".")[-1].replace("~", "").replace("[", "").replace("]", "")
        )

        # Check for ASG-based node groups
        for asg in auto_scaling_groups:
            # Check if ASG tags reference this node group
            if asg in tfdata["meta_data"]:
                tags = tfdata["meta_data"][asg].get("tags", {})
                asg_name = asg.split(".")[-1]

                # Match by name or tags
                if (
                    node_group_name in asg_name
                    or node_group_name in str(tags)
                    or "eks:nodegroup-name" in str(tags)
                ):
                    # Link node group to ASG
                    if asg not in tfdata["graphdict"][node_group]:
                        tfdata["graphdict"][node_group].append(asg)

        # Check for EC2-based worker nodes
        for instance in ec2_instances:
            if instance in tfdata["meta_data"]:
                tags = tfdata["meta_data"][instance].get("tags", {})

                # Check if instance tags reference this node group
                if "eks:nodegroup-name" in str(tags):
                    nodegroup_tag = str(tags.get("eks:nodegroup-name", ""))
                    if node_group_name in nodegroup_tag:
                        # Link node group to EC2 instance
                        if instance not in tfdata["graphdict"][node_group]:
                            tfdata["graphdict"][node_group].append(instance)

        # If node group has no workers, add metadata note
        if not tfdata["graphdict"].get(node_group):
            if node_group in tfdata["meta_data"]:
                desired_size = tfdata["meta_data"][node_group].get("desired_size", "")
                tfdata["meta_data"][node_group][
                    "note"
                ] = f"Manages worker nodes (count: {desired_size})"

    return tfdata


def match_fargate_profiles_to_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Match Fargate profiles to subnets by creating numbered instances.

    When a Fargate profile spans multiple subnets, create numbered instances
    (profile~1, profile~2) to match each subnet. Delete the original unnumbered
    profile after creating numbered instances.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Fargate profiles matched to subnets
    """
    # Find all fargate profiles and subnets
    fargate_profiles = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_fargate_profile"
    )
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_subnet")

    for profile in list(fargate_profiles):
        # Skip if already numbered
        if "~" in profile:
            continue

        # Check if profile has subnet references in metadata
        subnet_ids = []
        if profile in tfdata["meta_data"]:
            subnet_ids = tfdata["meta_data"][profile].get("subnet_ids", [])
            if isinstance(subnet_ids, str):
                subnet_ids = [subnet_ids]

        # Find matching subnets
        matching_subnets = []
        for subnet in subnets:
            subnet_id = tfdata["meta_data"].get(subnet, {}).get("id", "")
            subnet_name = subnet.split(".")[-1]

            # Check if subnet matches by ID or name
            if any(
                subnet_id in str(sid) or subnet_name in str(sid) for sid in subnet_ids
            ):
                matching_subnets.append(subnet)

        # If profile spans multiple subnets, create numbered instances
        if len(matching_subnets) > 1:
            # Sort for deterministic suffix assignment
            matching_subnets = sorted(matching_subnets)

            for i, subnet in enumerate(matching_subnets, start=1):
                numbered_profile = f"{profile}~{i}"

                # Create numbered instance
                if numbered_profile not in tfdata["graphdict"]:
                    tfdata["graphdict"][numbered_profile] = list(
                        tfdata["graphdict"].get(profile, [])
                    )
                    tfdata["meta_data"][numbered_profile] = copy.deepcopy(
                        tfdata["meta_data"].get(profile, {})
                    )

                # Add numbered profile to subnet
                if numbered_profile not in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].append(numbered_profile)

                # Remove unnumbered profile from subnet if present
                helpers.safe_remove_connection(tfdata, subnet, profile)

            # Update EKS cluster to reference numbered profiles
            eks_clusters = helpers.list_of_dictkeys_containing(
                tfdata["graphdict"], "aws_eks_cluster"
            )
            for cluster in eks_clusters:
                if helpers.safe_remove_connection(tfdata, cluster, profile):
                    # Add all numbered profiles to cluster
                    for i in range(1, len(matching_subnets) + 1):
                        numbered_profile = f"{profile}~{i}"
                        if numbered_profile not in tfdata["graphdict"][cluster]:
                            tfdata["graphdict"][cluster].append(numbered_profile)

            # Update other resources that reference the Fargate profile
            # (e.g., IAM roles for Fargate pod execution)
            for resource in list(tfdata["graphdict"].keys()):
                if helpers.safe_remove_connection(tfdata, resource, profile):
                    # Add all numbered profiles
                    for i in range(1, len(matching_subnets) + 1):
                        numbered_profile = f"{profile}~{i}"
                        if numbered_profile not in tfdata["graphdict"][resource]:
                            tfdata["graphdict"][resource].append(numbered_profile)

            # Remove original unnumbered profile
            helpers.delete_node(
                tfdata, profile, remove_from_connections=False, delete_meta_data=True
            )

        elif len(matching_subnets) == 1:
            # Single subnet - keep as is
            subnet = matching_subnets[0]
            if profile not in tfdata["graphdict"][subnet]:
                tfdata["graphdict"][subnet].append(profile)

    return tfdata


def helm_release_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle helm_release resources by inspecting chart metadata.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with helm_release connections
    """
    helm_releases = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "helm_release"
    )
    eks_clusters = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_cluster"
    )

    if not eks_clusters:
        return tfdata

    for release in helm_releases:
        chart_name = (
            tfdata.get("meta_data", {}).get(release, {}).get("chart", "").lower()
        )

        if chart_name == "karpenter":
            _handle_karpenter_release(tfdata, release)
        else:
            # Connect other helm releases to first EKS cluster
            if eks_clusters[0] not in tfdata["graphdict"][release]:
                tfdata["graphdict"][release].append(eks_clusters[0])

    return tfdata


def _handle_karpenter_release(tfdata: Dict[str, Any], release: str) -> None:
    """Handle Karpenter helm release by creating numbered instances per subnet.

    Args:
        tfdata: Terraform data dictionary
        release: Karpenter release resource name
    """
    new_name = release.replace("helm_release", "tv_karpenter")
    helpers.rename_node(
        tfdata, release, new_name, update_connections=False, rename_meta_data=True
    )

    node_groups = [k for k in tfdata["graphdict"] if "eks_node_group" in k]
    private_subnets = sorted(
        [k for k in tfdata["graphdict"] if "aws_subnet" in k and "private" in k.lower()]
    )
    eks_clusters = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_eks_cluster"
    )
    launch_templates = [k for k in tfdata["graphdict"] if "aws_launch_template" in k]

    if not (private_subnets and node_groups):
        return

    base_node_group = node_groups[0].split("~")[0]
    base_lt = launch_templates[0].split("~")[0] if launch_templates else None

    # Create numbered instances and link to clusters
    for i, subnet in enumerate(private_subnets, start=1):
        numbered_ng = f"{base_node_group}~{i}"
        tfdata["graphdict"][f"{new_name}~{i}"] = [numbered_ng]
        tfdata["meta_data"][f"{new_name}~{i}"] = copy.deepcopy(
            tfdata["meta_data"][new_name]
        )
        if numbered_ng not in tfdata["graphdict"]:
            tfdata["graphdict"][numbered_ng] = []
            tfdata["meta_data"][numbered_ng] = copy.deepcopy(
                tfdata["meta_data"].get(node_groups[0], {})
            )
        tfdata["graphdict"][subnet].extend([numbered_ng, f"{new_name}~{i}"])
        for cluster in eks_clusters:
            if numbered_ng not in tfdata["graphdict"][cluster]:
                tfdata["graphdict"][cluster].append(numbered_ng)
        if base_lt and numbered_ng not in tfdata["graphdict"].get(base_lt, []):
            tfdata["graphdict"].setdefault(base_lt, []).append(numbered_ng)

    # Cleanup
    unnumbered = [ng for ng in node_groups if "~" not in ng]
    for cluster in eks_clusters:
        for ng in unnumbered:
            helpers.safe_remove_connection(tfdata, cluster, ng)

    for key in (
        [new_name]
        + unnumbered
        + [lt for lt in launch_templates if not tfdata["graphdict"].get(lt)]
    ):
        helpers.delete_node(
            tfdata, key, remove_from_connections=False, delete_meta_data=True
        )


def random_string_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Remove random string resources from graph.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with random strings removed
    """
    randoms = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "random_string.")
    for r in list(randoms):
        helpers.delete_node(tfdata, r)
    return tfdata


def match_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Match resources based on suffix patterns and dependencies.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with resources matched
    """

    # Match security groups to subnets by suffix
    tfdata["graphdict"] = match_sg_to_subnets(tfdata["graphdict"])
    # Link EC2 instances to IAM roles
    tfdata["graphdict"] = link_ec2_to_iam_roles(tfdata["graphdict"])
    # Split NAT gateways per subnet
    tfdata["graphdict"] = split_nat_gateways(tfdata["graphdict"])
    # Place managed resources into matching subnets via subnet_id metadata
    place_resources_in_subnets(tfdata)
    # Place regional (multi-AZ) NAT gateways in the public subnet of each AZ
    place_regional_nat_gateways(tfdata)
    # Connect load balancers to ECS services via target_group_arn
    link_lb_to_ecs_services(tfdata)
    # Drop empty generic placeholder nodes when real module-scoped siblings exist
    _dedupe_placeholder_nodes(tfdata)
    # Remove generic subnet references
    tfdata["graphdict"] = _remove_consolidated_subnet_refs(tfdata["graphdict"])
    # Final step: only now do we fill still-empty subnets with blank spacers so
    # graphviz renders their clusters. Running late means blanks are created
    # only when genuinely needed, not reactively stripped later.
    tfdata["graphdict"] = _fill_empty_groups_with_space(tfdata["graphdict"])
    return tfdata


def _collect_public_subnet_ids(tfdata: Dict[str, Any]) -> set:
    """Return the set of subnet IDs whose route table has an IGW default route.

    Traces the chain: subnet → route_table_association → route_table → routes,
    and collects the subnets whose route table contains a ``0.0.0.0/0`` entry
    pointing at an ``igw-*`` gateway. This is the authoritative definition of
    a public subnet in AWS and is independent of naming conventions.
    """
    meta_data = tfdata.get("meta_data", {})
    original_metadata = tfdata.get("original_metadata", {})
    all_keys = set(meta_data) | set(original_metadata)

    def _merge(node: str) -> Dict[str, Any]:
        return {**original_metadata.get(node, {}), **meta_data.get(node, {})}

    # route_table_id → is_public?
    public_rt_ids: set = set()
    for node in all_keys:
        if "aws_route_table.this" not in helpers.get_no_module_name(
            node
        ) and not helpers.get_no_module_name(node).startswith("aws_route_table."):
            continue
        if "association" in node:
            continue
        m = _merge(node)
        rt_id = m.get("id")
        routes = m.get("route") or []
        if not isinstance(routes, list) or not isinstance(rt_id, str):
            continue
        for route in routes:
            if not isinstance(route, dict):
                continue
            dest = route.get("cidr_block") or route.get("destination_cidr_block")
            gw = route.get("gateway_id") or ""
            if dest == "0.0.0.0/0" and isinstance(gw, str) and gw.startswith("igw-"):
                public_rt_ids.add(rt_id)
                break

    # Also check standalone aws_route resources (when not inlined on the RT)
    for node in all_keys:
        if "aws_route." not in node or "table" in node:
            continue
        m = _merge(node)
        if (
            m.get("destination_cidr_block") == "0.0.0.0/0"
            and isinstance(m.get("gateway_id"), str)
            and m.get("gateway_id", "").startswith("igw-")
        ):
            rt_id = m.get("route_table_id")
            if isinstance(rt_id, str):
                public_rt_ids.add(rt_id)

    if not public_rt_ids:
        return set()

    # subnet_id → public? via RTAs pointing to any public RT
    public_subnet_ids: set = set()
    for node in all_keys:
        if "aws_route_table_association" not in helpers.get_no_module_name(node):
            continue
        m = _merge(node)
        if m.get("route_table_id") in public_rt_ids:
            sid = m.get("subnet_id")
            if isinstance(sid, str):
                public_subnet_ids.add(sid)

    return public_subnet_ids


def _is_public_subnet(
    meta: Dict[str, Any], module_key: str = "", public_subnet_ids: set = None
) -> bool:
    """Return True when a subnet is intended for public-facing workloads.

    Priority:
      1. Route-table analysis: subnet is associated with an RT that has a
         ``0.0.0.0/0`` route to an IGW (authoritative).
      2. ``map_public_ip_on_launch == True``.
      3. ``tags.tier`` in {"pub", "public"}.
      4. ``tags.Name`` containing "-pub" / "public".
      5. ``module_key`` (for_each key) starting with "pub".
    """
    if public_subnet_ids is not None and meta.get("id") in public_subnet_ids:
        return True
    if meta.get("map_public_ip_on_launch") is True:
        return True
    tags = meta.get("tags") or {}
    if isinstance(tags, dict):
        tier = str(tags.get("tier", "")).lower()
        if tier in ("pub", "public"):
            return True
        name = str(tags.get("Name", "")).lower()
        if "-pub" in name or "public" in name:
            return True
    if module_key and module_key.lower().startswith(("pub", "public")):
        return True
    return False


def _subnet_module_key(subnet_node: str) -> str:
    """Extract the for_each key from a subnet node name, e.g. ``pvt-1``."""
    match = re.search(r'\["([^"]+)"\]', subnet_node)
    return match.group(1) if match else ""


def place_regional_nat_gateways(tfdata: Dict[str, Any]) -> None:
    """Place regional (multi-AZ) NAT gateways into public subnets per AZ.

    Classic NAT gateways declare a single ``subnet_id`` and are handled by
    ``split_nat_gateways``. The regional variant
    (``availability_mode = "regional"``) has ``subnet_id = null`` and lists
    per-AZ ENIs under ``regional_nat_gateway_address``. We create one
    numbered NAT instance per AZ entry and drop each into a public subnet
    within that AZ.
    """
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})
    original_metadata = tfdata.get("original_metadata", {})

    def _get(node: str, key: str) -> Any:
        val = original_metadata.get(node, {}).get(key)
        if val in (None, "", []):
            val = meta_data.get(node, {}).get(key)
        return val

    nat_nodes = [n for n in graphdict if "aws_nat_gateway" in n and "~" not in n]
    if not nat_nodes:
        return

    public_subnet_ids = _collect_public_subnet_ids(tfdata)

    # Group subnets by availability_zone_id for lookup
    subnets_by_az: Dict[str, List[str]] = {}
    for node in graphdict:
        if not helpers.get_no_module_name(node).startswith("aws_subnet."):
            continue
        m = {**original_metadata.get(node, {}), **meta_data.get(node, {})}
        az_id = m.get("availability_zone_id") or ""
        if isinstance(az_id, str) and az_id:
            subnets_by_az.setdefault(az_id, []).append(node)

    for nat in nat_nodes:
        mode = _get(nat, "availability_mode")
        if mode != "regional":
            continue
        addresses = _get(nat, "regional_nat_gateway_address") or []
        if not isinstance(addresses, list) or not addresses:
            continue

        original_children = list(graphdict.get(nat, []))
        for i, entry in enumerate(addresses, start=1):
            if not isinstance(entry, dict):
                continue
            az_id = entry.get("availability_zone_id")
            if not isinstance(az_id, str):
                continue
            az_subnets = subnets_by_az.get(az_id, [])
            # Pick the first public subnet in this AZ
            target_subnet = None
            for sn in az_subnets:
                sn_meta = {
                    **original_metadata.get(sn, {}),
                    **meta_data.get(sn, {}),
                }
                if _is_public_subnet(
                    sn_meta, _subnet_module_key(sn), public_subnet_ids
                ):
                    target_subnet = sn
                    break
            if not target_subnet:
                continue
            numbered_nat = f"{nat}~{i}"
            graphdict[numbered_nat] = list(original_children)
            meta_data[numbered_nat] = copy.deepcopy(meta_data.get(nat, {}))
            if nat in original_metadata:
                original_metadata[numbered_nat] = copy.deepcopy(original_metadata[nat])
            if numbered_nat not in graphdict[target_subnet]:
                graphdict[target_subnet].append(numbered_nat)

        # Redirect parent references on the original NAT to the numbered copies
        numbered = [f"{nat}~{i}" for i in range(1, len(addresses) + 1)]
        numbered = [n for n in numbered if n in graphdict]
        if not numbered:
            continue
        for parent, kids in graphdict.items():
            if nat in kids:
                kids.remove(nat)
                for nn in numbered:
                    if nn not in kids:
                        kids.append(nn)
        helpers.delete_node(
            tfdata, nat, remove_from_connections=False, delete_meta_data=False
        )


def link_lb_to_ecs_services(tfdata: Dict[str, Any]) -> None:
    """Add LB → ECS service edges by matching target_group_arn.

    When Terraform plan has resolved ARNs rather than HCL references the
    ``aws_ecs_service.load_balancer[].target_group_arn`` never produces a
    graph edge. Match ARNs on the target group against the ECS service to
    recover the missing connection.
    """
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})
    original_metadata = tfdata.get("original_metadata", {})

    def _get(node: str, key: str) -> Any:
        val = original_metadata.get(node, {}).get(key)
        if val in (None, "", []):
            val = meta_data.get(node, {}).get(key)
        return val

    # ARN → target_group node
    tg_arn_to_node: Dict[str, str] = {}
    for node in set(meta_data) | set(original_metadata):
        if "aws_lb_target_group" not in helpers.get_no_module_name(node):
            continue
        arn = _get(node, "arn")
        if isinstance(arn, str) and arn.startswith("arn:"):
            tg_arn_to_node[arn] = node

    if not tg_arn_to_node:
        return

    # For each ECS service, extract load_balancer[].target_group_arn
    for node in set(meta_data) | set(original_metadata):
        if "aws_ecs_service" not in helpers.get_no_module_name(node):
            continue
        lb_cfg = _get(node, "load_balancer")
        if not isinstance(lb_cfg, list):
            continue
        for entry in lb_cfg:
            if not isinstance(entry, dict):
                continue
            arn = entry.get("target_group_arn")
            tg_node = tg_arn_to_node.get(arn) if isinstance(arn, str) else None
            if not tg_node:
                continue
            # Find the LB this target group belongs to (terraform graph usually links these)
            lb_nodes = [
                n for n, kids in graphdict.items() if tg_node in kids and "aws_lb" in n
            ]
            # Find actual ECS service instances in graphdict (may be consolidated / variant-renamed)
            ecs_instances = [
                n
                for n in graphdict
                if ("aws_fargate" in n or "aws_ec2ecs" in n or "aws_ecs_service" in n)
                and "cluster" not in n
            ]
            sources = lb_nodes or [
                n
                for n in graphdict
                if helpers.get_no_module_name(n).startswith(
                    ("aws_lb.", "aws_alb.", "aws_nlb.")
                )
            ]
            # Prefer variant nodes (aws_alb / aws_nlb) — the parent aws_lb
            # shouldn't connect directly to the ECS service when a variant
            # is present. Traffic flow: ELB → ALB → Fargate.
            variant_sources = [
                s
                for s in sources
                if helpers.get_no_module_name(s).startswith(("aws_alb.", "aws_nlb."))
            ]
            if variant_sources:
                sources = variant_sources

            # When both sides are replicated per-AZ (``src~1/~2``, ``inst~1/~2``)
            # pair them by the AZ of the subnet they live in, not by their
            # ``~N`` suffix — each resource type is numbered independently
            # so matching suffixes don't guarantee matching AZs. Looking up
            # each numbered node's subnet → AZ gives a reliable pairing.
            numbered_sources = [s for s in sources if "~" in s]
            numbered_instances = [i for i in ecs_instances if "~" in i]

            def _az_of(node: str) -> str:
                for parent, kids in graphdict.items():
                    if node not in kids:
                        continue
                    if not helpers.get_no_module_name(parent).startswith("aws_subnet."):
                        continue
                    sn_meta = {
                        **original_metadata.get(parent, {}),
                        **meta_data.get(parent, {}),
                    }
                    az = sn_meta.get("availability_zone_id") or sn_meta.get(
                        "availability_zone"
                    )
                    if isinstance(az, str) and az:
                        return az
                return ""

            if numbered_sources and numbered_instances:
                az_to_instance: Dict[str, str] = {}
                for inst in numbered_instances:
                    az = _az_of(inst)
                    if az:
                        az_to_instance.setdefault(az, inst)
                for src in numbered_sources:
                    az = _az_of(src)
                    match = az_to_instance.get(az) if az else None
                    if match and match not in graphdict.get(src, []):
                        graphdict.setdefault(src, []).append(match)
            else:
                for src in sources:
                    for inst in ecs_instances:
                        if inst not in graphdict.get(src, []):
                            graphdict.setdefault(src, []).append(inst)


def _dedupe_placeholder_nodes(tfdata: Dict[str, Any]) -> None:
    """Remove empty generic placeholder nodes when real module-scoped nodes exist.

    ``IMPLIED_CONNECTIONS`` and some handlers create generic nodes like
    ``aws_ecr_repository.ecr`` for diagram clarity. When the user's stack
    actually declares multiple real ECR repositories the generic node shows
    up as a confusing duplicate. Drop it when real siblings exist and it has
    no children of its own.
    """
    graphdict = tfdata.get("graphdict", {})
    # Patterns where a single generic placeholder is commonly injected
    candidate_prefixes = ("aws_ecr_repository.",)

    for node in list(graphdict.keys()):
        no_mod = helpers.get_no_module_name(node)
        if not any(no_mod.startswith(p) for p in candidate_prefixes):
            continue
        if "module." in node:
            continue  # Only target the generic (module-less) node
        if graphdict.get(node):
            continue  # Has children - not a pure placeholder
        res_type = no_mod.split(".")[0]
        real_siblings = [
            n
            for n in graphdict
            if n != node and helpers.get_no_module_name(n).startswith(res_type + ".")
        ]
        if not real_siblings:
            continue
        # Redirect any parent edges pointing at the placeholder to the real siblings
        for parent, kids in graphdict.items():
            if node in kids:
                kids.remove(node)
                for sib in real_siblings:
                    if sib not in kids:
                        kids.append(sib)
        helpers.delete_node(
            tfdata, node, remove_from_connections=False, delete_meta_data=True
        )


def _collect_subnet_ids_from_meta(meta: Dict[str, Any]) -> List[str]:
    """Collect all subnet ID references from a resource's metadata.

    Inspects common Terraform fields that reference subnets:
    ``subnet_id``, ``subnets``, ``subnet_ids``, and
    ``network_configuration[0].subnets`` (ECS services, Fargate).

    Returns a list of subnet-id strings (e.g. ``subnet-0abc...``).
    """
    ids: List[str] = []
    sid = meta.get("subnet_id")
    if isinstance(sid, str) and sid:
        ids.append(sid)
    for key in ("subnets", "subnet_ids"):
        val = meta.get(key)
        if isinstance(val, list):
            ids.extend(s for s in val if isinstance(s, str) and s.startswith("subnet-"))
    # ECS service network_configuration is a list-of-dicts in plan output
    nc = meta.get("network_configuration")
    if isinstance(nc, list):
        for block in nc:
            if isinstance(block, dict):
                sublist = block.get("subnets", [])
                if isinstance(sublist, list):
                    ids.extend(
                        s
                        for s in sublist
                        if isinstance(s, str) and s.startswith("subnet-")
                    )
    # aws_lb / aws_nlb can declare subnets via subnet_mapping blocks
    sub_mapping = meta.get("subnet_mapping")
    if isinstance(sub_mapping, list):
        for entry in sub_mapping:
            if isinstance(entry, dict):
                sid = entry.get("subnet_id")
                if isinstance(sid, str) and sid.startswith("subnet-"):
                    ids.append(sid)
    return ids


def place_resources_in_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Place managed resources into the subnets their metadata references.

    Many Terraform resources (EC2 instances, ECS services, RDS) record the
    subnet they live in via ``subnet_id``/``subnets``/``subnet_ids`` fields.
    When the plan contains resolved AWS IDs (not HCL references), the
    standard terraform-graph edges don't link them to subnet nodes, so they
    end up floating at the top level. This function matches those IDs
    against known subnet nodes and adds containment edges.

    Numbered resource instances (``foo~1``, ``foo~2``) are distributed
    round-robin across matching subnets so each instance lands in a
    distinct AZ/subnet.
    """
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})
    original_metadata = tfdata.get("original_metadata", {})

    def _meta(node: str) -> Dict[str, Any]:
        """Return merged metadata, preferring original_metadata values.

        Variable resolution sometimes nulls resolved attributes (e.g. when a
        ``local`` cannot be evaluated). ``original_metadata`` preserves the
        raw plan values, which is what we need for subnet-ID matching.
        """
        merged: Dict[str, Any] = {}
        md = meta_data.get(node, {}) or {}
        om = original_metadata.get(node, {}) or {}
        for key in (
            "id",
            "subnet_id",
            "subnets",
            "subnet_ids",
            "network_configuration",
            "db_subnet_group_name",
            "name",
            "vpc_id",
        ):
            val = om.get(key)
            if val in (None, "", []):
                val = md.get(key)
            if val not in (None, "", []):
                merged[key] = val
        return merged

    # Build subnet_id → subnet node lookup
    subnet_id_map: Dict[str, str] = {}
    for node in graphdict:
        if not helpers.get_no_module_name(node).startswith("aws_subnet."):
            continue
        sid = _meta(node).get("id", "")
        if isinstance(sid, str) and sid:
            subnet_id_map[sid] = node

    if not subnet_id_map:
        return tfdata

    # Build db_subnet_group_name → [subnet_ids] lookup (RDS uses the group name)
    db_group_subnet_ids: Dict[str, List[str]] = {}
    all_nodes = set(meta_data.keys()) | set(original_metadata.keys())
    for node in all_nodes:
        if "aws_db_subnet_group" not in helpers.get_no_module_name(node):
            continue
        m = _meta(node)
        name = m.get("name")
        sids = m.get("subnet_ids", [])
        if isinstance(name, str) and isinstance(sids, list):
            db_group_subnet_ids[name] = [s for s in sids if isinstance(s, str)]

    # Group numbered instances so we can distribute them across subnets
    base_to_instances: Dict[str, List[str]] = {}
    for node in list(graphdict.keys()):
        no_mod = helpers.get_no_module_name(node)
        # Skip subnets themselves and structural nodes
        if no_mod.startswith("aws_subnet.") or no_mod.startswith("aws_vpc."):
            continue
        if no_mod.startswith(("aws_az.", "tv_blank.", "aws_group.")):
            continue
        base = node.split("~")[0] if "~" in node else node
        base_to_instances.setdefault(base, []).append(node)

    def _add_subnet_edge(subnet_node: str, child: str) -> None:
        children = graphdict.setdefault(subnet_node, [])
        if child not in children:
            children.append(child)

    # Reverse lookup for variants (e.g. aws_fargate → aws_ecs_service)
    variant_to_original: Dict[str, str] = {}
    for original_type, variants in cloud_config.AWS_NODE_VARIANTS.items():
        for variant_name in variants.values():
            variant_to_original[variant_name] = original_type

    def _meta_with_fallback(base: str, instances: List[str]) -> Dict[str, Any]:
        """Look up metadata, falling back to variant or consolidation source nodes.

        Consolidated/variant renames can detach subnet metadata from the
        current graph node. When the direct lookup is empty we scan the
        full metadata map for entries whose resource type matches the
        original (pre-variant) type.
        """
        direct = _meta(base) or _meta(instances[0])
        ids = _collect_subnet_ids_from_meta(direct)
        if ids or direct.get("db_subnet_group_name"):
            return direct

        base_type = helpers.get_no_module_name(base).split(".")[0]
        candidate_types = {base_type}
        if base_type in variant_to_original:
            candidate_types.add(variant_to_original[base_type])

        for node_key in set(meta_data.keys()) | set(original_metadata.keys()):
            node_type = helpers.get_no_module_name(node_key).split(".")[0]
            if node_type not in candidate_types:
                continue
            m = _meta(node_key)
            if _collect_subnet_ids_from_meta(m) or m.get("db_subnet_group_name"):
                return m
        return direct

    for base, instances in base_to_instances.items():
        meta = _meta_with_fallback(base, instances)
        candidate_ids = _collect_subnet_ids_from_meta(meta)

        # RDS and similar reference a db_subnet_group by name rather than id
        if not candidate_ids:
            group_name = meta.get("db_subnet_group_name")
            if isinstance(group_name, str) and group_name in db_group_subnet_ids:
                candidate_ids = db_group_subnet_ids[group_name]

        if not candidate_ids:
            continue

        matching_subnets: List[str] = []
        seen: set = set()
        for sid in candidate_ids:
            sn = subnet_id_map.get(sid)
            if sn and sn not in seen:
                matching_subnets.append(sn)
                seen.add(sn)

        if not matching_subnets:
            continue

        # Load balancers logically span multiple subnets; expand a single
        # base node into numbered copies so each subnet gets its own icon.
        # When the variant form (aws_alb / aws_nlb) exists alongside the
        # generic aws_lb parent, only expand the variant — the aws_lb node
        # stays as a single top-level "ELB" icon pointing down at the
        # per-subnet variant copies.
        base_type = helpers.get_no_module_name(base).split(".")[0]
        is_lb = base_type in ("aws_lb", "aws_alb", "aws_nlb")
        base_instance = helpers.get_no_module_name(base).split(".", 1)[-1]
        variant_exists = base_type == "aws_lb" and any(
            helpers.get_no_module_name(n).startswith(
                (f"aws_alb.{base_instance}", f"aws_nlb.{base_instance}")
            )
            for n in graphdict
        )
        # If a variant (aws_alb/aws_nlb) exists, the base aws_lb is the
        # top-level "ELB Service" icon — it stays outside any subnet.
        if is_lb and variant_exists:
            continue
        if (
            is_lb
            and not variant_exists
            and len(instances) == 1
            and len(matching_subnets) > 1
        ):
            original = instances[0]
            original_children = list(graphdict.get(original, []))
            for i, subnet in enumerate(matching_subnets, start=1):
                numbered = f"{original}~{i}"
                if numbered not in graphdict:
                    graphdict[numbered] = list(original_children)
                    meta_data[numbered] = copy.deepcopy(meta_data.get(original, {}))
                    if original in original_metadata:
                        original_metadata[numbered] = copy.deepcopy(
                            original_metadata[original]
                        )
                _add_subnet_edge(subnet, numbered)
            # Redirect parent references on the original LB to the numbered copies
            numbered_nodes = [
                f"{original}~{i}" for i in range(1, len(matching_subnets) + 1)
            ]
            for parent, kids in graphdict.items():
                if original in kids and parent not in matching_subnets:
                    kids.remove(original)
                    for nn in numbered_nodes:
                        if nn not in kids:
                            kids.append(nn)
            helpers.delete_node(
                tfdata,
                original,
                remove_from_connections=False,
                delete_meta_data=False,
            )
            continue

        # Distribute instances round-robin across matching subnets
        instances_sorted = sorted(instances)
        for i, inst in enumerate(instances_sorted):
            target = matching_subnets[i % len(matching_subnets)]
            _add_subnet_edge(target, inst)

    # Ensure VPC → AZ edges exist so subnets render inside the VPC
    _link_vpcs_to_az_nodes(tfdata, subnet_id_map, _meta)
    return tfdata


def _link_vpcs_to_az_nodes(
    tfdata: Dict[str, Any],
    subnet_id_map: Dict[str, str],
    meta_lookup,
) -> None:
    """Add VPC → AZ edges based on each subnet's vpc_id metadata.

    The ``insert_intermediate_node`` subnet handler only wires AZ nodes when
    a VPC→subnet edge already exists. When dependencies flow through
    unresolved locals the terraform-graph skips that edge, leaving AZ nodes
    (and therefore subnets) orphaned. Match subnets' ``vpc_id`` against VPC
    nodes' ``id`` to reconstruct the containment edge.
    """
    graphdict = tfdata.get("graphdict", {})

    vpc_id_to_node: Dict[str, str] = {}
    for node in graphdict:
        if not helpers.get_no_module_name(node).startswith("aws_vpc."):
            continue
        vpc_id = meta_lookup(node).get("id", "")
        if isinstance(vpc_id, str) and vpc_id:
            vpc_id_to_node[vpc_id] = node

    if not vpc_id_to_node:
        return

    # For each AZ node, find its subnets' vpc_id and add VPC → AZ edge
    for az_node, subnets in list(graphdict.items()):
        if not helpers.get_no_module_name(az_node).startswith("aws_az."):
            continue
        for subnet in subnets:
            if not helpers.get_no_module_name(subnet).startswith("aws_subnet."):
                continue
            vpc_id = meta_lookup(subnet).get("vpc_id", "")
            vpc_node = vpc_id_to_node.get(vpc_id)
            if vpc_node and az_node not in graphdict.get(vpc_node, []):
                graphdict.setdefault(vpc_node, []).append(az_node)
                break


def _remove_redundant_blanks(graphdict: Dict[str, List[str]]) -> None:
    """Drop tv_blank placeholders from subnets that gained real children.

    Blank nodes exist solely to force graphviz to render empty group
    clusters. Once a subnet has a real child the placeholder is redundant
    and any orphaned blank node (no remaining parent) is deleted outright
    to keep it out of the graph export.
    """
    for node, children in graphdict.items():
        no_mod = helpers.get_no_module_name(node)
        if not no_mod.startswith("aws_subnet."):
            continue
        has_real_child = any(
            not helpers.get_no_module_name(c).startswith("tv_blank.") for c in children
        )
        if has_real_child:
            graphdict[node] = [
                c
                for c in children
                if not helpers.get_no_module_name(c).startswith("tv_blank.")
            ]

    # Drop any blank nodes no longer referenced by any parent
    referenced = set()
    for children in graphdict.values():
        for c in children:
            if helpers.get_no_module_name(c).startswith("tv_blank."):
                referenced.add(c)
    for node in list(graphdict.keys()):
        if (
            helpers.get_no_module_name(node).startswith("tv_blank.")
            and node not in referenced
        ):
            del graphdict[node]


def _fill_empty_groups_with_space(
    graphdict: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """Connect orphaned group nodes to blank nodes.

    Args:
        graphdict: Resource graph dictionary

    Returns:
        Updated graphdict with orphaned group nodes connected to blank nodes
    """
    counter = 1

    for resource in list(graphdict.keys()):
        # Check if resource starts with any GROUP_NODES prefix
        resource_type = helpers.get_no_module_name(resource).split(".")[0]
        if resource_type == "aws_subnet" or resource_type == "aws_vpc":
            # Check if resource has any outgoing connections
            if not graphdict.get(resource):
                # Always use a unique counter to avoid shared blank nodes
                # across multiple VPCs/subnets (causes overlapping clusters)
                blank_node = f"tv_blank.empty~{counter}"
                counter += 1
                graphdict[resource] = [blank_node]
                # Ensure blank node exists in graph
                if blank_node not in graphdict:
                    graphdict[blank_node] = []

    return graphdict


def _remove_consolidated_subnet_refs(
    graphdict: Dict[str, List[str]],
) -> Dict[str, List[str]]:
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
    nat_gateways = sorted(
        [k for k in terraform_data.keys() if "aws_nat_gateway" in k and "~" not in k]
    )

    for nat_gw in nat_gateways:
        # Find public subnets that reference this NAT gateway
        subnet_suffixes = set()
        for resource, deps in sorted(terraform_data.items()):
            if "public_subnets" in resource and "~" in resource:
                match = re.search(suffix_pattern, resource)
                if match and nat_gw in deps:
                    subnet_suffixes.add(match.group(1))

        # Create numbered NAT gateways
        for suffix in sorted(subnet_suffixes):
            nat_gw_numbered = f"{nat_gw}~{suffix}"
            result[nat_gw_numbered] = list(terraform_data[nat_gw])

        # Remove original NAT gateway if we created numbered ones
        if subnet_suffixes:
            del result[nat_gw]

    # Update subnet references to use numbered NAT gateways
    for resource in sorted(result.keys()):
        deps = result[resource]
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
    for resource, deps in sorted(terraform_data.items()):
        if "aws_iam_role" in resource:
            for dep in deps:
                if "aws_iam_instance_profile" in dep:
                    profile_to_role[dep] = resource

    # Find instance profiles that connect to EC2 instances and add EC2 to IAM role deps
    for resource, deps in sorted(terraform_data.items()):
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
    for resource, deps in sorted(terraform_data.items()):
        if "aws_sqs_queue" in resource:
            for dep in deps:
                if "aws_sqs_queue_policy" in dep:
                    policy_to_queue[dep] = resource

    # Find queue policies that connect to resources and add SQS queue to those resource deps
    for resource, deps in sorted(terraform_data.items()):
        for dep in deps:
            if "aws_sqs_queue_policy." in dep and dep in policy_to_queue:
                sqs_queue = policy_to_queue[dep]
                if sqs_queue not in result[resource]:
                    result[resource].append(sqs_queue)
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
    for key in sorted(terraform_data.keys()):
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
    for base_name in sorted(subnet_groups.keys()):
        group_data = subnet_groups[base_name]
        for subnet in group_data["subnets"]:
            # Extract subnet suffix
            subnet_match = re.search(suffix_pattern, subnet)
            if subnet_match:
                subnet_suffix = subnet_match.group(1)
                # Add all SGs with matching suffix
                for sg_base in sorted(group_data["sg_bases"]):
                    sg_with_suffix = f"{sg_base}~{subnet_suffix}"
                    if (
                        sg_with_suffix in terraform_data
                        and sg_with_suffix not in result[subnet]
                    ):
                        result[subnet].append(sg_with_suffix)

    return result


def aws_handle_waf_associations(tfdata: dict) -> dict:
    """Handle WAF WebACL associations to protected resources.

    Parses aws_wafv2_web_acl_association (and aws_waf_web_acl_association for Classic WAF)
    to create connections from WAF WebACLs to protected resources (ALB, CloudFront, API Gateway).

    The association resource references:
    - web_acl_arn: Terraform reference to WAF WebACL (e.g., "${aws_wafv2_web_acl.alb.arn}")
    - resource_arn: Terraform reference to protected resource (e.g., "${aws_lb.main.arn}")

    Note: ARNs are computed values (show as "true" in meta_data), so we parse from all_resource.

    Args:
        tfdata: TerraVision data structure containing graphdict, all_resource, meta_data

    Returns:
        Updated tfdata with WAF → protected resource connections

    Constitutional Compliance:
    - CO-005.1: Handler justified - association doesn't create Terraform dependencies
    - Baseline validation showed WAF → ALB connection missing despite association existing
    """
    import re
    from modules.helpers import append_dictlist

    graphdict = tfdata.get("graphdict", {})
    all_resource = tfdata.get("all_resource", {})

    # Iterate through all Terraform files to find WAF associations
    for _tf_file, resources in all_resource.items():
        if not isinstance(resources, list):
            continue

        for resource_block in resources:
            # Check if this is a WAF association resource
            if "aws_wafv2_web_acl_association" in resource_block:
                association_data = resource_block["aws_wafv2_web_acl_association"]
            elif "aws_waf_web_acl_association" in resource_block:
                association_data = resource_block["aws_waf_web_acl_association"]
            else:
                continue

            # Process each association instance
            for _instance_name, instance_data in association_data.items():
                web_acl_arn_ref = instance_data.get("web_acl_arn", "")
                resource_arn_ref = instance_data.get("resource_arn", "")

                if not web_acl_arn_ref or not resource_arn_ref:
                    continue

                # Extract resource references from Terraform interpolations
                # Format: "${aws_wafv2_web_acl.alb.arn}" or "${aws_lb.main.arn}"
                waf_match = re.search(
                    r"\$\{(aws_wafv2_web_acl\.\w+|aws_waf_web_acl\.\w+)",
                    web_acl_arn_ref,
                )
                resource_match = re.search(
                    r"\$\{(aws_lb\.\w+|aws_cloudfront_distribution\.\w+|aws_api_gateway_rest_api\.\w+)",
                    resource_arn_ref,
                )

                if not waf_match or not resource_match:
                    continue

                # Note: waf_ref would be "aws_wafv2_web_acl.alb", but we search for consolidated node instead
                protected_ref = resource_match.group(1)  # e.g., "aws_lb.main"

                # Find the consolidated WAF resource in graphdict
                # WAF consolidation creates "aws_wafv2_web_acl.waf" or "aws_waf_web_acl.waf"
                waf_resource = None
                for key in graphdict.keys():
                    if "aws_wafv2_web_acl.waf" in key or "aws_waf_web_acl.waf" in key:
                        waf_resource = key
                        break

                # Find the protected resource in graphdict
                # Note: ALB is consolidated to "aws_lb.elb" (service node)
                # We connect to the consolidation node, NOT numbered instances
                protected_resource = None
                for key in graphdict.keys():
                    if "aws_lb" in protected_ref:
                        # Look for LB consolidation node (aws_lb.elb) WITHOUT numbered suffix
                        if key == "aws_lb.elb":
                            protected_resource = key
                            break
                    elif "aws_cloudfront_distribution" in protected_ref:
                        if "aws_cloudfront_distribution" in key and "~" not in key:
                            protected_resource = key
                            break
                    elif "aws_api_gateway_rest_api" in protected_ref:
                        # API Gateway consolidates to aws_api_gateway_integration.gateway
                        if (
                            "aws_api_gateway" in key
                            and "gateway" in key
                            and "~" not in key
                        ):
                            protected_resource = key
                            break

                # Create WAF → protected resource connection
                if waf_resource and protected_resource:
                    # Get existing connections for WAF
                    waf_connections = graphdict.get(waf_resource, [])
                    # Append protected resource if not already connected
                    waf_connections = append_dictlist(
                        waf_connections, protected_resource
                    )
                    # Update graphdict
                    graphdict[waf_resource] = waf_connections

                    # IMPORTANT: Remove any reverse connections (protected resource → WAF)
                    # These come from Terraform dependencies but should not be in the graph
                    # We only want WAF → protected resource (WAF protects resources)
                    for key in list(graphdict.keys()):
                        if waf_resource in graphdict.get(key, []):
                            if waf_resource in graphdict[key]:
                                graphdict[key].remove(waf_resource)

    tfdata["graphdict"] = graphdict
    return tfdata


def aws_handle_s3_cross_region_grouping(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group S3 buckets by region for cross-region replication scenarios.

    Creates tv_aws_region.<region> nodes and moves S3 buckets into their respective
    regions based on provider alias configuration.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with regional grouping for S3 buckets
    """
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})
    all_provider = tfdata.get("all_provider", {})
    all_resource = tfdata.get("all_resource", {})

    # Build provider alias -> region mapping
    provider_region_map = {}
    for filepath, provider_list in all_provider.items():
        for provider_block in provider_list:
            for provider_type, provider_config in provider_block.items():
                if provider_type == "aws" and isinstance(provider_config, dict):
                    region = provider_config.get("region")
                    alias = provider_config.get("alias")
                    if region and alias:
                        provider_region_map[alias] = region

    # If no provider mappings found, skip regional grouping
    if not provider_region_map:
        return tfdata

    # Track which buckets belong to which regions
    bucket_region_map = {}

    # Find S3 buckets and their provider aliases
    for filepath, resource_list in all_resource.items():
        for resource_dict in resource_list:
            if "aws_s3_bucket" in resource_dict:
                for bucket_name, bucket_config in resource_dict[
                    "aws_s3_bucket"
                ].items():
                    if isinstance(bucket_config, dict):
                        provider_ref = bucket_config.get("provider", "")
                        # Extract alias from provider reference like "${aws.primary}"
                        if provider_ref:
                            # Remove ${} and extract alias (e.g., "aws.primary" -> "primary")
                            clean_ref = provider_ref.replace("${", "").replace("}", "")
                            if "." in clean_ref:
                                alias = clean_ref.split(".", 1)[1]
                                region = provider_region_map.get(alias)
                                if region:
                                    bucket_resource_name = (
                                        f"aws_s3_bucket.{bucket_name}"
                                    )
                                    bucket_region_map[bucket_resource_name] = region

    # If multiple regions detected, create regional grouping
    unique_regions = set(bucket_region_map.values())
    if len(unique_regions) > 1:
        # Create tv_aws_region nodes for each region
        for region in unique_regions:
            region_node = f"tv_aws_region.{region}"
            if region_node not in graphdict:
                graphdict[region_node] = []
                meta_data[region_node] = {"region": region}

        # Move S3 buckets (and related versioning resources) into their regions
        for bucket_name, region in bucket_region_map.items():
            region_node = f"tv_aws_region.{region}"

            # Add bucket to region node's children
            if bucket_name in graphdict and bucket_name not in graphdict[region_node]:
                graphdict[region_node].append(bucket_name)

            # Also move versioning resources to the same region
            versioning_resource = bucket_name.replace(
                "aws_s3_bucket.", "aws_s3_bucket_versioning."
            )
            if (
                versioning_resource in graphdict
                and versioning_resource not in graphdict[region_node]
            ):
                graphdict[region_node].append(versioning_resource)

        # Create direct source → destination bucket connections for replication
        for filepath, resource_list in all_resource.items():
            for resource_dict in resource_list:
                if "aws_s3_bucket_replication_configuration" in resource_dict:
                    for repl_name, repl_config in resource_dict[
                        "aws_s3_bucket_replication_configuration"
                    ].items():
                        if isinstance(repl_config, dict):
                            # Extract source bucket reference (e.g., "${aws_s3_bucket.source.id}")
                            source_ref = repl_config.get("bucket", "")
                            source_bucket = None
                            if "${" in source_ref and "}" in source_ref:
                                # Parse "${aws_s3_bucket.source.id}" -> "aws_s3_bucket.source"
                                ref_content = source_ref.replace("${", "").replace(
                                    "}", ""
                                )
                                if ".id" in ref_content or ".bucket" in ref_content:
                                    source_bucket = ref_content.rsplit(".", 1)[0]
                                else:
                                    source_bucket = ref_content

                            # Extract destination bucket from rule configuration
                            destination_bucket = None
                            rules = repl_config.get("rule", [])
                            if rules and len(rules) > 0:
                                rule = rules[0]
                                if isinstance(rule, dict):
                                    dest_list = rule.get("destination", [])
                                    # destination is an array of dicts
                                    if (
                                        isinstance(dest_list, list)
                                        and len(dest_list) > 0
                                    ):
                                        dest_config = dest_list[0]
                                        if isinstance(dest_config, dict):
                                            dest_ref = dest_config.get("bucket", "")
                                            if "${" in dest_ref and "}" in dest_ref:
                                                # Parse "${aws_s3_bucket.destination.arn}" -> "aws_s3_bucket.destination"
                                                ref_content = dest_ref.replace(
                                                    "${", ""
                                                ).replace("}", "")
                                                if (
                                                    ".arn" in ref_content
                                                    or ".bucket" in ref_content
                                                ):
                                                    destination_bucket = (
                                                        ref_content.rsplit(".", 1)[0]
                                                    )
                                                else:
                                                    destination_bucket = ref_content

                            # Create direct source → destination connection
                            if source_bucket and destination_bucket:
                                if (
                                    source_bucket in graphdict
                                    and destination_bucket
                                    not in graphdict.get(source_bucket, [])
                                ):
                                    graphdict[source_bucket].append(destination_bucket)

    tfdata["graphdict"] = graphdict
    tfdata["meta_data"] = meta_data
    return tfdata
