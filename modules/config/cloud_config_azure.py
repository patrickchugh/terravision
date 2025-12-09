# Azure Cloud Configuration for TerraVision
# Provider: Microsoft Azure (azurerm, azuread, azurestack providers)
# Architecture: Resource Groups > Virtual Networks > Subnets > Resources

# Provider metadata
PROVIDER_NAME = "Azure"
PROVIDER_PREFIX = ["azurerm_", "azuread_", "azurestack_", "azapi_"]
ICON_LIBRARY = "azure"

# Resource type to icon mappings (Azure uses resource_classes directly like AWS)
# This is maintained for validation consistency across providers
# Resource classes located in resource_classes/azure/ (compute.py, network.py, etc.)
RESOURCE_MAPPINGS = {}  # Azure uses dynamic resource class loading

# Any resource names with certain prefixes are consolidated into one node
AZURE_CONSOLIDATED_NODES = [
    {
        "azurerm_public_ip": {
            "resource_name": "azurerm_public_ip.public_ip",
            "import_location": "resource_classes.azure.network",
            "vnet": False,
            "edge_service": False,
        }
    },
    {
        "azurerm_network_security_group": {
            "resource_name": "azurerm_network_security_group.nsg",
            "import_location": "resource_classes.azure.network",
            "vnet": True,
        }
    },
    {
        "azurerm_application_gateway": {
            "resource_name": "azurerm_application_gateway.appgw",
            "import_location": "resource_classes.azure.network",
            "vnet": True,
        }
    },
    {
        "azurerm_load_balancer": {
            "resource_name": "azurerm_load_balancer.lb",
            "import_location": "resource_classes.azure.network",
            "vnet": True,
        }
    },
    {
        "azurerm_key_vault": {
            "resource_name": "azurerm_key_vault.keyvault",
            "import_location": "resource_classes.azure.security",
            "vnet": False,
        }
    },
    {
        "azurerm_monitor": {
            "resource_name": "azurerm_monitor.monitor",
            "import_location": "resource_classes.azure.management",
            "vnet": False,
        }
    },
]

# List of Group type nodes and order to draw them in
# Azure hierarchy: Resource Group > VNet > Subnet > NSG
AZURE_GROUP_NODES = [
    "azurerm_resource_group",
    "azurerm_virtual_network",
    "azurerm_subnet",
    "azurerm_network_security_group",
    "tv_azure_onprem",
]

# Nodes to be drawn first inside the Azure Cloud but outside any VNets
AZURE_EDGE_NODES = [
    "azurerm_dns_zone",
    "azurerm_traffic_manager_profile",
    "azurerm_cdn_profile",
    "azurerm_firewall",
    "azurerm_application_gateway",
]

# Nodes outside Cloud boundary
AZURE_OUTER_NODES = ["tv_azure_users", "tv_azure_internet"]

# Order to draw nodes - leave empty string list till last to denote everything else
AZURE_DRAW_ORDER = [
    AZURE_OUTER_NODES,
    AZURE_EDGE_NODES,
    AZURE_GROUP_NODES,
    AZURE_CONSOLIDATED_NODES,
    [""],
]

# List of prefixes where additional nodes should be created automatically
AZURE_AUTO_ANNOTATIONS = [
    {"azurerm_dns_zone": {"link": ["tv_azure_users.users"], "arrow": "reverse"}},
    {
        "azurerm_virtual_network_gateway": {
            "link": [
                "tv_azure_onprem.corporate_datacenter",
            ],
            "arrow": "forward",
        }
    },
    {
        "azurerm_public_ip": {
            "link": ["tv_azure_internet.internet"],
            "arrow": "forward",
        }
    },
    {"azurerm_kubernetes_cluster": {"link": ["azurerm_container_registry.acr"], "arrow": "forward"}},
    {"azurerm_app_service": {"link": ["azurerm_app_service_plan.appplan"], "arrow": "reverse"}},
]

# Variant icons for the same service - matches keyword in meta data and changes resource type
AZURE_NODE_VARIANTS = {
    "azurerm_virtual_machine": {"linux": "azurerm_linux_virtual_machine", "windows": "azurerm_windows_virtual_machine"},
    "azurerm_sql_database": {"basic": "azurerm_sql_database_basic", "standard": "azurerm_sql_database_standard"},
}

# Automatically reverse arrow direction for these resources when discovered through source
AZURE_REVERSE_ARROW_LIST = [
    "azurerm_dns_zone",
    "azurerm_virtual_network.",
    "azurerm_subnet.",
    "azurerm_resource_group.",
    "azurerm_network_security_group.",
]

# Force certain resources to be a destination connection only - original TF node relationships only
AZURE_FORCED_DEST = ["azurerm_sql_database", "azurerm_postgresql_server", "azurerm_mysql_server", "azurerm_virtual_machine"]

