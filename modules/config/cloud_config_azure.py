# Azure Cloud Configuration for TerraVision
# Provider: Microsoft Azure (azurerm, azuread, azurestack providers)
# Architecture: Resource Groups > Virtual Networks > Subnets > Resources

# Provider metadata
PROVIDER_NAME = "Azure"
PROVIDER_PREFIX = ["azurerm_", "azuread_", "azurestack_", "azapi_"]
ICON_LIBRARY = "azure"

# Any resource names with certain prefixes are consolidated into one node
AZURE_CONSOLIDATED_NODES = [
    {
        "azurerm_public_ip": {
            "resource_name": "azurerm_public_ip.public_ip",
            "import_location": "resource_classes.azure.network",
            "edge_service": False,
        }
    },
    {
        "azurerm_application_gateway": {
            "resource_name": "azurerm_application_gateway.appgw",
            "import_location": "resource_classes.azure.network",
        }
    },
    {
        "azurerm_load_balancer": {
            "resource_name": "azurerm_load_balancer.lb",
            "import_location": "resource_classes.azure.network",
        }
    },
    # NOTE: azurerm_lb is deliberately NOT consolidated. Merging every load
    # balancer into one node hides real topology - a hub firewall design has a
    # separate external and internal NLB and collapsing them makes the traffic
    # path unreadable. Sub-resources are folded into their own parent LB by the
    # azurerm_lb handler config instead.
    {
        "azurerm_storage_share": {
            "resource_name": "azurerm_storage_share.share",
            "import_location": "resource_classes.azure.storage",
        }
    },
    {
        "azurerm_storage_share_directory": {
            "resource_name": "azurerm_storage_share.share",
            "import_location": "resource_classes.azure.storage",
        }
    },
    {
        "azurerm_storage_share_file": {
            "resource_name": "azurerm_storage_share.share",
            "import_location": "resource_classes.azure.storage",
        }
    },
    {
        "azurerm_key_vault": {
            "resource_name": "azurerm_key_vault.keyvault",
            "import_location": "resource_classes.azure.security",
        }
    },
    {
        "azurerm_monitor": {
            "resource_name": "azurerm_monitor.monitor",
            "import_location": "resource_classes.azure.management",
        }
    },
    {
        "azurerm_api_management_api": {
            "resource_name": "azurerm_api_management.apim",
            "import_location": "resource_classes.azure.integration",
        }
    },
    {
        "azurerm_api_management_logger": {
            "resource_name": "azurerm_api_management.apim",
            "import_location": "resource_classes.azure.integration",
        }
    },
    {
        "azurerm_api_management_diagnostic": {
            "resource_name": "azurerm_api_management.apim",
            "import_location": "resource_classes.azure.integration",
        }
    },
    {
        "azurerm_api_management_api_operation": {
            "resource_name": "azurerm_api_management.apim",
            "import_location": "resource_classes.azure.integration",
        }
    },
    {
        "azurerm_api_management_api_policy": {
            "resource_name": "azurerm_api_management.apim",
            "import_location": "resource_classes.azure.integration",
        }
    },
    {
        "azurerm_api_management_api_operation_policy": {
            "resource_name": "azurerm_api_management.apim",
            "import_location": "resource_classes.azure.integration",
        }
    },
]

# List of Group type nodes and order to draw them in
# Azure hierarchy: Resource Group > VNet > Subnet > NSG
AZURE_GROUP_NODES = [
    "azurerm_resource_group",
    # Shared services box - a Cluster class, so it must be declared as a group
    # or the renderer instantiates it as a plain node and blows up on ._id
    "azurerm_group",
    "azurerm_virtual_network",
    "azurerm_subnet",
    "tv_azurerm_zone",  # Availability zones for VMSS instances
    "tv_azure_onprem",
]

# Nodes to remove in simplified mode for a high-level services-only view
AZURE_SIMPLIFIED_REMOVE_NODES = [
    # Group/container nodes
    "azurerm_resource_group",
    "azurerm_virtual_network",
    "azurerm_subnet",
    "tv_azurerm_zone",
    # Networking plumbing
    "azurerm_route_table",
    "azurerm_network_security_group",
    "azurerm_network_security_rule",
    "azurerm_network_interface",
    "azurerm_public_ip",
    "azurerm_nat_gateway",
    "azurerm_subnet_route_table_association",
    "azurerm_subnet_network_security_group_association",
    # IAM
    "azurerm_role_assignment",
    "azurerm_user_assigned_identity",
]

AZURE_SIMPLIFIED_GATEWAY_TYPES = []
AZURE_SIMPLIFIED_COMPUTE_TYPES = []

