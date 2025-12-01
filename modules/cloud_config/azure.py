"""
Azure provider configuration for TerraVision.

This module contains all Azure (azurerm) specific constants and configuration.
Initial minimal viable configuration for Phase 1.
"""

# Consolidated nodes for Azure services
CONSOLIDATED_NODES = [
    {
        "azurerm_network_security_group": {
            "resource_name": "azurerm_network_security_group.nsg",
            "import_location": "resource_classes.azure.security",
            "vpc": True,
        }
    },
    {
        "azurerm_lb": {
            "resource_name": "azurerm_lb.load_balancer",
            "import_location": "resource_classes.azure.network",
            "vpc": True,
        }
    },
    {
        "azurerm_application_gateway": {
            "resource_name": "azurerm_application_gateway.app_gw",
            "import_location": "resource_classes.azure.network",
            "vpc": True,
        }
    },
    {
        "azurerm_dns_zone": {
            "resource_name": "azurerm_dns_zone.dns",
            "import_location": "resource_classes.azure.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "azurerm_key_vault": {
            "resource_name": "azurerm_key_vault.keyvault",
            "import_location": "resource_classes.azure.security",
            "vpc": False,
        }
    },
]

# Azure group/container nodes
GROUP_NODES = [
    "azurerm_virtual_network",
    "azurerm_subnet",
    "azurerm_resource_group",
    "azurerm_network_security_group",
]

# Azure edge services (outside VNet but inside cloud boundary)
EDGE_NODES = [
    "azurerm_dns_zone",
    "azurerm_frontdoor",
    "azurerm_cdn_profile",
    "azurerm_application_gateway",
]

# Nodes outside cloud boundary
OUTER_NODES = ["tv_azure_users", "tv_azure_internet"]

# Draw order
DRAW_ORDER = [
    OUTER_NODES,
    EDGE_NODES,
    GROUP_NODES,
    CONSOLIDATED_NODES,
    [""],
]

# Auto-annotations for Azure
AUTO_ANNOTATIONS = [
    {"azurerm_dns_zone": {"link": ["tv_azure_users.users"], "arrow": "reverse"}},
    {
        "azurerm_public_ip": {
            "link": ["tv_azure_internet.internet"],
            "arrow": "forward",
        }
    },
    {
        "azurerm_frontdoor": {
            "link": ["tv_azure_internet.internet"],
            "arrow": "reverse",
        }
    },
]

# Azure resource variants
NODE_VARIANTS = {
    "azurerm_lb": {"Standard": "azurerm_lb_standard", "Basic": "azurerm_lb_basic"},
    "azurerm_linux_virtual_machine": {"Standard": "azurerm_vm"},
    "azurerm_windows_virtual_machine": {"Standard": "azurerm_vm"},
}

# Reverse arrow list
REVERSE_ARROW_LIST = [
    "azurerm_virtual_network.",
    "azurerm_subnet.",
    "azurerm_resource_group.",
    "azurerm_dns_zone",
]

# Forced destination (databases, VMs)
FORCED_DEST = [
    "azurerm_mysql_flexible_server",
    "azurerm_postgresql_flexible_server",
    "azurerm_sql_server",
    "azurerm_linux_virtual_machine",
    "azurerm_windows_virtual_machine",
]

# Forced origin (edge services)
FORCED_ORIGIN = ["azurerm_dns_zone", "azurerm_frontdoor", "azurerm_cdn_profile"]

# Implied connections based on keywords in metadata
IMPLIED_CONNECTIONS = {
    "key_vault_id": "azurerm_key_vault",
    "ssl_certificate": "azurerm_key_vault",
}

# Special resource handlers
SPECIAL_RESOURCES = {
    "azurerm_virtual_network": "azure_handle_vnet_subnets",
    "azurerm_network_security_group": "azure_handle_nsg",
    "azurerm_lb": "azure_handle_lb",
    "azurerm_application_gateway": "azure_handle_app_gateway",
}

# Shared services (resources that can be referenced across multiple VNets)
SHARED_SERVICES = [
    "azurerm_key_vault",
    "azurerm_log_analytics_workspace",
    "azurerm_storage_account",
    "azurerm_dns_zone",
]

# Always draw connection lines for these resources
ALWAYS_DRAW_LINE = [
    "azurerm_lb",
    "azurerm_application_gateway",
    "azurerm_network_security_group",
]

# Never draw lines for these
NEVER_DRAW_LINE = ["azurerm_role_assignment"]

DISCONNECT_LIST = ["azurerm_role_assignment"]

# Azure acronyms
ACRONYMS_LIST = [
    "vm",
    "vnet",
    "nsg",
    "lb",
    "ip",
    "dns",
    "sql",
    "aks",
    "acr",
    "cdn",
    "kv",
    "rg",
]

# Azure name replacements
NAME_REPLACEMENTS = {
    "virtual_network": "VNet",
    "network_security_group": "NSG",
    "linux_virtual_machine": "Linux VM",
    "windows_virtual_machine": "Windows VM",
    "public_ip": "Public IP",
    "application_gateway": "App Gateway",
    "key_vault": "Key Vault",
    "log_analytics_workspace": "Log Analytics",
    "frontdoor": "Front Door",
    "cdn_profile": "CDN",
    "resource_group": "Resource Group",
}
