"""
GCP (Google Cloud Platform) provider configuration for TerraVision.

This module contains all GCP-specific constants and configuration.
Initial minimal viable configuration for Phase 1.
"""

# Consolidated nodes for GCP services
# Resources with multiple sub-types that should be consolidated to a single icon
CONSOLIDATED_NODES = [
    # Cloud DNS consolidation (zones, records, policies)
    {
        "google_dns_managed_zone": {
            "resource_name": "google_dns_managed_zone.dns",
            "import_location": "resource_classes.gcp.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    # Firewall consolidation (rules grouped)
    {
        "google_compute_firewall": {
            "resource_name": "google_compute_firewall.firewall",
            "import_location": "resource_classes.gcp.security",
            "vpc": True,
        }
    },
    # Load Balancer consolidation (backend service + forwarding rules + url maps)
    {
        "google_compute_backend_service": {
            "resource_name": "google_compute_backend_service.lb",
            "import_location": "resource_classes.gcp.network",
            "vpc": True,
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

# GCP group/container nodes
GROUP_NODES = [
    "google_compute_network",
    "google_compute_subnetwork",
    "google_project",
]

# GCP edge services
EDGE_NODES = [
    "google_dns_managed_zone",
    "google_compute_global_forwarding_rule",
    "google_compute_url_map",
]

# Nodes outside cloud boundary
OUTER_NODES = ["tv_gcp_users", "tv_gcp_internet"]

# Draw order
DRAW_ORDER = [
    OUTER_NODES,
    EDGE_NODES,
    GROUP_NODES,
    CONSOLIDATED_NODES,
    [""],
]

# Auto-annotations for GCP
# Automatically creates connections and annotations for common patterns
AUTO_ANNOTATIONS = [
    # Cloud DNS connected to external users
    {
        "google_dns_managed_zone": {
            "link": ["tv_gcp_users.users"],
            "arrow": "reverse",
        }
    },
    # External IP addresses connected to internet
    {
        "google_compute_address": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "forward",
        }
    },
    # Global forwarding rules (load balancers) connected to internet
    {
        "google_compute_global_forwarding_rule": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
    # GKE clusters create implicit service connection
    {
        "google_container_cluster": {
            "link": ["google_container_service.gke"],
            "arrow": "reverse",
        }
    },
    # NAT gateway connections
    {
        "google_compute_router_nat": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "forward",
        }
    },
    # Cloud CDN connections
    {
        "google_compute_backend_bucket": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
    # Cloud Armor (security policies)
    {
        "google_compute_security_policy": {
            "link": ["google_compute_backend_service.*"],
            "arrow": "forward",
        }
    },
    # Cloud Run services exposed externally
    {
        "google_cloud_run_service": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
]

# GCP resource variants
# Maps resource types to different variants based on metadata keywords
NODE_VARIANTS = {
    # Compute Instance variants based on machine type
    "google_compute_instance": {
        "n1-standard": "google_compute_instance_standard",
        "n1-highmem": "google_compute_instance_memory",
        "n1-highcpu": "google_compute_instance_cpu",
        "e2-": "google_compute_instance_e2",
        "n2-": "google_compute_instance_n2",
        "c2-": "google_compute_instance_c2",
        "m1-": "google_compute_instance_memory",
    },
    # Storage Bucket variants based on storage class
    "google_storage_bucket": {
        "STANDARD": "google_storage_standard",
        "NEARLINE": "google_storage_nearline",
        "COLDLINE": "google_storage_coldline",
        "ARCHIVE": "google_storage_archive",
    },
    # Cloud SQL variants based on tier and database type
    "google_sql_database_instance": {
        "POSTGRES": "google_sql_postgres",
        "MYSQL": "google_sql_mysql",
        "SQLSERVER": "google_sql_sqlserver",
        "db-f1-micro": "google_sql_micro",
        "db-n1-standard": "google_sql_standard",
        "db-n1-highmem": "google_sql_highmem",
    },
    # GKE variants based on release channel
    "google_container_cluster": {
        "RAPID": "google_gke_rapid",
        "REGULAR": "google_gke_regular",
        "STABLE": "google_gke_stable",
        "UNSPECIFIED": "google_gke_unspecified",
    },
    # Load Balancer variants
    "google_compute_backend_service": {
        "EXTERNAL": "google_lb_external",
        "INTERNAL": "google_lb_internal",
        "INTERNAL_MANAGED": "google_lb_internal_managed",
    },
    # Cloud Function variants based on runtime
    "google_cloudfunctions_function": {
        "python": "google_function_python",
        "nodejs": "google_function_nodejs",
        "go": "google_function_go",
        "java": "google_function_java",
    },
    # Cloud Run variants
    "google_cloud_run_service": {
        "cpu-boost": "google_run_boosted",
        "cloudsql": "google_run_sql",
    },
    # Firewall variants based on direction
    "google_compute_firewall": {
        "INGRESS": "google_firewall_ingress",
        "EGRESS": "google_firewall_egress",
    },
    # Redis variants based on tier
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