# Nodes to be drawn first inside the Azure Cloud but outside any VNets
AZURE_EDGE_NODES = [
    "azurerm_dns_zone",
    "azurerm_traffic_manager_profile",
    "azurerm_cdn_profile",
    "azurerm_firewall",
    "azurerm_application_gateway",
]

# Nodes outside Cloud boundary
# NB these must match the node types actually created (tv_azurerm_*). The old
# values silently never matched - "tv_azure_users" was missing the "rm" and
# "tv_azurerm_internet " had a trailing space - so Users and Internet were
# drawn inside the cloud boundary instead of outside it.
AZURE_OUTER_NODES = ["tv_azurerm_users", "tv_azurerm_internet"]

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
            "link": ["tv_azurerm_internet.internet"],
            "arrow": "forward",
        }
    },
    {
        "azurerm_public_ip": {
            "link": ["tv_azurerm_users.users"],
            "arrow": "reverse",
        }
    },
    {
        "tv_azurerm_internet.internet": {
            "link": ["tv_azurerm_users.users"],
            "arrow": "reverse",
        }
    },
    {
        "azurerm_kubernetes_cluster": {
            "link": ["azurerm_container_registry.acr"],
            "arrow": "forward",
        }
    },
    {
        "azurerm_app_service": {
            "link": ["azurerm_app_service_plan.appplan"],
            "arrow": "reverse",
        }
    },
]

# Variant icons for the same service - matches keyword in meta data and changes resource type
# Marketplace network appliances are ordinary Linux VMs as far as Terraform is
# concerned, so they draw as a generic server. The image publisher identifies
# what the VM actually is; matching on it gives the appliance its real icon.
AZURE_NODE_VARIANTS = {
    "azurerm_linux_virtual_machine": {
        # Marketplace publisher ids - distinctive enough to match safely, since
        # check_variant() searches the whole metadata blob rather than a
        # specific attribute
        # NB not "azurerm_firewall" - that is the managed Azure Firewall
        # service and an EDGE_NODE, which would pull the VM out of its VNET
        "paloaltonetworks": "azurerm_virtual_machine_appliance",
        "fortinet": "azurerm_virtual_machine_appliance",
        "checkpoint": "azurerm_virtual_machine_appliance",
    },
    "azurerm_virtual_machine": {
        "linux": "azurerm_linux_virtual_machine",
        "windows": "azurerm_windows_virtual_machine",
    },
    "azurerm_sql_database": {
        "basic": "azurerm_sql_database_basic",
        "standard": "azurerm_sql_database_standard",
    },
}

# Automatically reverse arrow direction for these resources when discovered through source
AZURE_REVERSE_ARROW_LIST = [
    "azurerm_resource_group.",  # Highest priority - everything belongs to a resource group
    "azurerm_virtual_network.",
    "azurerm_subnet.",
    "azurerm_network_security_group.",
    "azurerm_dns_zone",
    # A public IP is attached to a frontend rather than sitting behind it, so
    # Terraform's "the load balancer references its IP" is a dependency, not a
    # flow. Reversed, inbound traffic reads the way it actually travels:
    # users -> public IP -> load balancer -> backend NICs.
    "azurerm_public_ip.",
]

# Force certain resources to be a destination connection only - original TF node relationships only
AZURE_FORCED_DEST = [
    "azurerm_sql_database",
    "azurerm_postgresql_server",
    "azurerm_mysql_server",
    "azurerm_virtual_machine",
]

# Force certain resources to be a origin connection only - original TF node relationships only
AZURE_FORCED_ORIGIN = ["azurerm_dns_zone", "azurerm_traffic_manager_profile"]

AZURE_IMPLIED_CONNECTIONS = {
    "key_vault_id": "azurerm_key_vault",
    "storage_account_id": "azurerm_storage_account",
    "api_management_name": "azurerm_api_management",
    "eventhub_name": "azurerm_eventhub",
    "stream_analytics_job_name": "azurerm_stream_analytics_job",
}

# Special resources that need custom handling
# TODO: Migrate to config-driven approach like AWS (see resource_handler_configs_azure.py)
# For now, keeping manual dict until Azure handlers are refactored
from modules.config.resource_handler_configs_azure import RESOURCE_HANDLER_CONFIGS

# Generate from config if available, otherwise use manual dict
if RESOURCE_HANDLER_CONFIGS:
    AZURE_SPECIAL_RESOURCES = {
        pattern: config.get("additional_handler_function", f"config_handler_{pattern}")
        for pattern, config in RESOURCE_HANDLER_CONFIGS.items()
    }
else:
    # Manual dict (legacy - will be removed once handlers are migrated)
    AZURE_SPECIAL_RESOURCES = {
        "azurerm_resource_group": "azure_handle_resource_group",
        "azurerm_virtual_network": "azure_handle_vnet",
        "azurerm_subnet": "azure_handle_subnet",
        "azurerm_virtual_machine_scale_set": "azure_handle_vmss",
        "azurerm_linux_virtual_machine_scale_set": "azure_handle_vmss",
        "azurerm_windows_virtual_machine_scale_set": "azure_handle_vmss",
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
    "azurerm_kubernetes_cluster",
]

