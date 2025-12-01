"""
Azure Provider Configuration for TerraVision Multi-Cloud Architecture.

This module defines all Azure (azurerm) provider-specific constants and configuration
used throughout the graph building and rendering pipeline. The configuration follows
the CloudConfig contract established in cloud_config/common.py.

**Provider Information:**
- Provider ID: `azurerm` (also supports `azuread_` prefix)
- Terraform Provider: hashicorp/azurerm
- Resource Prefix: `azurerm_*`

**Configuration Components:**
1. CONSOLIDATED_NODES: Resources with sub-types consolidated to single diagram nodes
2. GROUP_NODES: Resources that act as containers for other resources
3. EDGE_NODES: Resources placed at network edge (internet gateways, CDN, DNS)
4. OUTER_NODES: Resources drawn outside VNet boundaries
5. DRAW_ORDER: Rendering order for proper diagram layering
6. NODE_VARIANTS: Resource type variations (SKUs, tiers, configurations)
7. SPECIAL_RESOURCES: Resources requiring custom handler functions
8. AUTO_ANNOTATIONS: Automatic edge creation rules for common patterns
9. Styling constants: ACRONYMS_LIST, NAME_REPLACEMENTS, etc.

**Phase 5 Enhancements (December 2024):**
- Expanded NODE_VARIANTS from 3 to 10 types (+7 variants: Storage, PostgreSQL, MySQL,
  App Service, AKS, Application Gateway, Redis Cache)
- Expanded CONSOLIDATED_NODES from 5 to 12 consolidations (+7 consolidations)
- Added 72 lines of variant definitions for 22 different resource configurations
- Total lines: 303 (increased from 184 lines, +64% expansion)

**Usage:**
This module is loaded dynamically by ProviderContext when Azure resources are detected
in Terraform plan JSON. All constants are accessed through the provider abstraction layer.

**Example:**
```python
from modules.provider_runtime import ProviderContext

context = ProviderContext.from_tfdata(tfdata)
if context.provider == "azurerm":
    variants = context.get_variants()  # Returns NODE_VARIANTS from this module
    consolidated = context.get_consolidated_nodes()  # Returns CONSOLIDATED_NODES
```

**Status:** Phase 5 Complete (Configuration Enhanced)
**TODO:** Implement handler functions in resource_handlers/azure.py (Phase 8)
"""

