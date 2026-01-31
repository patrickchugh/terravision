"""Generic resource transformation operations for AWS architecture diagrams.

Provides reusable building blocks for mutating tfdata['graphdict'] to create
professional AWS architecture diagrams. Each transformer is a pure function
that can be composed via configuration.
"""

from typing import Dict, List, Any, Callable, Optional
import copy
import re
import modules.helpers as helpers


def expand_to_numbered_instances(
    tfdata: Dict[str, Any],
    resource_pattern: str,
    subnet_key: str = "subnet_ids",
    skip_if_numbered: bool = True,
    inherit_connections: bool = True,
) -> Dict[str, Any]:
    """Expand single resource into numbered instances (~1, ~2, ~3) per subnet.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources (e.g., "aws_eks_node_group")
        subnet_key: Metadata key containing subnet references
        skip_if_numbered: Skip resources already containing ~
        inherit_connections: If True, numbered instances inherit base resource connections.
                            If False, numbered instances start with empty connections.
                            Use False for visual-only resources (ElastiCache multi-AZ),
                            True for actual instances (EKS nodes, ASG instances).

    Returns:
        Updated tfdata with numbered instances
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_subnet")

    for resource in list(resources):
        if skip_if_numbered and "~" in resource:
            continue

        # Get subnet references from metadata
        subnet_ids = tfdata["meta_data"].get(resource, {}).get(subnet_key, [])
        if isinstance(subnet_ids, str):
            subnet_ids = [subnet_ids]

        # Find matching subnets
        matching_subnets = []
        for subnet in subnets:
            subnet_id = tfdata["meta_data"].get(subnet, {}).get("id", "")
            if any(subnet_id in str(sid) for sid in subnet_ids):
                matching_subnets.append(subnet)

        matching_subnets = sorted(matching_subnets)

        # Create numbered instances if multiple subnets
        if len(matching_subnets) > 1:
            for i, subnet in enumerate(matching_subnets, start=1):
                numbered = f"{resource}~{i}"
                # Inherit connections based on parameter
                if inherit_connections:
                    tfdata["graphdict"][numbered] = list(
                        tfdata["graphdict"].get(resource, [])
                    )
                else:
                    # Visual-only instances start with empty connections
                    tfdata["graphdict"][numbered] = []
                tfdata["meta_data"][numbered] = copy.deepcopy(
                    tfdata["meta_data"].get(resource, {})
                )

                # Add to subnet
                if numbered not in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].append(numbered)

                # Remove unnumbered from subnet
                if resource in tfdata["graphdict"][subnet]:
                    tfdata["graphdict"][subnet].remove(resource)

            # Delete original
            tfdata["graphdict"].pop(resource, None)
            tfdata["meta_data"].pop(resource, None)

        elif len(matching_subnets) == 1:
            # Single subnet - add if not present
            if resource not in tfdata["graphdict"][matching_subnets[0]]:
                tfdata["graphdict"][matching_subnets[0]].append(resource)

    # Cleanup: Ensure each subnet only contains numbered instances assigned to it
    # This prevents overlapping connections where subnet_a contains both resource~1 and resource~2
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_subnet")
    for subnet_idx, subnet in enumerate(sorted(subnets), start=1):
        subnet_connections = tfdata["graphdict"].get(subnet, [])[:]

        for connection in subnet_connections:
            # Check if this is a numbered instance
            match = re.search(r"(.+)~(\d+)$", connection)
            if match:
                base_resource = match.group(1)
                instance_num = int(match.group(2))

                # If this numbered instance doesn't match the subnet's position, remove it
                if instance_num != subnet_idx:
                    tfdata["graphdict"][subnet].remove(connection)

    return tfdata


def apply_resource_variants(
    tfdata: Dict[str, Any],
    resource_pattern: str,
    variant_map: Dict[str, str],
    metadata_key: str,
) -> Dict[str, Any]:
    """Apply variants to specific resource type and its connections.

    Replaces resource icons based on metadata and also updates connections.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources
        variant_map: Map of metadata values to new resource types
        metadata_key: Metadata key to check for variant

    Returns:
        Updated tfdata with variants applied
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )

    for resource in list(resources):
        if resource not in tfdata["meta_data"]:
            continue

        node_name = resource.split("~")[0] if "~" in resource else resource
        metadata_value = str(
            tfdata["meta_data"].get(node_name, {}).get(metadata_key, "")
        ).lower()

        # Find matching variant
        new_type = None
        for key, value in variant_map.items():
            if key.lower() in metadata_value:
                new_type = value
                break

        if new_type and resource in tfdata["graphdict"]:
            node_title = helpers.get_no_module_name(resource).split(".")[1]
            renamed = f"{new_type}.{node_title}"

            # Copy connections and metadata
            tfdata["graphdict"][renamed] = list(tfdata["graphdict"][resource])
            tfdata["meta_data"][renamed] = copy.deepcopy(
                tfdata["meta_data"].get(node_name, {})
            )

            # Update parent references
            for parent in helpers.list_of_parents(tfdata["graphdict"], resource):
                if resource in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].remove(resource)
                    if renamed not in tfdata["graphdict"][parent]:
                        tfdata["graphdict"][parent].append(renamed)

            # Delete original
            del tfdata["graphdict"][resource]

    return tfdata


