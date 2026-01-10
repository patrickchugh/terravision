"""GCP resource handler configurations for TerraVision.

This module defines configuration-driven resource handlers for GCP.
Each configuration specifies how a resource type should be processed,
including transformations to apply and custom handler functions to run.

Handler Types:
- Pure Config-Driven: Only uses declarative transformation building blocks
- Hybrid: Uses transformations + custom Python function
- Pure Function: Uses only custom Python code

See CLAUDE.md for detailed documentation on the handler architecture.
"""

# Resource handler configurations for GCP resources
# Maps Terraform resource types to their handler configurations
RESOURCE_HANDLER_CONFIGS = {
    "google_compute_subnetwork": {
        "description": "Create region nodes and link to subnets (VPC→Subnet becomes VPC→Region→Subnet)",
        "handler_execution_order": "before",  # Run custom function FIRST to prepare metadata
        "additional_handler_function": "gcp_prepare_subnet_region_metadata",
        "transformations": [
            # Insert Region nodes between VPC and subnet
            # This transformer handles both unlinking and relinking in one operation
            {
                "operation": "insert_intermediate_node",
                "params": {
                    "parent_pattern": "google_compute_network",
                    "child_pattern": "google_compute_subnetwork",
                    "intermediate_node_generator": "generate_region_node_name",
                    "create_if_missing": True,
                },
            },
        ],
    },
    "google_compute_instance": {
        "description": "Create zone nodes and link to instances (Subnet→Instance becomes Subnet→Zone→Instance)",
        "handler_execution_order": "before",  # Run custom function FIRST to prepare metadata
        "additional_handler_function": "gcp_prepare_zone_metadata",
        "transformations": [
            # Insert Zone nodes between subnet/region and instance
            # This handles the case where instances point directly to subnets
            {
                "operation": "insert_intermediate_node",
                "params": {
                    "parent_pattern": "google_compute_subnetwork",
                    "child_pattern": "google_compute_instance",
                    "intermediate_node_generator": "generate_zone_node_name",
                    "create_if_missing": True,
                },
            },
        ],
    },
    "google_container_cluster": {
        "description": "Create region nodes and link to GKE clusters (GKE is regional)",
        "handler_execution_order": "before",  # Run custom function FIRST to prepare metadata
        "additional_handler_function": "gcp_prepare_subnet_region_metadata",
        "transformations": [
            # Insert Region nodes between VPC and GKE cluster
            # GKE clusters are regional resources
            {
                "operation": "insert_intermediate_node",
                "params": {
                    "parent_pattern": "google_compute_network",
                    "child_pattern": "google_container_cluster",
                    "intermediate_node_generator": "generate_region_node_name",
                    "create_if_missing": True,
                },
            },
        ],
    },
    "google_compute_instance_group_manager": {
        "description": "Link IGMs to zones under their associated subnets (Pure Function: traces template→subnet relationships)",
        "handler_execution_order": "before",  # Run BEFORE templates moved to regions, so we can trace subnet→template→IGM
        "additional_handler_function": "gcp_link_igms_to_subnet_zones",
        "transformations": [],
    },
    "google_compute_region_instance_group_manager": {
        "description": "Create region nodes and link to regional instance group managers",
        "handler_execution_order": "before",
        "additional_handler_function": "gcp_prepare_subnet_region_metadata",
        "transformations": [
            # Insert Region nodes between VPC and regional instance group manager
            {
                "operation": "insert_intermediate_node",
                "params": {
                    "parent_pattern": "google_compute_network",
                    "child_pattern": "google_compute_region_instance_group_manager",
                    "intermediate_node_generator": "generate_region_node_name",
                    "create_if_missing": True,
                },
            },
        ],
    },
    "google_compute_instance_template": {
        "description": "Move instance templates from subnets/zones to region (regional resources, not zonal)",
        "handler_execution_order": "after",  # Run AFTER other handlers create zones
        "additional_handler_function": "gcp_move_templates_to_region",
        "transformations": [],
    },
    # NOTE: google_compute_firewall is in GROUP_NODES list in cloud_config_gcp.py
    # It renders as a grouping zone with hex color #FBE9E7 (peach)
    # No special handler needed - standard group rendering applies
    #
    # Load Balancer grouping - groups all LB components into a tv_gcp_load_balancer zone
    "google_compute_global_forwarding_rule": {
        "description": "Group load balancer components into tv_gcp_load_balancer zone",
        "handler_execution_order": "after",  # Run after other handlers
        "additional_handler_function": "gcp_group_load_balancer_components",
        "transformations": [],
    },
}
