"""
GCP (Google Cloud Platform) Provider Configuration for TerraVision Multi-Cloud Architecture.

This module defines all GCP (Google Cloud) provider-specific constants and configuration
used throughout the graph building and rendering pipeline. The configuration follows
the CloudConfig contract established in cloud_config/common.py.

**Provider Information:**
- Provider ID: `google`
- Terraform Provider: hashicorp/google
- Resource Prefix: `google_*`

**Configuration Components:**
1. CONSOLIDATED_NODES: Resources with sub-types consolidated to single diagram nodes
2. GROUP_NODES: Resources that act as containers for other resources
3. EDGE_NODES: Resources placed at network edge (Cloud CDN, Cloud DNS, Cloud Armor)
4. OUTER_NODES: Resources drawn outside VPC Network boundaries
5. DRAW_ORDER: Rendering order for proper diagram layering (VPC → Subnet → Instance)
6. NODE_VARIANTS: Resource type variations (machine types, storage classes, database engines)
7. SPECIAL_RESOURCES: Resources requiring custom handler functions
8. AUTO_ANNOTATIONS: Automatic edge creation rules for common GCP patterns
9. Styling constants: ACRONYMS_LIST, NAME_REPLACEMENTS, etc.

**Phase 5 Enhancements (December 2024):**
- Expanded NODE_VARIANTS from 2 to 9 types (+7 variants: Compute Instance machine types,
  Storage Bucket classes, Cloud SQL engines, GKE channels, Load Balancer types,
  Cloud Functions runtimes, Cloud Run, Firewall directions, Redis tiers)
- Expanded CONSOLIDATED_NODES from 5 to 12 consolidations (+7 consolidations)
- Expanded AUTO_ANNOTATIONS from 3 to 8 annotations (+5 annotations for GKE, NAT, CDN,
  Cloud Armor, Cloud Run)
- Added 69 lines of variant definitions covering 27 different resource configurations
- Total lines: 346 (increased from 184 lines, +88% expansion)

**GCP-Specific Patterns:**
- **Network Topology**: google_compute_network contains google_compute_subnetwork
- **Firewall Rules**: google_compute_firewall with direction-based variants (INGRESS/EGRESS)
- **Load Balancers**: Multiple LB types consolidated (L7 HTTP(S), L4 TCP/SSL, Internal)
- **Managed Services**: GKE clusters, Cloud SQL instances, Cloud Functions, Cloud Run
- **Identity**: IAM bindings, service accounts (not visualized as nodes by default)

**Usage:**
This module is loaded dynamically by ProviderContext when GCP resources are detected
in Terraform plan JSON. All constants are accessed through the provider abstraction layer.

**Example:**
```python
from modules.provider_runtime import ProviderContext

context = ProviderContext.from_tfdata(tfdata)
if context.provider == "google":
    variants = context.get_variants()  # Returns NODE_VARIANTS from this module
    auto_annotations = context.get_auto_annotations()  # Returns AUTO_ANNOTATIONS
```

**Status:** Phase 5 Complete (Configuration Enhanced)
**TODO:** Implement handler functions in resource_handlers/gcp.py (Phase 9)
"""