def create_group_node(
    tfdata: Dict[str, Any],
    group_name: str,
    children: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a group/container node with children.

    Args:
        tfdata: Terraform data dictionary
        group_name: Name of group node to create
        children: List of child resource names
        metadata: Optional metadata for group

    Returns:
        Updated tfdata with group node
    """
    if group_name not in tfdata["graphdict"]:
        tfdata["graphdict"][group_name] = []
        tfdata["meta_data"][group_name] = metadata or {}

    for child in children:
        if child not in tfdata["graphdict"][group_name]:
            tfdata["graphdict"][group_name].append(child)

    return tfdata


def move_to_parent(
    tfdata: Dict[str, Any],
    resource_pattern: str,
    from_parent_pattern: str,
    to_parent_pattern: str,
) -> Dict[str, Any]:
    """Move resources from one parent to another.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources to move
        from_parent_pattern: Pattern to match source parent
        to_parent_pattern: Pattern to match destination parent

    Returns:
        Updated tfdata with resources moved
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )
    from_parents = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], from_parent_pattern
    )
    to_parents = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], to_parent_pattern
    )

    if not to_parents:
        return tfdata

    to_parent = to_parents[0]

    for resource in resources:
        for from_parent in from_parents:
            if resource in tfdata["graphdict"].get(from_parent, []):
                tfdata["graphdict"][from_parent].remove(resource)
                if resource not in tfdata["graphdict"][to_parent]:
                    tfdata["graphdict"][to_parent].append(resource)

    return tfdata


def link_resources(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str,
    bidirectional: bool = False,
) -> Dict[str, Any]:
    """Create connections between resources.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        target_pattern: Pattern to match target resources
        bidirectional: Create connections in both directions

    Returns:
        Updated tfdata with new connections
    """
    sources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], source_pattern)
    targets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], target_pattern)

    for source in sources:
        for target in targets:
            if target not in tfdata["graphdict"].get(source, []):
                tfdata["graphdict"][source].append(target)

            if bidirectional and source not in tfdata["graphdict"].get(target, []):
                tfdata["graphdict"][target].append(source)

    return tfdata


def unlink_resources(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str,
) -> Dict[str, Any]:
    """Remove connections between resources.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        target_pattern: Pattern to match target resources

    Returns:
        Updated tfdata with connections removed
    """
    sources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], source_pattern)
    targets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], target_pattern)

    for source in sources:
        for target in targets:
            if target in tfdata["graphdict"].get(source, []):
                tfdata["graphdict"][source].remove(target)

    return tfdata


