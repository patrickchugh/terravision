"""
GCP (Google Cloud Platform) provider configuration for TerraVision.

This module contains all GCP-specific constants and configuration.
Initial minimal viable configuration for Phase 1.
"""

# Consolidated nodes for GCP services
CONSOLIDATED_NODES = [
    {
        "google_compute_firewall": {
            "resource_name": "google_compute_firewall.firewall",
            "import_location": "resource_classes.gcp.security",
            "vpc": True,
        }
    },
    {
        "google_compute_backend_service": {
            "resource_name": "google_compute_backend_service.lb",
            "import_location": "resource_classes.gcp.network",
            "vpc": True,
        }
    },
    {
        "google_dns_managed_zone": {
            "resource_name": "google_dns_managed_zone.dns",
            "import_location": "resource_classes.gcp.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "google_kms_key_ring": {
            "resource_name": "google_kms_key_ring.kms",
            "import_location": "resource_classes.gcp.security",
            "vpc": False,
        }
    },
    {
        "google_logging": {
            "resource_name": "google_logging_project_sink.logging",
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
AUTO_ANNOTATIONS = [
    {"google_dns_managed_zone": {"link": ["tv_gcp_users.users"], "arrow": "reverse"}},
    {
        "google_compute_address": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "forward",
        }
    },
    {
        "google_compute_global_forwarding_rule": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "reverse",
        }
    },
]

# GCP resource variants
NODE_VARIANTS = {
    "google_compute_instance": {"Standard": "google_compute_instance"},
    "google_sql_database_instance": {
        "MYSQL": "google_sql_mysql",
        "POSTGRES": "google_sql_postgres",
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
