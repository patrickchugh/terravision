"""GCP resource-specific handlers for Terraform graph processing.

Handles special cases for GCP resources including projects, VPCs, subnets,
firewall rules, load balancers, and other GCP-specific relationships.
"""

from typing import Dict, List, Any
import modules.config.cloud_config_gcp as cloud_config
import modules.helpers as helpers
from ast import literal_eval
import re
import copy

REVERSE_ARROW_LIST = cloud_config.GCP_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.GCP_IMPLIED_CONNECTIONS
GROUP_NODES = cloud_config.GCP_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.GCP_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.GCP_NODE_VARIANTS
SPECIAL_RESOURCES = cloud_config.GCP_SPECIAL_RESOURCES
SHARED_SERVICES = cloud_config.GCP_SHARED_SERVICES
DISCONNECT_SERVICES = cloud_config.GCP_DISCONNECT_LIST


def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle special resource cases and disconnections for GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with special cases handled
    """
    # Remove connections to services specified in disconnect services
    for r in sorted(tfdata["graphdict"].keys()):
        for d in DISCONNECT_SERVICES:
            if d in r:
                tfdata["graphdict"][r] = []
    return tfdata


def gcp_handle_project(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Project relationships.

    Projects are top-level containers in GCP. All GCP resources belong to a Project.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Project relationships configured
    """
    # TODO: Implement Project handling in Phase 4 (US2)
    # - Group all resources by their project attribute
    # - Create hierarchical structure: Project > VPC > Subnet > Resources
    return tfdata