def delete_nodes(
    tfdata: Dict[str, Any],
    resource_pattern: str,
    remove_from_parents: bool = True,
) -> Dict[str, Any]:
    """Delete nodes from graph.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources to delete
        remove_from_parents: Also remove from parent connections

    Returns:
        Updated tfdata with nodes deleted
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )

    for resource in list(resources):
        if remove_from_parents:
            parents = helpers.list_of_parents(tfdata["graphdict"], resource)
            for parent in parents:
                if resource in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].remove(resource)

        tfdata["graphdict"].pop(resource, None)
        tfdata["meta_data"].pop(resource, None)

    return tfdata


def match_by_suffix(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str,
) -> Dict[str, Any]:
    """Link resources with matching ~N suffixes.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        target_pattern: Pattern to match target resources

    Returns:
        Updated tfdata with suffix-matched connections
    """
    sources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], source_pattern)
    targets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], target_pattern)

    suffix_pattern = r"~(\d+)$"

    for source in sources:
        source_match = re.search(suffix_pattern, source)
        if not source_match:
            continue

        source_suffix = source_match.group(1)

        for target in targets:
            target_match = re.search(suffix_pattern, target)
            if target_match and target_match.group(1) == source_suffix:
                if target not in tfdata["graphdict"].get(source, []):
                    tfdata["graphdict"][source].append(target)

    return tfdata


def redirect_connections(
    tfdata: Dict[str, Any],
    from_resource_pattern: str,
    to_resource_pattern: str,
    parent_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """Redirect connections from one resource to another.

    Args:
        tfdata: Terraform data dictionary
        from_resource_pattern: Pattern to match resources to redirect from
        to_resource_pattern: Pattern to match resources to redirect to
        parent_pattern: Optional pattern to limit which parents are updated

    Returns:
        Updated tfdata with redirected connections
    """
    from_resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], from_resource_pattern
    )
    to_resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], to_resource_pattern
    )

    if not to_resources:
        return tfdata

    to_resource = to_resources[0]

    for from_resource in from_resources:
        parents = helpers.list_of_parents(tfdata["graphdict"], from_resource)

        if parent_pattern:
            parents = [p for p in parents if parent_pattern in p]

        for parent in parents:
            if from_resource in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(from_resource)
                if to_resource not in tfdata["graphdict"][parent]:
                    tfdata["graphdict"][parent].append(to_resource)

    return tfdata


def clone_with_suffix(
    tfdata: Dict[str, Any],
    resource_pattern: str,
    count: int,
) -> Dict[str, Any]:
    """Clone resources with numbered suffixes.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources to clone
        count: Number of clones to create

    Returns:
        Updated tfdata with cloned resources
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )

    for resource in resources:
        if "~" in resource:
            continue

        for i in range(1, count + 1):
            numbered = f"{resource}~{i}"
            tfdata["graphdict"][numbered] = list(tfdata["graphdict"].get(resource, []))
            tfdata["meta_data"][numbered] = copy.deepcopy(
                tfdata["meta_data"].get(resource, {})
            )

        # Delete original
        tfdata["graphdict"].pop(resource, None)
        tfdata["meta_data"].pop(resource, None)

    return tfdata


