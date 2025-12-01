"""
Azure provider configuration for TerraVision.

This module contains all Azure (azurerm) specific constants and configuration.
Initial minimal viable configuration for Phase 1.
"""

# Consolidated nodes for Azure services
# Resources with multiple sub-types that should be consolidated to a single icon
CONSOLIDATED_NODES = [
    # DNS Zone consolidation (zones, records, nameservers)
    {
        "azurerm_dns_zone": {
            "resource_name": "azurerm_dns_zone.dns",
            "import_location": "resource_classes.azure.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    # Network Security Group consolidation (NSG + rules)
    {
        "azurerm_network_security_group": {
            "resource_name": "azurerm_network_security_group.nsg",
            "import_location": "resource_classes.azure.security",
            "vpc": True,
        }
    },
    # Load Balancer consolidation (LB + backend pools + probes + rules)
    {
        "azurerm_lb": {
            "resource_name": "azurerm_lb.load_balancer",
            "import_location": "resource_classes.azure.network",
            "vpc": True,
        }
    },
    # Application Gateway consolidation (gateway + backend pools + listeners + rules)
    {
        "azurerm_application_gateway": {
            "resource_name": "azurerm_application_gateway.app_gw",
            "import_location": "resource_classes.azure.network",
            "vpc": True,
        }
    },
    # Key Vault consolidation (vault + keys + secrets + certificates)
    {
        "azurerm_key_vault": {
            "resource_name": "azurerm_key_vault.keyvault",
            "import_location": "resource_classes.azure.security",
            "vpc": False,
        }
    },
    # Storage Account consolidation (account + containers + blobs + queues)
    {
        "azurerm_storage": {
            "resource_name": "azurerm_storage_account.storage",
            "import_location": "resource_classes.azure.storage",
            "vpc": False,
        }
    },
    # AKS consolidation (cluster + node pools)
    {
        "azurerm_kubernetes": {
            "resource_name": "azurerm_kubernetes_cluster.aks",
            "import_location": "resource_classes.azure.compute",
            "vpc": True,
        }
    },
    # Front Door consolidation (frontdoor + backend pools + routing rules)
    {
        "azurerm_frontdoor": {
            "resource_name": "azurerm_frontdoor.frontdoor",
            "import_location": "resource_classes.azure.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    # CDN consolidation (profile + endpoints)
    {
        "azurerm_cdn": {
            "resource_name": "azurerm_cdn_profile.cdn",
            "import_location": "resource_classes.azure.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    # Log Analytics consolidation (workspace + solutions + data sources)
    {
        "azurerm_log_analytics": {
            "resource_name": "azurerm_log_analytics_workspace.logs",
            "import_location": "resource_classes.azure.management",
            "vpc": False,
        }
    },
    # Container Registry consolidation (registry + replications + webhooks)
    {
        "azurerm_container_registry": {
            "resource_name": "azurerm_container_registry.acr",
            "import_location": "resource_classes.azure.compute",
            "vpc": False,
        }
    },
    # App Service consolidation (plan + app + slots)
    {
        "azurerm_app_service": {
            "resource_name": "azurerm_app_service.webapp",
            "import_location": "resource_classes.azure.compute",
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
# Maps resource types to different variants based on metadata keywords
NODE_VARIANTS = {
    # Load Balancer variants based on SKU
    "azurerm_lb": {
        "Standard": "azurerm_lb_standard",
        "Basic": "azurerm_lb_basic",
    },
    # Virtual Machine variants
    "azurerm_linux_virtual_machine": {
        "Standard_D": "azurerm_linux_vm",
        "Standard_B": "azurerm_linux_vm_basic",
        "Standard_F": "azurerm_linux_vm_compute",
    },
    "azurerm_windows_virtual_machine": {
        "Standard_D": "azurerm_windows_vm",
        "Standard_B": "azurerm_windows_vm_basic",
        "Standard_F": "azurerm_windows_vm_compute",
    },
    # Storage Account variants based on tier
    "azurerm_storage_account": {
        "Premium": "azurerm_storage_premium",
        "Standard": "azurerm_storage_standard",
        "FileStorage": "azurerm_storage_files",
        "BlockBlobStorage": "azurerm_storage_blob",
    },
    # Database variants
    "azurerm_postgresql_flexible_server": {
        "Burstable": "azurerm_postgres_burstable",
        "GeneralPurpose": "azurerm_postgres_general",
        "MemoryOptimized": "azurerm_postgres_memory",
    },
    "azurerm_mysql_flexible_server": {
        "Burstable": "azurerm_mysql_burstable",
        "GeneralPurpose": "azurerm_mysql_general",
        "MemoryOptimized": "azurerm_mysql_memory",
    },
    # App Service variants
    "azurerm_app_service": {
        "Free": "azurerm_app_service_free",
        "Basic": "azurerm_app_service_basic",
        "Standard": "azurerm_app_service_standard",
        "Premium": "azurerm_app_service_premium",
    },
    # AKS variants based on tier
    "azurerm_kubernetes_cluster": {
        "Free": "azurerm_aks_free",
        "Standard": "azurerm_aks_standard",
        "Premium": "azurerm_aks_premium",
    },
    # Application Gateway variants
    "azurerm_application_gateway": {
        "Standard_v2": "azurerm_app_gateway_v2",
        "WAF_v2": "azurerm_app_gateway_waf",
    },
    # Redis Cache variants
    "azurerm_redis_cache": {
        "Basic": "azurerm_redis_basic",
        "Standard": "azurerm_redis_standard",
        "Premium": "azurerm_redis_premium",
    },
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