# Force certain resources to be a origin connection only - original TF node relationships only
AZURE_FORCED_ORIGIN = ["azurerm_dns_zone", "azurerm_traffic_manager_profile"]

AZURE_IMPLIED_CONNECTIONS = {
    "key_vault_id": "azurerm_key_vault",
    "storage_account_id": "azurerm_storage_account",
}

# List of special resources and handler function name
AZURE_SPECIAL_RESOURCES = {
    "azurerm_resource_group": "azure_handle_resource_group",
    "azurerm_virtual_network": "azure_handle_vnet",
    "azurerm_subnet": "azure_handle_subnet",
    "azurerm_network_security_group": "azure_handle_nsg",
    "azurerm_virtual_machine_scale_set": "azure_handle_vmss",
    "azurerm_application_gateway": "azure_handle_appgw",
    "azurerm_": "azure_handle_sharedgroup",
    "random_string": "random_string_handler",
}

AZURE_SHARED_SERVICES = [
    "azurerm_key_vault",
    "azurerm_monitor",
    "azurerm_log_analytics_workspace",
    "azurerm_container_registry",
    "azurerm_storage_account",
]

AZURE_ALWAYS_DRAW_LINE = [
    "azurerm_load_balancer",
    "azurerm_application_gateway",
    "azurerm_network_interface",
    "azurerm_virtual_machine_scale_set",
]

AZURE_NEVER_DRAW_LINE = ["azurerm_role_assignment"]

AZURE_DISCONNECT_LIST = ["azurerm_role_assignment"]

AZURE_ACRONYMS_LIST = [
    "vm",
    "vnet",
    "nsg",
    "nic",
    "ip",
    "lb",
    "acr",
    "aks",
    "sql",
    "rg",
    "vnet",
    "api",
]

AZURE_NAME_REPLACEMENTS = {
    "virtual_machine": "VM",
    "virtual_network": "VNet",
    "network_security_group": "NSG",
    "network_interface": "NIC",
    "public_ip": "Public IP",
    "resource_group": "Resource Group",
    "storage_account": "Storage",
    "sql_server": "SQL Server",
    "sql_database": "SQL DB",
    "kubernetes_cluster": "AKS",
    "container_registry": "ACR",
    "key_vault": "Key Vault",
    "app_service": "App Service",
    "function_app": "Function",
    "this": "",
}

AZURE_REFINEMENT_PROMPT = """
You are an expert Azure Solutions Architect. I have a JSON representation of an Azure architecture diagram generated from Terraform code. The diagram may have incorrect resource groupings, missing connections, or layout issues.
INPUT JSON FORMAT: Each key is a Terraform resource ID, and its value is a list of resource IDs it connects to.
SPECIAL CONVENTIONS:
- Resources starting with "tv_" are visual helper nodes (e.g., "tv_azure_internet.internet" represents the public internet)
- Resource Groups are always top-level containers - all Azure resources belong to a Resource Group
- VNets (Virtual Networks) are network boundary containers within Resource Groups
- Subnets are network segments within VNets
- Network Security Groups (NSGs) can be associated with Subnets or Network Interfaces
- Resources ending with ~1, ~2, ~3 (instance number) indicate multiple instances or multi-AZ deployments

Please refine this diagram following Azure conventions and industry best practices:
1. Fix resource groupings (Resource Groups > VNets > Subnets > Resources)
2. Add missing logical connections between resources
3. Remove incorrect connections
4. Ensure proper hierarchy and containment
5. Group related resources (e.g., VMs with their NICs, Load Balancers with backend pools)
6. Add implied connections (e.g., VMs to Storage Accounts, App Services to SQL Databases)
7. Ensure NSGs are properly associated with Subnets or NICs
8. Group shared services (Key Vault, Monitor, ACR) separately
9. Virtual Network Gateways should connect to on-premises representations
10. Public IPs should connect to internet boundary

"""

AZURE_DOCUMENTATION_PROMPT = """\
You are an Azure architect that needs to summarise this JSON of Terraform Azure resources and their associations concisely in paragraph form using as few bullet points as possible. Follow these instructions:
1. If you see ~1, ~2, ~3 etc at the end of the resource name it means multiple instances of the same resource are created. Include how many of each resource type are created in the summary.
2. Use only Azure resource names in the text which can be inferred from terraform resource type names. e.g. instead of azurerm_virtual_machine.XXX just say a Virtual Machine named XXX
3. Mention which resources are associated with each respective Resource Group, VNet, and Subnet if any.
4. Provide an overall summary of the architecture and what the system does

"""

# Replace with your OLLAMA server IP and port number
OLLAMA_HOST = "http://localhost:11434"

# Replace with your actual API Gateway endpoint
BEDROCK_API_ENDPOINT = (
    "https://yirz70b5mc.execute-api.us-east-1.amazonaws.com/prod/chat"
)