def apply_all_variants(
    tfdata: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply all resource variants based on NODE_VARIANTS config.

    Replaces handle_variants() function with config-driven approach.
    Handles both node renaming and connection renaming based on metadata.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with all variants applied
    """
    from modules.provider_detector import get_primary_provider_or_default
    from modules.config_loader import load_config

    provider = get_primary_provider_or_default(tfdata)
    config = load_config(provider)

    # Get provider-specific constants
    provider_upper = provider.upper()
    NODE_VARIANTS = getattr(config, f"{provider_upper}_NODE_VARIANTS", {})
    SPECIAL_RESOURCES = getattr(config, f"{provider_upper}_SPECIAL_RESOURCES", {})
    provider_prefixes = config.PROVIDER_PREFIX

    # Process each node
    for node in list(tfdata["graphdict"].keys()):
        node_title = helpers.get_no_module_name(node).split(".")[1]
        node_name = (
            node.split("~")[0] if (node[-1].isdigit() and node[-2] == "~") else node
        )

        # Check if resource belongs to current provider
        resource_name = helpers.get_no_module_name(node_name)
        is_provider_resource = any(
            resource_name.startswith(prefix) for prefix in provider_prefixes
        )

        if not is_provider_resource:
            continue

        # Check for variant
        renamed_node = helpers.check_variant(node, tfdata["meta_data"].get(node_name))

        # Rename node if variant found and not already processed
        if (
            renamed_node
            and helpers.get_no_module_name(node).split(".")[0]
            not in SPECIAL_RESOURCES.keys()
            and node in tfdata["graphdict"]
        ):
            renamed_node = f"{renamed_node}.{node_title}"
            tfdata["graphdict"][renamed_node] = list(tfdata["graphdict"][node])
            tfdata["meta_data"][renamed_node] = copy.deepcopy(
                tfdata["meta_data"].get(node, {})
            )
            del tfdata["graphdict"][node]
            node = renamed_node

        # Process connections
        if node not in tfdata["graphdict"]:
            continue

        shared_group_name = f"{provider}_group.shared_services"

        for resource in list(tfdata["graphdict"][node]):
            connection_resource_name = (
                resource.split("~")[0]
                if ("~" in resource and resource[-1].isdigit() and resource[-2] == "~")
                else resource
            )

            # Check if connection belongs to current provider
            connection_name = helpers.get_no_module_name(connection_resource_name)
            is_provider_connection = any(
                connection_name.startswith(prefix) for prefix in provider_prefixes
            )

            if not is_provider_connection:
                continue

            variant_suffix = helpers.check_variant(
                resource, tfdata["meta_data"].get(connection_resource_name)
            )

            if (
                variant_suffix
                and helpers.get_no_module_name(resource).split(".")[0]
                not in SPECIAL_RESOURCES.keys()
                and not node.startswith(f"{provider}_group.shared")
                and (
                    shared_group_name not in tfdata["graphdict"]
                    or resource not in tfdata["graphdict"].get(shared_group_name, [])
                    or "~" in node
                )
                and resource.split(".")[0] != node.split(".")[0]
            ):
                variant_label = resource.split(".")[1]
                new_variant_name = f"{variant_suffix}.{variant_label}"

                tfdata["graphdict"][node].remove(resource)
                tfdata["graphdict"][node].append(new_variant_name)
                tfdata["meta_data"][new_variant_name] = copy.deepcopy(
                    tfdata["meta_data"].get(resource, {})
                )

    return tfdata


def move_to_vpc_parent(
    tfdata: Dict[str, Any],
    resource_pattern: str,
) -> Dict[str, Any]:
    """Move resources from subnets to VPC parent.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources to move

    Returns:
        Updated tfdata with resources moved to VPC
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )

    for resource in resources:
        parents = helpers.list_of_parents(tfdata["graphdict"], resource)
        subnets = [p for p in parents if "aws_subnet" in p]

        for subnet in subnets:
            if resource in tfdata["graphdict"][subnet]:
                tfdata["graphdict"][subnet].remove(resource)

                # Navigate to VPC through AZ
                az_parents = helpers.list_of_parents(tfdata["graphdict"], subnet)
                for az in az_parents:
                    if "aws_az" in az:
                        vpc_parents = helpers.list_of_parents(tfdata["graphdict"], az)
                        for vpc in vpc_parents:
                            if (
                                "aws_vpc" in vpc
                                and resource not in tfdata["graphdict"][vpc]
                            ):
                                tfdata["graphdict"][vpc].append(resource)

    return tfdata