AZURE_NEVER_DRAW_LINE = ["azurerm_role_assignment"]

AZURE_DISCONNECT_LIST = ["azurerm_role_assignment"]

# Plumbing resources that carry no architectural meaning on a diagram. Hidden
# nodes are skipped by both relationship detection and drawing, so only list
# types whose links are represented some other way (an NSG association is
# redundant once the NSG itself is drawn against the NIC).
AZURE_HIDE_NODES = [
    "azurerm_network_security_rule",
    "azurerm_network_interface_security_group_association",
    "azurerm_subnet_network_security_group_association",
    # Peerings are drawn as a line between the two VNET boxes (AZURE_GROUP_LINKS),
    # so an icon for them as well is a duplicate that also drags spurious edges
    # onto whatever it was attached to.
    "azurerm_virtual_network_peering",
    # Individual routes are entries *inside* a route table and draw with the
    # same icon as the table itself, so showing both doubles the route icons
    # on the diagram without adding information. The route table stays.
    "azurerm_route",
    # Access control is not network architecture. These carry generated GUIDs
    # as their deployed name, so they render as unreadable labels attached to
    # whatever they grant rights over.
    "azurerm_role_assignment",
    "azurerm_role_definition",
    "azurerm_user_assigned_identity",
    "azuread_user",
    "azuread_group",
    "azuread_service_principal",
    # Terraform glue with no cloud presence at all
    "null_resource",
    "terraform_data",
    "time_sleep",
    "local_file",
    "random_string",
]

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
    "linux_virtual_machine": "Linux VM",
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
    "lb": "Load Balancer",
    "this": "",
}

# Configuration patterns for multi-instance resource detection
# Each pattern defines:
# - resource_types: List of Terraform resource types to check
# - trigger_attributes: Attributes that trigger expansion (e.g., "subnets", "zones")
# - also_expand_attributes: Attributes containing related resources to also expand
# - resource_pattern: Regex pattern to extract resource references from attribute values
AZURE_MULTI_INSTANCE_PATTERNS = [
    {
        "resource_types": ["azurerm_public_ip"],
        "trigger_attributes": ["zones"],
        "also_expand_attributes": [],
        "resource_pattern": r"^(.+)$",  # Match plain zone strings: ["1", "2", "3"]
        "description": "Azure Load Balancer with multiple zones",
    },
    {
        "resource_types": [
            "azurerm_linux_virtual_machine_scale_set",
            "azurerm_windows_virtual_machine_scale_set",
        ],
        "trigger_attributes": ["zones"],
        "also_expand_attributes": [],
        "resource_pattern": r"^(.+)$",  # Match plain zone strings ["1", "2", "3"]
        "description": "Azure VM Scale Set with multiple zones",
    },
    {
        "resource_types": ["azurerm_kubernetes_cluster_node_pool"],
        "trigger_attributes": ["zones"],
        "also_expand_attributes": [],
        "resource_pattern": r"^(.+)$",  # Match plain zone strings ["1", "2", "3"]
        "description": "Azure Kubernetes Service node pool with multiple zones",
    },
    # Add more Azure patterns as needed
]

# Replace with your OLLAMA server IP and port number
OLLAMA_HOST = "http://localhost:11434"

# Default Ollama model used by --ai-annotate ollama. Must be already
# pulled to the local Ollama server (`ollama pull <model>`). Any model
# the server has installed is valid — llama3, mistral, qwen2.5,
# llama3.1, etc.
OLLAMA_MODEL = "llama3"

# Resources that describe a relationship between two whole groups rather than
# anything inside them. Rendered as an edge clipped to both group boundaries
# instead of an icon sitting inside one of them (see _draw_group_links).
AZURE_GROUP_LINKS = [
    {
        "resource_type": "azurerm_virtual_network_peering",
        # Which group declares the link, and which it points at. Both are needed
        # because graph parentage cannot be trusted to say which is which.
        "local_attribute": "virtual_network_name",
        "icon": "resource_images/azure/other/peerings.png",
        "remote_attribute": "remote_virtual_network_id",
        "label": "peering",
    },
]


# Nodes whose links always carry traffic both ways, so they are drawn with a
# two-way arrow regardless of which direction Terraform happened to express.
# The internet is a medium rather than a destination - a resource reaching out
# and a user coming in are the same line - and a site-to-site VPN tunnel is
# bidirectional by definition.
AZURE_BIDIRECTIONAL_NODES = ["tv_azurerm_internet", "tv_azure_onprem"]