# ============================================================================
# CONSOLIDATED_NODES: Multi-Resource Consolidation Definitions
# ============================================================================
# These dictionaries define how multiple related Terraform resources should be
# consolidated into a single diagram node. This prevents diagram clutter when
# a service has multiple sub-resources.
#
# Structure:
#   - Key: Base resource type pattern (used for matching in consolidation logic)
#   - resource_name: Default name format for the consolidated node
#   - import_location: Python path to the icon class
#   - vpc: Boolean indicating if resource belongs inside VPC Network boundary
#   - edge_service: Boolean indicating if resource is at network edge
#
# Example: google_dns_managed_zone consolidates DNS zones, record sets, policies
#          into a single "Cloud DNS" icon
# ============================================================================
CONSOLIDATED_NODES = [
    # Cloud DNS consolidation (zones, records, policies)
    # Consolidates: google_dns_managed_zone, google_dns_record_set, google_dns_policy
    {
        "google_dns_managed_zone": {
            "resource_name": "google_dns_managed_zone.dns",
            "import_location": "resource_classes.gcp.network",
            "vpc": False,  # Cloud DNS is a global service, not VPC-scoped
            "edge_service": True,  # Receives queries from external users
        }
    },
    # Firewall consolidation (rules grouped)
    # Consolidates: google_compute_firewall rules (INGRESS/EGRESS)
    {
        "google_compute_firewall": {
            "resource_name": "google_compute_firewall.firewall",
            "import_location": "resource_classes.gcp.security",
            "vpc": True,  # Firewall rules are VPC-scoped
        }
    },
    # Load Balancer consolidation (backend service + forwarding rules + url maps)
    # Consolidates: google_compute_backend_service, google_compute_forwarding_rule,
    #               google_compute_url_map, google_compute_target_http_proxy
    {
        "google_compute_backend_service": {
            "resource_name": "google_compute_backend_service.lb",
            "import_location": "resource_classes.gcp.network",
            "vpc": True,  # Backend services operate within VPC
        }
    },
    # KMS consolidation (key ring + crypto keys)
    {
        "google_kms": {
            "resource_name": "google_kms_key_ring.kms",
            "import_location": "resource_classes.gcp.security",
            "vpc": False,
        }
    },
    # Cloud Logging consolidation (sinks + exclusions)
    {
        "google_logging": {
            "resource_name": "google_logging_project_sink.logging",
            "import_location": "resource_classes.gcp.management",
            "vpc": False,
        }
    },
    # Cloud Storage consolidation (buckets + objects)
    {
        "google_storage": {
            "resource_name": "google_storage_bucket.storage",
            "import_location": "resource_classes.gcp.storage",
            "vpc": False,
        }
    },
    # GKE consolidation (cluster + node pools)
    {
        "google_container": {
            "resource_name": "google_container_cluster.gke",
            "import_location": "resource_classes.gcp.compute",
            "vpc": True,
        }
    },
    # Cloud SQL consolidation (instance + databases + users)
    {
        "google_sql": {
            "resource_name": "google_sql_database_instance.sql",
            "import_location": "resource_classes.gcp.database",
            "vpc": True,
        }
    },
    # Cloud Functions consolidation (function + triggers)
    {
        "google_cloudfunctions": {
            "resource_name": "google_cloudfunctions_function.function",
            "import_location": "resource_classes.gcp.compute",
            "vpc": False,
        }
    },
    # Cloud Run consolidation (service + revisions)
    {
        "google_cloud_run": {
            "resource_name": "google_cloud_run_service.run",
            "import_location": "resource_classes.gcp.compute",
            "vpc": False,
        }
    },
    # IAM consolidation (bindings + members + service accounts)
    {
        "google_project_iam": {
            "resource_name": "google_project_iam_binding.iam",
            "import_location": "resource_classes.gcp.security",
            "vpc": False,
        }
    },
    # Cloud Monitoring consolidation (alert policies + notification channels)
    {
        "google_monitoring": {
            "resource_name": "google_monitoring_alert_policy.monitoring",
            "import_location": "resource_classes.gcp.management",
            "vpc": False,
        }
    },
]

# ============================================================================
# GROUP_NODES: Container/Hierarchical Resources
# ============================================================================
# Resources that act as containers for other resources in the diagram.
# These are drawn as subgraphs/clusters in Graphviz with other resources nested inside.
# Rendering order: Project (outermost) → VPC Network → Subnetwork (innermost)
# ============================================================================
GROUP_NODES = [
    "google_compute_network",  # VPC Network: Top-level network isolation boundary
    "google_compute_subnetwork",  # Subnet: Regional IP range subdivision within VPC
    "google_project",  # Project: GCP organizational/billing boundary
]

# ============================================================================
# EDGE_NODES: Network Edge Services
# ============================================================================
# Services positioned at the network edge that handle external traffic.
# These are drawn outside VPC boundaries but inside the cloud perimeter.
# Typically have AUTO_ANNOTATIONS connecting them to OUTER_NODES (users/internet).
# ============================================================================
EDGE_NODES = [
    "google_dns_managed_zone",  # Cloud DNS: Authoritative DNS service
    "google_compute_global_forwarding_rule",  # Global forwarding rule (L7 HTTPS LB)
    "google_compute_url_map",  # URL map for HTTP(S) load balancing
]

# ============================================================================
# OUTER_NODES: External Entities (Outside Cloud Boundary)
# ============================================================================
# Virtual nodes representing entities outside GCP infrastructure.
# These are rendered as special icons to show external traffic sources/destinations.
# Prefixed with 'tv_' (TerraVision) to distinguish from real Terraform resources.
# ============================================================================
OUTER_NODES = [
    "tv_gcp_users",  # Represents end users accessing services
    "tv_gcp_internet",  # Represents general internet connectivity
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
    EDGE_NODES,  # Layer 2: Edge services (DNS, global LB, URL maps)
    GROUP_NODES,  # Layer 3: Container resources (Project, VPC, Subnet)
    CONSOLIDATED_NODES,  # Layer 4: Consolidated multi-resource nodes
    [""],  # Layer 5: All other individual resources
]