def redirect_to_security_group(
    tfdata: Dict[str, Any],
    resource_pattern: str,
) -> Dict[str, Any]:
    """Redirect VPC connections to security group if resource has one.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match resources

    Returns:
        Updated tfdata with redirected connections
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )
    vpcs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_vpc.")

    for resource in resources:
        for connection in tfdata["graphdict"].get(resource, []):
            # Check if connection has security group
            sg_parents = helpers.list_of_parents(tfdata["graphdict"], connection)
            security_groups = [p for p in sg_parents if "aws_security_group" in p]

            if security_groups:
                # Replace resource with security group in VPC
                for vpc in vpcs:
                    if resource in tfdata["graphdict"][vpc]:
                        tfdata["graphdict"][vpc].remove(resource)
                        for sg in security_groups:
                            if sg not in tfdata["graphdict"][vpc]:
                                tfdata["graphdict"][vpc].append(sg)

    return tfdata


def group_shared_services(
    tfdata: Dict[str, Any],
    service_patterns: List[str],
    group_name: str = "aws_group.shared_services",
) -> Dict[str, Any]:
    """Group shared services into a shared services group.

    Args:
        tfdata: Terraform data dictionary
        service_patterns: List of patterns to match shared services
        group_name: Name of the shared services group

    Returns:
        Updated tfdata with shared services grouped
    """
    # Create group if needed
    if group_name not in tfdata["graphdict"]:
        tfdata["graphdict"][group_name] = []
        tfdata["meta_data"][group_name] = {}

    # Find and add shared services (avoid duplicates)
    for node in sorted(tfdata["graphdict"].keys()):
        for pattern in service_patterns:
            if pattern in node and node not in tfdata["graphdict"][group_name]:
                tfdata["graphdict"][group_name].append(node)
                break

    # Replace consolidated nodes with their consolidated names
    updated_services = []
    for service in tfdata["graphdict"][group_name]:
        consolidated = helpers.consolidated_node_check(service, tfdata)
        if consolidated and "cluster" not in service:
            if consolidated not in updated_services:
                updated_services.append(consolidated)
        else:
            if service not in updated_services:
                updated_services.append(service)

    tfdata["graphdict"][group_name] = updated_services

    # Add default IAM service
    if "aws_iam_group.iam" not in tfdata["graphdict"][group_name]:
        tfdata["graphdict"][group_name].append("aws_iam_group.of_services")

    return tfdata


def link_via_shared_child(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str,
    remove_intermediate: bool = True,
) -> Dict[str, Any]:
    """Create direct links when an intermediate node connects to source and target connects to that intermediate.

    Detects pattern: intermediate → source, target → intermediate
    Then creates: source → target

    Example: If node X connects to CloudFront, and ALB connects to node X,
             creates CloudFront → ALB

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources (receives incoming from intermediate)
        target_pattern: Pattern to match target resources (connects to intermediate)
        remove_intermediate: Whether to remove intermediate connections and clean up

    Returns:
        Updated tfdata with direct links
    """
    from modules.config.cloud_config_aws import AWS_GROUP_NODES

    graphdict = tfdata["graphdict"]
    sources = sorted([s for s in graphdict.keys() if source_pattern in s])
    targets = sorted([s for s in graphdict.keys() if target_pattern in s])

    # For each node, check if it connects to source and target connects to it
    for node in sorted(graphdict.keys()):
        connections = graphdict[node]

        for source in sources:
            if source in connections:  # node → source
                for target in targets:
                    # Check if target connects to node (target → node)
                    if node in graphdict.get(target, []):
                        # Create direct source → target link
                        if target not in graphdict[source]:
                            graphdict[source].append(target)

                        if remove_intermediate:
                            # Remove source from intermediate node
                            graphdict[node].remove(source)

                            # Remove target from non-group parents
                            target_parents = helpers.list_of_parents(graphdict, target)
                            for parent in target_parents:
                                parent_type = helpers.get_no_module_name(parent).split(
                                    "."
                                )[0]
                                if parent_type not in AWS_GROUP_NODES:
                                    if target in graphdict[parent]:
                                        graphdict[parent].remove(target)

    return tfdata


def link_via_common_connection(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str,
    remove_shared_connection: bool = False,
) -> Dict[str, Any]:
    """Create direct links when source and target both connect TO the same node.

    Detects pattern: source → shared, target → shared
    Then creates: source → target

    Example: API Gateway → lambda_permission, Lambda → lambda_permission
             becomes API Gateway → Lambda

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources (e.g., "aws_api_gateway")
        target_pattern: Pattern to match target resources (e.g., "aws_lambda_function")
        remove_shared_connection: Whether to remove the shared connection from source

    Returns:
        Updated tfdata with direct links via common connections
    """
    graphdict = tfdata["graphdict"]
    sources = sorted([s for s in graphdict.keys() if source_pattern in s])
    targets = sorted([s for s in graphdict.keys() if target_pattern in s])

    # Find common connections: nodes that both source and target connect TO
    for source in sources:
        source_connections = set(graphdict.get(source, []))
        for target in targets:
            if source == target:
                continue
            target_connections = set(graphdict.get(target, []))
            # Find nodes that both source and target connect to
            shared_connections = source_connections & target_connections
            if shared_connections:
                # Both connect to same node - create source → target link
                if target not in graphdict[source]:
                    graphdict[source].append(target)

                if remove_shared_connection:
                    # Remove shared connections from source
                    for conn in shared_connections:
                        if conn in graphdict[source]:
                            graphdict[source].remove(conn)

    return tfdata


def link_by_metadata_pattern(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_resource: str,
    metadata_key: str,
    metadata_value_pattern: str,
) -> Dict[str, Any]:
    """Create links when source metadata contains pattern.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        target_resource: Target resource to link to
        metadata_key: Metadata key to check
        metadata_value_pattern: Pattern to search for in metadata value

    Returns:
        Updated tfdata with metadata-based links
    """
    sources = sorted([s for s in tfdata["graphdict"].keys() if source_pattern in s])

    for source in sources:
        metadata = tfdata["meta_data"].get(source, {})
        metadata_value = str(metadata.get(metadata_key, ""))

        if metadata_value_pattern in metadata_value:
            if target_resource not in tfdata["graphdict"][source]:
                tfdata["graphdict"][source].append(target_resource)

    return tfdata


def create_transitive_links(
    tfdata: Dict[str, Any],
    source_pattern: str,
    intermediate_pattern: str,
    target_pattern: str,
    remove_intermediate: bool = True,
) -> Dict[str, Any]:
    """Create transitive links: a→b→c becomes a→c.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        intermediate_pattern: Pattern to match intermediate resources
        target_pattern: Pattern to match target resources
        remove_intermediate: Whether to remove intermediate node and connections

    Returns:
        Updated tfdata with transitive links created
    """
    graphdict = tfdata["graphdict"]
    sources = sorted([s for s in graphdict.keys() if source_pattern in s])
    intermediates = sorted([s for s in graphdict.keys() if intermediate_pattern in s])
    targets = sorted([s for s in graphdict.keys() if target_pattern in s])

    for source in sources:
        for intermediate in intermediates:
            if intermediate in graphdict.get(source, []):
                for target in targets:
                    if target in graphdict.get(intermediate, []):
                        # Create direct source → target link
                        if target not in graphdict[source]:
                            graphdict[source].append(target)

                        if remove_intermediate:
                            # Remove intermediate from source
                            graphdict[source].remove(intermediate)
                            # Remove intermediate node entirely
                            graphdict.pop(intermediate, None)
                            tfdata["meta_data"].pop(intermediate, None)

    return tfdata


def link_peers_via_intermediary(
    tfdata: Dict[str, Any],
    intermediary_pattern: str,
    source_pattern: str,
    target_pattern: str,
    remove_intermediary: bool = True,
) -> Dict[str, Any]:
    """Link peer resources that share an intermediary: intermediate→peer1 + intermediate→peer2 becomes peer1→peer2.

    Use case: Event source mappings, queue policies, and other configuration resources
    that logically connect two peers but shouldn't appear in diagrams.

    Pattern:
        Before: intermediate → source, intermediate → target
        After: source → target (intermediate removed)

    Args:
        tfdata: Terraform data dictionary
        intermediary_pattern: Pattern to match intermediary resources (e.g., "aws_lambda_event_source_mapping")
        source_pattern: Pattern to match source peer resources (e.g., "aws_sqs_queue")
        target_pattern: Pattern to match target peer resources (e.g., "aws_lambda_function")
        remove_intermediary: Whether to remove intermediary node (default: True)

    Returns:
        Updated tfdata with peer links created and intermediary optionally removed
    """
    graphdict = tfdata["graphdict"]
    intermediaries = sorted([s for s in graphdict.keys() if intermediary_pattern in s])

    for intermediary in list(intermediaries):
        intermediary_connections = graphdict.get(intermediary, [])

        if not intermediary_connections:
            continue

        # Find source and target peers in intermediary's connections
        sources = [c for c in intermediary_connections if source_pattern in c]
        targets = [c for c in intermediary_connections if target_pattern in c]

        # Only process if we have BOTH sources and targets
        if not (sources and targets):
            continue

        # Create direct links from each source to each target
        for source in sources:
            for target in targets:
                if source in graphdict:
                    if target not in graphdict[source]:
                        graphdict[source].append(target)
                else:
                    graphdict[source] = [target]

        # Remove intermediary node if requested (only if we created links)
        if remove_intermediary:
            # Remove the intermediary node itself
            graphdict.pop(intermediary, None)
            tfdata["meta_data"].pop(intermediary, None)

            # Clean up dangling references to the deleted intermediary from all other nodes
            for node in list(graphdict.keys()):
                if intermediary in graphdict[node]:
                    graphdict[node].remove(intermediary)

    return tfdata


def unlink_from_parents(
    tfdata: Dict[str, Any],
    resource_pattern: str,
    parent_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Remove child resources from all their parent connections.

    Args:
        tfdata: Terraform data dictionary
        resource_pattern: Pattern to match child resources
        parent_filter: Optional pattern to filter which parents to unlink from

    Returns:
        Updated tfdata with children unlinked from parents
    """
    resources = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], resource_pattern
    )

    for resource in resources:
        parents = helpers.list_of_parents(tfdata["graphdict"], resource)

        # Apply parent filter if specified
        if parent_filter:
            parents = [p for p in parents if parent_filter in p]

        for parent in parents:
            if resource in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(resource)

    return tfdata