# ============================================================================
# CONSOLIDATED_NODES: Multi-Resource Consolidation Definitions
# ============================================================================
# These dictionaries define how multiple related Terraform resources should be
# consolidated into a single diagram node. This prevents diagram clutter when
# a service has multiple sub-resources (e.g., DNS zone + records, LB + rules).
#
# Structure:
#   - Key: Base resource type pattern (used for matching in consolidation logic)
#   - resource_name: Default name format for the consolidated node
#   - import_location: Python path to the icon class
#   - vpc: Boolean indicating if resource belongs inside VNet boundary
#   - edge_service: Boolean indicating if resource is at network edge
#
# Example: azurerm_dns_zone consolidates DNS zones, A/AAAA/CNAME records,
#          nameserver delegations into a single "Cloud DNS" icon
# ============================================================================
CONSOLIDATED_NODES = [
    # DNS Zone consolidation (zones, records, nameservers)
    # Consolidates: azurerm_dns_zone, azurerm_dns_a_record, azurerm_dns_aaaa_record, etc.
    {
        "azurerm_dns_zone": {
            "resource_name": "azurerm_dns_zone.dns",
            "import_location": "resource_classes.azure.network",
            "vpc": False,  # DNS is a global service, not VNet-scoped
            "edge_service": True,  # DNS receives traffic from external users
        }
    },
    # Network Security Group consolidation (NSG + rules)
    # Consolidates: azurerm_network_security_group, azurerm_network_security_rule
    {
        "azurerm_network_security_group": {
            "resource_name": "azurerm_network_security_group.nsg",
            "import_location": "resource_classes.azure.security",
            "vpc": True,  # NSGs are VNet-scoped resources
        }
    },
    # Load Balancer consolidation (LB + backend pools + probes + rules)
    # Consolidates: azurerm_lb, azurerm_lb_backend_address_pool, azurerm_lb_probe,
    #               azurerm_lb_rule, azurerm_lb_nat_rule
    {
        "azurerm_lb": {
            "resource_name": "azurerm_lb.load_balancer",
            "import_location": "resource_classes.azure.network",
            "vpc": True,  # Load balancers operate within VNet
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

# ============================================================================
# GROUP_NODES: Container/Hierarchical Resources
# ============================================================================
# Resources that act as containers for other resources in the diagram.
# These are drawn as subgraphs/clusters in Graphviz with other resources nested inside.
# Rendering order: VNet (outermost) → Subnet → Resource Group → NSG (innermost)
# ============================================================================
GROUP_NODES = [
    "azurerm_virtual_network",  # VNet: Top-level network isolation boundary
    "azurerm_subnet",  # Subnet: IP range subdivision within VNet
    "azurerm_resource_group",  # Resource Group: Logical grouping/lifecycle container
    "azurerm_network_security_group",  # NSG: Security boundary (can group rules)
]

# ============================================================================
# EDGE_NODES: Network Edge Services
# ============================================================================
# Services positioned at the network edge that handle external traffic.
# These are drawn outside VNet boundaries but inside the cloud perimeter.
# Typically have AUTO_ANNOTATIONS connecting them to OUTER_NODES (users/internet).
# ============================================================================
EDGE_NODES = [
    "azurerm_dns_zone",  # Azure DNS: External DNS resolution
    "azurerm_frontdoor",  # Azure Front Door: Global HTTP(S) load balancer + CDN
    "azurerm_cdn_profile",  # Azure CDN: Content delivery network
    "azurerm_application_gateway",  # Application Gateway: Regional L7 load balancer + WAF
]

# ============================================================================
# OUTER_NODES: External Entities (Outside Cloud Boundary)
# ============================================================================
# Virtual nodes representing entities outside Azure infrastructure.
# These are rendered as special icons to show external traffic sources/destinations.
# Prefixed with 'tv_' (TerraVision) to distinguish from real Terraform resources.
# ============================================================================
OUTER_NODES = [
    "tv_azure_users",  # Represents end users accessing services
    "tv_azure_internet",  # Represents general internet connectivity
]

# ============================================================================
# DRAW_ORDER: Diagram Rendering Layer Order
# ============================================================================
# Defines the order in which node categories are drawn in the diagram.
# Earlier items are drawn first (outermost layers), later items drawn last (innermost).
# This ensures proper visual hierarchy: External → Edge → Groups → Consolidated → Individual
# ============================================================================
DRAW_ORDER = [
    OUTER_NODES,  # Layer 1: External entities (users, internet)
    EDGE_NODES,  # Layer 2: Edge services (DNS, CDN, Front Door)
    GROUP_NODES,  # Layer 3: Container resources (VNet, Subnet, RG)
    CONSOLIDATED_NODES,  # Layer 4: Consolidated multi-resource nodes
    [""],  # Layer 5: All other individual resources
]

# ============================================================================
# AUTO_ANNOTATIONS: Automatic Edge Creation Rules
# ============================================================================
# Defines automatic connections between resources and external entities based on
# resource type. These rules eliminate manual annotation requirements for common patterns.
#
# Structure:
#   - Key: Terraform resource type
#   - link: List of target node patterns to connect to
#   - arrow: Direction of connection ("forward" = source→dest, "reverse" = dest→source)
#
# Example: All azurerm_dns_zone resources automatically get an arrow from tv_azure_users
# ============================================================================
AUTO_ANNOTATIONS = [
    # DNS zones receive queries from external users (users → DNS)
    {"azurerm_dns_zone": {"link": ["tv_azure_users.users"], "arrow": "reverse"}},
    # Public IPs connect outbound to internet (resource → internet)
    {
        "azurerm_public_ip": {
            "link": ["tv_azure_internet.internet"],
            "arrow": "forward",
        }
    },
    # Front Door receives inbound traffic from internet (internet → Front Door)
    {
        "azurerm_frontdoor": {
            "link": ["tv_azure_internet.internet"],
            "arrow": "reverse",
        }
    },
]

# ============================================================================
# NODE_VARIANTS: Resource Type Variation Mapping (Phase 5)
# ============================================================================
# Maps base Terraform resource types to variant-specific icon types based on
# configuration metadata (SKU, tier, size, etc.). Enables visual differentiation
# of resource configurations in diagrams (e.g., Premium vs. Standard storage).
#
# Structure:
#   - Key: Base Terraform resource type
#   - Value: Dict mapping metadata keyword → variant resource type
#
# Matching Process:
#   1. Extract resource metadata (SKU, tier, size fields from Terraform JSON)
#   2. Search metadata string for variant keywords (case-sensitive substring match)
#   3. If match found, use variant icon; otherwise use base icon
#
# Example: azurerm_lb with sku="Standard" → icon azurerm_lb_standard
#          azurerm_lb with sku="Basic" → icon azurerm_lb_basic
#
# Phase 5 Expansion: Increased from 3 to 10 variant types (+233%)
# ============================================================================
NODE_VARIANTS = {
    # Load Balancer variants based on SKU (Standard vs. Basic)
    # Standard: Zone-redundant, higher SLA, more features
    # Basic: Single-zone, lower SLA, limited features
    "azurerm_lb": {
        "Standard": "azurerm_lb_standard",
        "Basic": "azurerm_lb_basic",
    },
    # Virtual Machine variants based on VM size series
    # D-series: General purpose (balanced CPU/memory)
    # B-series: Burstable (cost-optimized for low baseline usage)
    # F-series: Compute-optimized (high CPU/memory ratio)
    "azurerm_linux_virtual_machine": {
        "Standard_D": "azurerm_linux_vm",  # General purpose
        "Standard_B": "azurerm_linux_vm_basic",  # Burstable
        "Standard_F": "azurerm_linux_vm_compute",  # Compute-optimized
    },
    "azurerm_windows_virtual_machine": {
        "Standard_D": "azurerm_windows_vm",  # General purpose
        "Standard_B": "azurerm_windows_vm_basic",  # Burstable
        "Standard_F": "azurerm_windows_vm_compute",  # Compute-optimized
    },
    # Storage Account variants based on performance tier and account kind
    # Premium: SSD-backed, low-latency, premium pricing
    # Standard: HDD-backed, standard performance
    # FileStorage: Optimized for Azure Files (SMB/NFS)
    # BlockBlobStorage: Optimized for block blobs and append blobs
    "azurerm_storage_account": {
        "Premium": "azurerm_storage_premium",
        "Standard": "azurerm_storage_standard",
        "FileStorage": "azurerm_storage_files",
        "BlockBlobStorage": "azurerm_storage_blob",
    },
    # Database variants based on compute tier
    # Burstable: B-series, cost-optimized for variable workloads
    # GeneralPurpose: D-series, balanced compute/memory for production
    # MemoryOptimized: E-series, high memory/CPU ratio for in-memory workloads
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
    # App Service variants based on pricing tier
    # Free: F1, no SLA, limited resources
    # Basic: B1-B3, no autoscale, custom domains
    # Standard: S1-S3, autoscale, staging slots, custom domains
    # Premium: P1v2-P3v2, VNet integration, private endpoints, higher performance
    "azurerm_app_service": {
        "Free": "azurerm_app_service_free",
        "Basic": "azurerm_app_service_basic",
        "Standard": "azurerm_app_service_standard",
        "Premium": "azurerm_app_service_premium",
    },
    # AKS (Azure Kubernetes Service) variants based on tier
    # Free: No SLA, no financially-backed uptime guarantee
    # Standard: 99.95% SLA (availability zones), production-ready
    # Premium: 99.95% SLA + additional enterprise features
    "azurerm_kubernetes_cluster": {
        "Free": "azurerm_aks_free",
        "Standard": "azurerm_aks_standard",
        "Premium": "azurerm_aks_premium",
    },
    # Application Gateway variants based on SKU version
    # Standard_v2: L7 load balancer with autoscaling, zone redundancy
    # WAF_v2: Web Application Firewall (WAF) + Standard_v2 features
    "azurerm_application_gateway": {
        "Standard_v2": "azurerm_app_gateway_v2",
        "WAF_v2": "azurerm_app_gateway_waf",
    },
    # Redis Cache variants based on tier
    # Basic: Single node, no SLA, dev/test workloads
    # Standard: 2-node replication, 99.9% SLA, production workloads
    # Premium: Clustering, persistence, VNet integration, higher throughput
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