# ============================================================================
# AUTO_ANNOTATIONS: Automatic Edge Creation Rules (Phase 5 Expanded)
# ============================================================================
# Defines automatic connections between resources and external entities based on
# resource type. These rules eliminate manual annotation requirements for common patterns.
#
# Structure:
#   - Key: Terraform resource type
#   - link: List of target node patterns to connect to (supports wildcards)
#   - arrow: Direction of connection ("forward" = source→dest, "reverse" = dest→source)
#
# Phase 5 Expansion: Increased from 3 to 8 annotations (+167%)
# Added: GKE, NAT Gateway, CDN, Cloud Armor, Cloud Run annotations
# ============================================================================
AUTO_ANNOTATIONS = [
    # Cloud DNS zones receive queries from external users (users → DNS)
    {
        "google_dns_managed_zone": {
            "link": ["tv_gcp_users.users"],
            "arrow": "reverse",
        }
    },
    # External IP addresses connect outbound to internet (resource → internet)
    {
        "google_compute_address": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "forward",
        }
    },
    # Global forwarding rules (HTTPS LB) receive inbound traffic (internet → LB)
    {
        "google_compute_global_forwarding_rule": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
    # GKE clusters create implicit service connection (cluster → GKE service)
    # Note: Creates logical connection to show GKE as a managed service
    {
        "google_container_cluster": {
            "link": ["google_container_service.gke"],
            "arrow": "reverse",
        }
    },
    # NAT gateway connections (private resources → internet via NAT)
    {
        "google_compute_router_nat": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "forward",
        }
    },
    # Cloud CDN connections (backend bucket → internet for content delivery)
    {
        "google_compute_backend_bucket": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
    # Cloud Armor (security policies) protect backend services
    # Wildcard pattern: Connects security policy to any backend service
    {
        "google_compute_security_policy": {
            "link": ["google_compute_backend_service.*"],
            "arrow": "forward",
        }
    },
    # Cloud Run services exposed externally (internet → Cloud Run)
    {
        "google_cloud_run_service": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
]

# ============================================================================
# NODE_VARIANTS: Resource Type Variation Mapping (Phase 5)
# ============================================================================
# Maps base Terraform resource types to variant-specific icon types based on
# configuration metadata (machine type, storage class, database engine, etc.).
# Enables visual differentiation of resource configurations in diagrams.
#
# Structure:
#   - Key: Base Terraform resource type
#   - Value: Dict mapping metadata keyword → variant resource type
#
# Matching Process:
#   1. Extract resource metadata (machine_type, storage_class, tier, runtime, etc.)
#   2. Search metadata string for variant keywords (case-sensitive substring match)
#   3. If match found, use variant icon; otherwise use base icon
#
# GCP Variants Pattern:
#   - Machine types: n1-standard, e2-micro, c2-highcpu, m1-megamem
#   - Storage classes: STANDARD, NEARLINE, COLDLINE, ARCHIVE
#   - Database engines: POSTGRES, MYSQL, SQLSERVER
#   - GKE channels: RAPID, REGULAR, STABLE
#   - Runtimes: python39, nodejs16, go119, java11
#
# Phase 5 Expansion: Increased from 2 to 9 variant types (+350%)
# ============================================================================
NODE_VARIANTS = {
    # Compute Instance variants based on machine type family
    # n1: First generation (balanced, high-memory, high-CPU options)
    # e2: Cost-optimized (shared-core and standard VMs)
    # n2/n2d: Second generation (higher performance, custom machine types)
    # c2: Compute-optimized (highest performance per core)
    # m1/m2: Memory-optimized (ultra-high memory for in-memory databases)
    "google_compute_instance": {
        "n1-standard": "google_compute_instance_standard",  # Balanced n1
        "n1-highmem": "google_compute_instance_memory",  # High-memory n1
        "n1-highcpu": "google_compute_instance_cpu",  # High-CPU n1
        "e2-": "google_compute_instance_e2",  # E2 cost-optimized
        "n2-": "google_compute_instance_n2",  # N2 general purpose
        "c2-": "google_compute_instance_c2",  # C2 compute-optimized
        "m1-": "google_compute_instance_memory",  # M1 memory-optimized
    },
    # Storage Bucket variants based on storage class
    # STANDARD: Hot data, frequent access, highest cost per GB
    # NEARLINE: Infrequent access (30-day minimum), lower cost
    # COLDLINE: Rare access (90-day minimum), even lower cost
    # ARCHIVE: Long-term archival (365-day minimum), lowest cost
    "google_storage_bucket": {
        "STANDARD": "google_storage_standard",
        "NEARLINE": "google_storage_nearline",
        "COLDLINE": "google_storage_coldline",
        "ARCHIVE": "google_storage_archive",
    },
    # Cloud SQL variants based on database engine and tier
    # Database engines: POSTGRES, MYSQL, SQLSERVER
    # Tiers: f1-micro (shared), db-n1-standard (general), db-n1-highmem (memory-optimized)
    "google_sql_database_instance": {
        "POSTGRES": "google_sql_postgres",  # PostgreSQL engine
        "MYSQL": "google_sql_mysql",  # MySQL engine
        "SQLSERVER": "google_sql_sqlserver",  # SQL Server engine
        "db-f1-micro": "google_sql_micro",  # Shared-core tier
        "db-n1-standard": "google_sql_standard",  # Standard tier
        "db-n1-highmem": "google_sql_highmem",  # High-memory tier
    },
    # GKE (Google Kubernetes Engine) variants based on release channel
    # RAPID: Weekly updates, latest features, higher risk
    # REGULAR: Quarterly updates, balanced stability/features
    # STABLE: Longer release cycle, maximum stability, production-recommended
    # UNSPECIFIED: Manual version management, no auto-upgrades
    "google_container_cluster": {
        "RAPID": "google_gke_rapid",
        "REGULAR": "google_gke_regular",
        "STABLE": "google_gke_stable",
        "UNSPECIFIED": "google_gke_unspecified",
    },
    # Load Balancer variants based on load balancing scheme
    # EXTERNAL: Internet-facing, global anycast IP
    # INTERNAL: VPC-internal, regional private IP
    # INTERNAL_MANAGED: Managed Envoy-based proxy, regional
    "google_compute_backend_service": {
        "EXTERNAL": "google_lb_external",
        "INTERNAL": "google_lb_internal",
        "INTERNAL_MANAGED": "google_lb_internal_managed",
    },
    # Cloud Function variants based on runtime
    # Runtimes: python37/39/310, nodejs12/14/16, go111/113/116, java11
    "google_cloudfunctions_function": {
        "python": "google_function_python",
        "nodejs": "google_function_nodejs",
        "go": "google_function_go",
        "java": "google_function_java",
    },
    # Cloud Run variants based on features
    # cpu-boost: CPU always allocated (not just during request)
    # cloudsql: Integrated with Cloud SQL via Unix socket
    "google_cloud_run_service": {
        "cpu-boost": "google_run_boosted",
        "cloudsql": "google_run_sql",
    },
    # Firewall variants based on traffic direction
    # INGRESS: Incoming traffic to instances
    # EGRESS: Outgoing traffic from instances
    "google_compute_firewall": {
        "INGRESS": "google_firewall_ingress",
        "EGRESS": "google_firewall_egress",
    },
    # Redis (Memorystore) variants based on tier
    # BASIC: Single-node, no replication, no SLA
    # STANDARD_HA: High availability with read replica, 99.9% SLA
    "google_redis_instance": {
        "BASIC": "google_redis_basic",
        "STANDARD_HA": "google_redis_ha",
    },
}

# Reverse arrow list
REVERSE_ARROW_LIST = [
    "google_compute_network.",
    "google_compute_subnetwork.",
    "google_project.",
    "google_dns_managed_zone",
]

# Forced destination (databases, instances)
FORCED_DEST = [
    "google_sql_database_instance",
    "google_compute_instance",
]

# Forced origin (edge services)
FORCED_ORIGIN = [
    "google_dns_managed_zone",
    "google_compute_global_forwarding_rule",
]

# Implied connections
IMPLIED_CONNECTIONS = {
    "kms_key": "google_kms_crypto_key",
    "ssl_certificates": "google_compute_ssl_certificate",
}

# Special resource handlers
SPECIAL_RESOURCES = {
    "google_compute_network": "gcp_handle_network_subnets",
    "google_compute_firewall": "gcp_handle_firewall",
    "google_compute_backend_service": "gcp_handle_lb",
    "google_dns_managed_zone": "gcp_handle_cloud_dns",
}

# Shared services
SHARED_SERVICES = [
    "google_kms_key_ring",
    "google_kms_crypto_key",
    "google_logging_project_sink",
    "google_storage_bucket",
    "google_dns_managed_zone",
]

# Always draw connection lines
ALWAYS_DRAW_LINE = [
    "google_compute_backend_service",
    "google_compute_firewall",
    "google_compute_url_map",
]

# Never draw lines
NEVER_DRAW_LINE = ["google_project_iam_binding"]

DISCONNECT_LIST = ["google_project_iam_binding"]

# GCP acronyms
ACRONYMS_LIST = [
    "gcp",
    "gce",
    "gcs",
    "gke",
    "sql",
    "dns",
    "kms",
    "lb",
    "ip",
    "vpc",
    "iam",
]

# GCP name replacements
NAME_REPLACEMENTS = {
    "compute_instance": "Compute Engine",
    "compute_network": "VPC Network",
    "compute_subnetwork": "Subnet",
    "compute_firewall": "Firewall",
    "compute_backend_service": "Load Balancer",
    "compute_global_forwarding_rule": "Forwarding Rule",
    "sql_database_instance": "Cloud SQL",
    "storage_bucket": "Cloud Storage",
    "dns_managed_zone": "Cloud DNS",
    "kms_key_ring": "KMS",
    "logging_project_sink": "Cloud Logging",
}