def insert_intermediate_node(
    tfdata: Dict[str, Any],
    parent_pattern: str,
    child_pattern: str,
    intermediate_node_generator: Callable[[str, Dict[str, Any]], str],
    create_if_missing: bool = True,
) -> Dict[str, Any]:
    """Insert intermediate nodes between parents and children.

    Transforms: parent→child into parent→intermediate→child

    Args:
        tfdata: Terraform data dictionary
        parent_pattern: Pattern to match parent resources
        child_pattern: Pattern to match child resources
        intermediate_node_generator: Function that generates intermediate node name
                                     from child resource and its metadata
        create_if_missing: Create intermediate node if it doesn't exist

    Returns:
        Updated tfdata with intermediate nodes inserted
    """
    parents = helpers.list_of_dictkeys_containing(tfdata["graphdict"], parent_pattern)
    children = helpers.list_of_dictkeys_containing(tfdata["graphdict"], child_pattern)

    for child in children:
        child_parents = [p for p in parents if child in tfdata["graphdict"].get(p, [])]

        # Generate intermediate node name
        child_metadata = tfdata["meta_data"].get(child, {})
        intermediate = intermediate_node_generator(child, child_metadata)

        # Create intermediate node if needed
        if create_if_missing and intermediate not in tfdata["graphdict"]:
            tfdata["graphdict"][intermediate] = []
            # Copy metadata but exclude count-related attributes that would trigger numbering
            intermediate_metadata = copy.deepcopy(child_metadata)
            # Remove attributes that trigger create_multiple_resources
            for attr in ["count", "desired_count", "max_capacity", "for_each"]:
                intermediate_metadata.pop(attr, None)
            tfdata["meta_data"][intermediate] = intermediate_metadata

        # Rewire connections: parent→child becomes parent→intermediate→child
        for parent in child_parents:
            # Remove direct parent→child link
            if child in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].remove(child)

            # Add parent→intermediate link
            if intermediate not in tfdata["graphdict"][parent]:
                tfdata["graphdict"][parent].append(intermediate)

        # Add intermediate→child link
        if child not in tfdata["graphdict"][intermediate]:
            tfdata["graphdict"][intermediate].append(child)

    return tfdata


