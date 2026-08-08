"""Azure resource handler configurations.

Defines transformation pipelines for Azure resources.
Patterns support wildcards via substring matching.
"""

RESOURCE_HANDLER_CONFIGS = {
    # Core Azure hierarchy handlers (Pure Function - complex logic)
    "azurerm_resource_group": {
        "description": "Handle Azure Resource Group relationships - all resources belong to RG (Pure Function)",
        "additional_handler_function": "azure_handle_resource_group",
    },
    "azurerm_virtual_network": {
        "description": "Handle Azure Virtual Network relationships - network boundary containers (Pure Function)",
        "additional_handler_function": "azure_handle_vnet",
    },
    "azurerm_subnet": {
        "description": "Handle Azure Subnet relationships - places VMs and NICs in correct subnet (Pure Function)",
        "additional_handler_function": "azure_handle_subnet",
    },
    # VMSS with zone expansion
    "azurerm_virtual_machine_scale_set": {
        "description": "Handle Azure VMSS - expansion and zone containerization (Pure Function)",
        "additional_handler_function": "azure_handle_vmss",
    },
    "azurerm_linux_virtual_machine_scale_set": {
        "description": "Handle Azure Linux VMSS - expansion and zone containerization (Pure Function)",
        "additional_handler_function": "azure_handle_vmss",
    },
    "azurerm_windows_virtual_machine_scale_set": {
        "description": "Handle Azure Windows VMSS - expansion and zone containerization (Pure Function)",
        "additional_handler_function": "azure_handle_vmss",
    },
    # NSG: resolve association resources into connections, place NSG in subnet as a node
    "azurerm_network_security_group": {
        "description": "Place NSGs inside associated subnets and clean up association resources (Pure Function)",
        "additional_handler_function": "azure_handle_nsg",
    },
    # Load balancers keep their own identity (external vs internal matters), so
    # instead of consolidating them we fold each LB's own sub-resources into it
    "azurerm_lb": {
        "description": "Collapse LB backend pools and NIC associations into a direct LB to NIC link, and drop probes and rules (Pure Config-Driven)",
        "transformations": [
            # A backend pool is an implementation detail, so whatever it points
            # at belongs on the LB itself. Empty target_pattern matches every
            # child, which covers both NIC associations and scale sets that
            # attach to the pool directly.
            # remove_intermediate stays False throughout: create_transitive_links
            # deletes the intermediate inside its target loop, so with more than
            # one target only the first link survives. The nodes are dropped by
            # the delete_nodes steps below instead.
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "azurerm_lb.",
                    "intermediate_pattern": "azurerm_lb_backend_address_pool.",
                    "target_pattern": "",
                    "remove_intermediate": False,
                },
            },
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "azurerm_lb.",
                    "intermediate_pattern": "azurerm_network_interface_backend_address_pool_association.",
                    "target_pattern": "azurerm_network_interface.",
                    "remove_intermediate": False,
                },
            },
            {
                "operation": "delete_nodes",
                "params": {"resource_pattern": "azurerm_lb_probe."},
            },
            {
                "operation": "delete_nodes",
                "params": {"resource_pattern": "azurerm_lb_rule."},
            },
            {
                "operation": "delete_nodes",
                "params": {"resource_pattern": "azurerm_lb_backend_address_pool."},
            },
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "azurerm_network_interface_backend_address_pool_association."
                },
            },
        ],
    },
    # A VPN connection resource is the link between the Azure gateway and the
    # remote peer, not a thing in its own right. Left as a node it draws twice
    # (once each way) and buries the gateway in lines.
    "azurerm_virtual_network_gateway": {
        "description": "Collapse VPN connections into a direct gateway to peer link (Pure Config-Driven)",
        "transformations": [
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "azurerm_virtual_network_gateway.",
                    "intermediate_pattern": "azurerm_virtual_network_gateway_connection.",
                    "target_pattern": "azurerm_local_network_gateway.",
                    "remove_intermediate": False,
                },
            },
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "azurerm_virtual_network_gateway_connection."
                },
            },
        ],
    },
    # A local network gateway is Azure's stand-in for the far end of a VPN
    # tunnel, not a device in the subscription, so it belongs in the
    # on-premises box rather than loose on the canvas
    "azurerm_local_network_gateway": {
        "description": "Move VPN peers into the on-premises box and make the tunnel two-way (Pure Function)",
        "additional_handler_function": "azure_handle_local_network_gateway",
    },
    # Route tables: the association resource is pure plumbing, but it is the
    # only thing linking a subnet to its route table - so collapse rather than
    # hide, keeping subnet -> route table
    "azurerm_route_table": {
        "description": "Collapse subnet to association to route table into a direct subnet to route table link (Pure Config-Driven)",
        "transformations": [
            {
                "operation": "create_transitive_links",
                "params": {
                    "source_pattern": "azurerm_subnet.",
                    "intermediate_pattern": "azurerm_subnet_route_table_association.",
                    "target_pattern": "azurerm_route_table.",
                    "remove_intermediate": True,
                },
            },
            # Several subnets usually share one route table. A node can only be
            # drawn inside one cluster, so the sharing subnets would be left
            # with no member of their own and drift outside their VNET - give
            # each its own copy instead.
            {
                "operation": "expand_shared_children",
                "params": {
                    "parent_pattern": "azurerm_subnet.",
                    "child_pattern": "azurerm_route_table.",
                },
            },
        ],
    },
    # Runs last: sweeps up services that belong to no network boundary so they
    # stop floating loose around the diagram
    "azurerm_": {
        "description": "Group shared services into a single Shared Services box (Pure Config-Driven)",
        "transformations": [
            {
                "operation": "group_shared_services",
                "params": {
                    "service_patterns": [
                        "azurerm_key_vault",
                        "azurerm_monitor",
                        "azurerm_log_analytics_workspace",
                        "azurerm_container_registry",
                        "azurerm_storage_account",
                        "azurerm_storage_share",
                        "azurerm_disk_encryption_set",
                    ],
                    "group_name": "azurerm_group.shared_services",
                    # No AWS IAM node on an Azure diagram
                    "always_include": "",
                },
            },
        ],
    },
}

COMPLEX_HANDLERS = {
    # Azure complex handlers that need custom functions
}
