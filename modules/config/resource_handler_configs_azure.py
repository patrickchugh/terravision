"""Azure resource handler configurations.

Defines transformation pipelines for Azure resources.
Patterns support wildcards via substring matching.
"""

RESOURCE_HANDLER_CONFIGS = {
    # Association resource removal handled in match_resources() after numbering
    # So we can properly connect Load Balancers to backend VMs
    # "association": {
    #     "description": "Remove Azure association resources from diagram (Pure Config)",
    #     "transformations": [
    #         {
    #             "operation": "delete_nodes",
    #             "params": {
    #                 "resource_pattern": "association",
    #                 "remove_from_parents": True,
    #             },
    #         }
    #     ],
    # },
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
}

COMPLEX_HANDLERS = {
    # Azure complex handlers that need custom functions
}