def bidirectional_link(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str,
    cleanup_reverse: bool = False,
) -> Dict[str, Any]:
    """Create bidirectional links between resources.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        target_pattern: Pattern to match target resources
        cleanup_reverse: Remove target→source links after creating source→target

    Returns:
        Updated tfdata with bidirectional links
    """
    sources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], source_pattern)
    targets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], target_pattern)

    for source in sources:
        for target in targets:
            # Create source→target link
            if target not in tfdata["graphdict"].get(source, []):
                tfdata["graphdict"][source].append(target)

            # Optionally clean up reverse link
            if cleanup_reverse and source in tfdata["graphdict"].get(target, []):
                tfdata["graphdict"][target].remove(source)

    return tfdata


def propagate_metadata(
    tfdata: Dict[str, Any],
    source_pattern: str,
    target_pattern: str = "",
    metadata_keys: Optional[List[str]] = None,
    direction: str = "forward",
    copy_from_connections: bool = False,
    propagate_to_children: bool = False,
) -> Dict[str, Any]:
    """Propagate metadata values from source to target resources.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        target_pattern: Pattern to match target resources (empty if propagate_to_children=True)
        metadata_keys: List of metadata keys to propagate (None = copy all keys)
        direction: "forward" (source→target), "reverse" (target→source), or "bidirectional"
        copy_from_connections: Copy metadata from resources connected to source
        propagate_to_children: Propagate to all children of source (ignores target_pattern)

    Returns:
        Updated tfdata with propagated metadata
    """
    sources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], source_pattern)

    # Determine targets based on mode
    if propagate_to_children:
        # Propagate to all children of sources
        targets = []
        for source in sources:
            children = tfdata["graphdict"].get(source, [])
            # Filter by target_pattern if provided
            if target_pattern:
                children = [c for c in children if target_pattern in c]
            targets.extend(children)
        targets = list(set(targets))  # Remove duplicates
    else:
        targets = helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], target_pattern
        )

    for source in sources:
        source_metadata = tfdata["meta_data"].get(source, {})

        # When propagating to children, get children for this specific source
        if propagate_to_children:
            source_targets = tfdata["graphdict"].get(source, [])
            if target_pattern:
                source_targets = [t for t in source_targets if target_pattern in t]
        else:
            source_targets = targets

        for target in source_targets:
            if target not in tfdata["meta_data"]:
                tfdata["meta_data"][target] = {}

            # Determine which keys to copy
            keys_to_copy = (
                metadata_keys
                if metadata_keys is not None
                else list(source_metadata.keys())
            )

            # Propagate metadata keys
            for key in keys_to_copy:
                value = source_metadata.get(key)

                # Copy from connections if specified
                if copy_from_connections and not value:
                    for connection in tfdata["graphdict"].get(source, []):
                        conn_value = tfdata["meta_data"].get(connection, {}).get(key)
                        if conn_value:
                            value = conn_value
                            break

                if value is not None:
                    if direction in ["forward", "bidirectional"]:
                        tfdata["meta_data"][target][key] = copy.deepcopy(value)

                    if direction in ["reverse", "bidirectional"]:
                        tfdata["meta_data"][source][key] = copy.deepcopy(value)

    return tfdata