def gcp_handle_vpc(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP VPC (Virtual Private Cloud) relationships.

    VPCs are global network containers in GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with VPC relationships configured
    """
    # TODO: Implement VPC handling in Phase 4 (US2)
    # - Link VPCs to their Projects
    # - Group Subnets within VPCs
    # - VPCs are global in GCP (not regional)
    return tfdata


def gcp_handle_subnet(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Subnet relationships.

    Subnets are regional network segments within VPCs in GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Subnet relationships configured
    """
    # TODO: Implement Subnet handling in Phase 4 (US2)
    # - Link Subnets to their VPCs
    # - Group resources within Subnets
    # - Handle regional placement
    return tfdata


def gcp_handle_firewall(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Firewall Rule relationships.

    Firewall rules are applied at the VPC level in GCP.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Firewall Rule relationships configured
    """
    # TODO: Implement Firewall handling in Phase 4 (US2)
    # - Associate Firewall Rules with VPCs
    # - Handle target tags and service accounts
    return tfdata


def gcp_handle_gke(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP GKE (Google Kubernetes Engine) cluster relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with GKE relationships configured
    """
    # TODO: Implement GKE handling in Phase 4 (US2)
    # - Link GKE clusters to Subnets
    # - Handle node pools
    # - Link to Container Registry (GCR)
    return tfdata


def gcp_handle_instance_group(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Compute Instance Group relationships.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Instance Group relationships configured
    """
    # TODO: Implement Instance Group handling in Phase 4 (US2)
    # - Link instance groups to zones
    # - Handle autoscaling
    return tfdata


def gcp_handle_backend_service(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GCP Backend Service relationships (Load Balancing).

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with Backend Service relationships configured
    """
    # TODO: Implement Backend Service handling in Phase 4 (US2)
    # - Link to instance groups
    # - Link to health checks
    # - Link to forwarding rules
    return tfdata


def gcp_handle_sharedgroup(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group shared GCP services into a shared services group.

    Shared services include KMS, Cloud Storage, Logging, Monitoring, GCR, etc.

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
            if not tfdata["graphdict"].get("google_group.shared_services"):
                tfdata["graphdict"]["google_group.shared_services"] = []
                tfdata["meta_data"]["google_group.shared_services"] = {}
            # Add node to shared services group
            if node not in tfdata["graphdict"]["google_group.shared_services"]:
                tfdata["graphdict"]["google_group.shared_services"].append(node)

    # Replace consolidated nodes with their consolidated names
    if tfdata["graphdict"].get("google_group.shared_services"):
        for service in sorted(
            list(tfdata["graphdict"]["google_group.shared_services"])
        ):
            if helpers.consolidated_node_check(service, tfdata):
                tfdata["graphdict"]["google_group.shared_services"] = list(
                    map(
                        lambda x: x.replace(
                            service, helpers.consolidated_node_check(service, tfdata)
                        ),
                        tfdata["graphdict"]["google_group.shared_services"],
                    )
                )
    return tfdata


def random_string_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Remove random string resources from graph.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with random strings removed
    """
    randoms = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "random_string.")
    for r in list(randoms):
        del tfdata["graphdict"][r]
    return tfdata


def match_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Match GCP resources based on patterns and dependencies.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with resources matched
    """
    # TODO: Implement GCP-specific resource matching in Phase 4 (US2)
    # - Match firewall rules to VPCs
    # - Match instances to subnets
    # - Match load balancers to backend services
    return tfdata


def generate_region_node_name(subnet_name: str, subnet_metadata: Dict[str, Any]) -> str:
    """Generate region node name from subnet metadata.

    This is a helper function for the insert_intermediate_node transformer.
    GCP subnets are regional resources, so they have a region attribute.

    Args:
        subnet_name: Name of the subnet resource (unused - required for transformer signature)
        subnet_metadata: Metadata dictionary for the subnet

    Returns:
        Generated region node name (e.g., "tv_gcp_region.us-central1")
    """
    _ = subnet_name  # Unused but required by transformer signature

    region = subnet_metadata.get("region", "unknown-region")

    # Use tv_gcp_region prefix (synthetic TerraVision node, not real Terraform resource)
    # Similar to existing: tv_gcp_users, tv_gcp_onprem, tv_azurerm_zone, aws_az
    region_node = f"tv_gcp_region.{region}"
    region_node = region_node.replace("-", "_")

    return region_node


def gcp_prepare_subnet_region_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare region metadata for regional resources before transformers run.

    This function runs BEFORE transformations (handler_execution_order: "before")
    to copy region data from original_metadata to meta_data so that the
    generic insert_intermediate_node transformer can use it.

    Handles: subnets, GKE clusters, instance templates, regional instance group managers

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with region metadata prepared
    """
    # Find all regional resources (excluding hidden)
    regional_resource_patterns = [
        "google_compute_subnetwork",
        "google_container_cluster",
        "google_compute_instance_template",
        "google_compute_region_instance_group_manager",
    ]

    regional_resources = [
        k
        for k in tfdata["graphdict"]
        if any(
            helpers.get_no_module_name(k).startswith(pattern)
            for pattern in regional_resource_patterns
        )
        and k not in tfdata.get("hidden", [])
    ]

    # Copy necessary metadata from original_metadata to meta_data
    # so that generate_region_node_name can access it
    for resource in regional_resources:
        original_meta = tfdata.get("original_metadata", {}).get(resource, {})

        # Ensure meta_data exists for this resource
        if resource not in tfdata["meta_data"]:
            tfdata["meta_data"][resource] = {}

        # Copy region for region name generation
        # Some resources use "region", others use "location" (e.g., GKE clusters)
        if "region" in original_meta:
            tfdata["meta_data"][resource]["region"] = original_meta["region"]
        elif "location" in original_meta:
            # GKE clusters and some other resources use "location" instead of "region"
            tfdata["meta_data"][resource]["region"] = original_meta["location"]

    return tfdata


def generate_zone_node_name(
    instance_name: str, instance_metadata: Dict[str, Any]
) -> str:
    """Generate zone node name from instance metadata.

    This is a helper function for the insert_intermediate_node transformer.
    GCP instances run in specific zones (e.g., us-central1-a).

    Args:
        instance_name: Name of the instance resource (unused - required for transformer signature)
        instance_metadata: Metadata dictionary for the instance

    Returns:
        Generated zone node name (e.g., "tv_gcp_zone.us_central1_a")
    """
    _ = instance_name  # Unused but required by transformer signature

    zone = instance_metadata.get("zone", "unknown-zone")

    # Use tv_gcp_zone prefix (synthetic TerraVision node, not real Terraform resource)
    zone_node = f"tv_gcp_zone.{zone}"
    zone_node = zone_node.replace("-", "_")

    return zone_node


def gcp_prepare_zone_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare zone metadata for zonal resources before transformers run.

    This function runs BEFORE transformations (handler_execution_order: "before")
    to copy zone data from original_metadata to meta_data so that the
    generic insert_intermediate_node transformer can use it.

    Handles: compute instances, zonal instance group managers

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with zone metadata prepared
    """
    # Find all zonal resources (excluding hidden)
    # Note: google_compute_instance_group_manager is zonal (vs google_compute_region_instance_group_manager)
    zonal_resource_patterns = [
        "google_compute_instance",
        "google_compute_instance_group_manager",
    ]

    zonal_resources = [
        k
        for k in tfdata["graphdict"]
        if any(
            helpers.get_no_module_name(k).startswith(pattern)
            for pattern in zonal_resource_patterns
        )
        and k not in tfdata.get("hidden", [])
        # Exclude regional instance group managers (they have "region" in the name)
        and "region_instance_group" not in helpers.get_no_module_name(k)
    ]

    # Copy necessary metadata from original_metadata to meta_data
    # so that generate_zone_node_name can access it
    for resource in zonal_resources:
        original_meta = tfdata.get("original_metadata", {}).get(resource, {})

        # Ensure meta_data exists for this resource
        if resource not in tfdata["meta_data"]:
            tfdata["meta_data"][resource] = {}

        # Copy zone for zone name generation
        if "zone" in original_meta:
            tfdata["meta_data"][resource]["zone"] = original_meta["zone"]

    return tfdata


def gcp_link_igms_to_subnet_zones(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Link instance group managers to zones and create synthetic VM instances.

    IGMs are zonal resources that should be organized:
    Subnet → Zone → IGM → Synthetic VMs (based on target_size)

    This handler:
    1. Builds subnet→template mapping from original_graphdict (unmodified Terraform graph)
    2. Finds all instance group manager resources
    3. Traces through their template to find the associated subnet using the mapping
    4. Creates zone nodes under the appropriate subnets
    5. Links IGMs to their respective zones
    6. Creates synthetic VM instances as children of the IGM based on target_size

    Why use original_graphdict:
    - Handler execution order isn't fully deterministic (depends on resource type processing order)
    - By the time this handler runs, other handlers may have already moved templates
    - original_graphdict contains the pristine Terraform relationships before any modifications
    - This makes the handler robust regardless of execution order

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with IGMs linked to subnet zones and populated with synthetic VMs
    """
    # Deduplication: Mark handler as already run to prevent duplicate processing
    # Since this handler processes ALL IGMs at once, it should only run once total
    if tfdata.get("_gcp_igm_zones_processed"):
        return tfdata
    tfdata["_gcp_igm_zones_processed"] = True

    # Build subnet→template mapping from original_graphdict
    # We must use the unmodified Terraform graph because handlers execute in an
    # undefined order based on which resource types are encountered during processing.
    # By the time ANY handler runs, other handlers may have already modified the graph.
    # original_graphdict is the architectural solution for accessing pristine relationships.
    template_to_subnet = {}
    original_graph = tfdata.get("original_graphdict", tfdata["graphdict"])
    for resource, children in original_graph.items():
        if helpers.get_no_module_name(resource).startswith("google_compute_subnetwork"):
            for child in children:
                if helpers.get_no_module_name(child).startswith(
                    "google_compute_instance_template"
                ):
                    template_to_subnet[child] = resource

    # Find all instance group manager resources (zonal only, not regional)
    igm_resources = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith(
            "google_compute_instance_group_manager"
        )
        and not helpers.get_no_module_name(k).startswith(
            "google_compute_region_instance_group_manager"
        )
        and k not in tfdata.get("hidden", [])
    ]

    for igm in igm_resources:
        # Find the template this IGM references (IGM → Template after arrow reversal)
        template = None
        igm_children = tfdata["graphdict"].get(igm, [])
        for child in igm_children:
            if helpers.get_no_module_name(child).startswith(
                "google_compute_instance_template"
            ):
                template = child
                break

        if not template:
            continue

        # Look up the subnet from our pre-built mapping
        subnet = template_to_subnet.get(template)
        if not subnet:
            continue

        # Get zone from IGM metadata
        original_meta = tfdata.get("original_metadata", {}).get(igm, {})
        zone = original_meta.get("zone", "unknown-zone")

        # Generate zone node name unique to this subnet
        # IMPORTANT: Multiple subnets can have resources in the same physical GCP zone.
        # For diagram clarity, we create separate zone instances per subnet (e.g., zone~1, zone~2)
        # to avoid the issue where one zone node can't be drawn in multiple subnet parents.
        zone_base = f"tv_gcp_zone.{zone}".replace("-", "_")

        # Find or create a unique zone instance for THIS SPECIFIC SUBNET
        # Look for existing zone instances already linked to this subnet
        existing_zones = [
            child
            for child in tfdata["graphdict"].get(subnet, [])
            if child.startswith(zone_base)
        ]

        if existing_zones:
            # Reuse existing zone for this subnet
            zone_node = existing_zones[0]
        else:
            # Create new numbered zone instance unique to this subnet
            # Count how many instances of this zone already exist globally
            existing_zone_count = len(
                [k for k in tfdata["graphdict"] if k.startswith(zone_base)]
            )
            if existing_zone_count == 0:
                # First instance - use base name without number
                zone_node = zone_base
            else:
                # Subsequent instances - use numbered format
                zone_node = f"{zone_base}~{existing_zone_count + 1}"

        # CRITICAL: Handler guard to prevent hierarchy gaps (FR-008a)
        # Verify subnet exists in graphdict before creating zone
        if subnet not in tfdata["graphdict"]:
            # Subnet missing - skip zone creation to prevent orphaned zone
            import logging

            logging.warning(
                f"Skipping zone creation for IGM {igm}: subnet {subnet} not found in graphdict. "
                f"This prevents FR-008a violation (zones without subnet parent)"
            )
            continue

        # Create zone node if it doesn't exist
        if zone_node not in tfdata["graphdict"]:
            tfdata["graphdict"][zone_node] = []
        if zone_node not in tfdata["meta_data"]:
            tfdata["meta_data"][zone_node] = {"zone": zone}

        # Link subnet → zone (if not already linked)
        if zone_node not in tfdata["graphdict"][subnet]:
            tfdata["graphdict"][subnet].append(zone_node)

        # Link zone → IGM
        if igm not in tfdata["graphdict"][zone_node]:
            tfdata["graphdict"][zone_node].append(igm)

        # Step 6: Create synthetic VM instances based on target_size
        target_size = original_meta.get("target_size")
        base_instance_name = original_meta.get("base_instance_name", "instance")

        if target_size:
            # Create synthetic VM instances as children of IGM
            try:
                num_instances = int(target_size)
                for i in range(1, num_instances + 1):
                    vm_name = f"google_compute_instance.{base_instance_name}~{i}"

                    # Create VM node in graphdict if it doesn't exist
                    if vm_name not in tfdata["graphdict"]:
                        tfdata["graphdict"][vm_name] = []

                    # Set metadata for synthetic VM
                    if vm_name not in tfdata["meta_data"]:
                        tfdata["meta_data"][vm_name] = {
                            "zone": zone,
                            "synthetic": True,  # Mark as synthetic
                            "instance_template": template,
                        }

                    # Link Zone → VM (place VM inside the zone)
                    if vm_name not in tfdata["graphdict"][zone_node]:
                        tfdata["graphdict"][zone_node].append(vm_name)

                    # Link IGM → VM (arrow showing "managed by" relationship)
                    if vm_name not in tfdata["graphdict"][igm]:
                        tfdata["graphdict"][igm].append(vm_name)
            except (ValueError, TypeError):
                # If target_size is not a valid integer, skip synthetic VM creation
                pass

    # Cleanup: Remove orphaned zones (zones not linked from any subnet)
    # This can happen if zones were created but then IGMs were moved elsewhere
    all_zones = [k for k in tfdata["graphdict"] if k.startswith("tv_gcp_zone.")]
    for zone in all_zones:
        # Check if this zone is a child of any subnet
        is_linked = False
        for resource, children in tfdata["graphdict"].items():
            if helpers.get_no_module_name(resource).startswith(
                "google_compute_subnetwork"
            ):
                if zone in children:
                    is_linked = True
                    break

        # If zone is not linked from any subnet, remove it
        if not is_linked:
            if zone in tfdata["graphdict"]:
                del tfdata["graphdict"][zone]
            if zone in tfdata["meta_data"]:
                del tfdata["meta_data"][zone]

    return tfdata


def gcp_move_templates_to_region(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Move instance templates from subnets to their parent region nodes.

    Instance templates are regional resources, not zonal. They should be children
    of tv_gcp_region nodes, not children of subnets.

    This handler:
    1. Finds all instance template resources
    2. Determines their region from metadata
    3. Creates or finds the appropriate tv_gcp_region node
    4. Moves templates from subnet children to region children

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with templates moved to region level
    """
    # Find all instance template resources
    template_resources = [
        k
        for k in tfdata["graphdict"]
        if helpers.get_no_module_name(k).startswith("google_compute_instance_template")
        and k not in tfdata.get("hidden", [])
    ]

    for template in template_resources:
        # Get template's region from metadata
        original_meta = tfdata.get("original_metadata", {}).get(template, {})
        region = original_meta.get("region", "unknown-region")

        # Generate region node name
        region_node = f"tv_gcp_region.{region}"
        region_node = region_node.replace("-", "_")

        # Ensure region node exists in graphdict
        if region_node not in tfdata["graphdict"]:
            tfdata["graphdict"][region_node] = []
        if region_node not in tfdata["meta_data"]:
            tfdata["meta_data"][region_node] = {}

        # Remove template from all subnet and zone parent lists
        # (templates may have been incorrectly placed in zones by other handlers)
        for resource, children in tfdata["graphdict"].items():
            resource_type = helpers.get_no_module_name(resource)
            if resource_type.startswith(
                "google_compute_subnetwork"
            ) or resource_type.startswith("tv_gcp_zone"):
                if template in children:
                    tfdata["graphdict"][resource] = [
                        c for c in children if c != template
                    ]

        # Add template as child of region node
        if template not in tfdata["graphdict"][region_node]:
            tfdata["graphdict"][region_node].append(template)

    # Clean up empty tv_gcp_zone nodes (leftover from incorrect placements)
    empty_zones = [
        k
        for k, v in tfdata["graphdict"].items()
        if k.startswith("tv_gcp_zone.") and len(v) == 0
    ]
    for zone in empty_zones:
        # Remove empty zone from graphdict
        del tfdata["graphdict"][zone]
        if zone in tfdata["meta_data"]:
            del tfdata["meta_data"][zone]

        # Remove references to empty zone from parent nodes
        for resource, children in tfdata["graphdict"].items():
            if zone in children:
                tfdata["graphdict"][resource] = [c for c in children if c != zone]

    return tfdata


def gcp_group_load_balancer_components(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group load balancer components into a tv_gcp_load_balancer zone.

    GCP load balancers are composed of multiple resources that work together:
    - google_compute_global_forwarding_rule (entry point)
    - google_compute_target_http_proxy / google_compute_target_https_proxy
    - google_compute_url_map (routing)
    - google_compute_backend_service (backend config)
    - google_compute_health_check (health checking)
    - google_compute_global_address (IP address)

    This handler creates a synthetic tv_gcp_load_balancer group node and
    moves all LB components inside it for cleaner visualization.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Updated tfdata with LB components grouped
    """
    lb_component_prefixes = cloud_config.GCP_LOAD_BALANCER_COMPONENTS

    # Find all load balancer components in the graph
    lb_components = []
    for resource in tfdata["graphdict"]:
        resource_type = helpers.get_no_module_name(resource)
        for prefix in lb_component_prefixes:
            if resource_type.startswith(prefix):
                lb_components.append(resource)
                break

    if not lb_components:
        return tfdata

    # Create the load balancer group node
    lb_group_name = "tv_gcp_load_balancer.http_load_balancer"

    if lb_group_name not in tfdata["graphdict"]:
        tfdata["graphdict"][lb_group_name] = []
    if lb_group_name not in tfdata["meta_data"]:
        tfdata["meta_data"][lb_group_name] = {"type": "load_balancer_group"}

    # Move LB components into the group
    for component in lb_components:
        # Add component as child of LB group
        if component not in tfdata["graphdict"][lb_group_name]:
            tfdata["graphdict"][lb_group_name].append(component)

        # Remove component from other parent nodes (except within the LB group itself)
        for parent, children in list(tfdata["graphdict"].items()):
            if parent == lb_group_name:
                continue
            if parent.startswith("tv_gcp_load_balancer"):
                continue
            # Keep LB components pointing to each other within the group
            if parent in lb_components:
                continue
            # Keep connections from synthetic TV nodes (like tv_gcp_users_icon.users)
            # These are auto-annotation connections that should be preserved
            if helpers.get_no_module_name(parent).startswith("tv_"):
                continue
            if component in children:
                tfdata["graphdict"][parent] = [c for c in children if c != component]

    # Preserve connections from LB components to non-LB resources (e.g., backend_service → IGM)
    # These connections should remain as the LB group will have arrows pointing out

    # Add missing connections within the LB group based on known GCP LB hierarchy:
    # Forwarding Rule → Target Proxy → URL Map → Backend Service
    # (These connections may be missing if terraform plan shows computed values as 'true')
    forwarding_rules = [
        c for c in lb_components if "forwarding_rule" in helpers.get_no_module_name(c)
    ]
    target_proxies = [
        c
        for c in lb_components
        if "target_http_proxy" in helpers.get_no_module_name(c)
        or "target_https_proxy" in helpers.get_no_module_name(c)
    ]

    # Connect forwarding rules to target proxies
    # Extract module path (everything before the resource type)
    def get_module_path(resource: str) -> str:
        """Extract module path from resource name like 'module.foo.google_xxx.name'."""
        parts = resource.split(".")
        # Find where the google_ resource type starts
        for i, part in enumerate(parts):
            if part.startswith("google_"):
                return ".".join(parts[:i]) if i > 0 else ""
        return ""

    for fr in forwarding_rules:
        for tp in target_proxies:
            # Only connect if they share the same module path (belong to same LB)
            fr_module = get_module_path(fr)
            tp_module = get_module_path(tp)
            if fr_module == tp_module:
                if tp not in tfdata["graphdict"].get(fr, []):
                    if fr not in tfdata["graphdict"]:
                        tfdata["graphdict"][fr] = []
                    tfdata["graphdict"][fr].append(tp)

    return tfdata