def replace_connection_targets(
    tfdata: Dict[str, Any],
    source_pattern: str,
    old_target_pattern: str,
    new_target_pattern: str,
) -> Dict[str, Any]:
    """Replace connection targets matching pattern with new targets.

    Args:
        tfdata: Terraform data dictionary
        source_pattern: Pattern to match source resources
        old_target_pattern: Pattern to match old connection targets
        new_target_pattern: Pattern to match new connection targets

    Returns:
        Updated tfdata with connection targets replaced
    """
    sources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], source_pattern)
    old_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], old_target_pattern
    )
    new_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], new_target_pattern
    )

    if not new_targets:
        return tfdata

    new_target = new_targets[0]  # Use first matching new target

    for source in sources:
        for old_target in old_targets:
            if old_target in tfdata["graphdict"].get(source, []):
                tfdata["graphdict"][source].remove(old_target)
                if new_target not in tfdata["graphdict"][source]:
                    tfdata["graphdict"][source].append(new_target)

    return tfdata


def apply_transformation_pipeline(
    tfdata: Dict[str, Any],
    transformations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply a sequence of transformations from configuration.

    Transformers are automatically discovered by name from this module's globals.
    The operation name in config must match the transformer function name exactly.

    Function parameters ending in '_function' or '_generator' are automatically
    resolved from string names to actual function references from handler modules.

    Args:
        tfdata: Terraform data dictionary
        transformations: List of transformation configs with 'operation' and 'params' keys
                        (params ending in _function or _generator are auto-resolved)

    Returns:
        Updated tfdata after all transformations

    Example:
        transformations = [
            {"operation": "expand_to_numbered_instances", "params": {...}},
            {"operation": "insert_intermediate_node", "params": {
                "intermediate_node_generator": "generate_az_node_name"  # Auto-resolved
            }},
        ]
    """
    for transform_config in transformations:
        operation = transform_config.get("operation")
        params = transform_config.get(
            "params", {}
        ).copy()  # Copy to avoid modifying original

        # Resolve function name strings to actual function references
        # Any parameter ending in _function or _generator is expected to be callable
        import modules.resource_handlers_aws as handlers_aws
        import modules.resource_handlers_gcp as handlers_gcp
        import modules.resource_handlers_azure as handlers_azure

        for param_name, param_value in params.items():
            if isinstance(param_value, str) and (
                param_name.endswith("_function") or param_name.endswith("_generator")
            ):
                # Try to find the function in handler modules
                if hasattr(handlers_aws, param_value):
                    params[param_name] = getattr(handlers_aws, param_value)
                elif hasattr(handlers_gcp, param_value):
                    params[param_name] = getattr(handlers_gcp, param_value)
                elif hasattr(handlers_azure, param_value):
                    params[param_name] = getattr(handlers_azure, param_value)
                else:
                    raise ValueError(
                        f"Could not resolve function '{param_value}' for parameter '{param_name}'. "
                        f"Make sure the function exists in one of the handler modules."
                    )

        # Dynamically look up transformer function by name
        # Operation name must match function name exactly
        transformer_func = globals().get(operation)

        if transformer_func and callable(transformer_func):
            tfdata = transformer_func(tfdata, **params)
        else:
            raise ValueError(
                f"Unknown transformer operation: '{operation}'. "
                f"Make sure the operation name matches a transformer function in resource_transformers.py"
            )

    return tfdata
