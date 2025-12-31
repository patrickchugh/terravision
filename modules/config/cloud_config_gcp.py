# GCP Cloud Configuration for TerraVision
# Provider: Google Cloud Platform (google provider)
# Architecture: Projects > VPC (Global) > Subnets (Regional) > Resources

# Provider metadata
PROVIDER_NAME = "GCP"
PROVIDER_PREFIX = ["google_"]
ICON_LIBRARY = "gcp"

# Any resource names with certain prefixes are consolidated into one node
GCP_CONSOLIDATED_NODES = [
    {
        "google_compute_firewall": {
            "resource_name": "google_compute_firewall.firewall",
            "import_location": "resource_classes.gcp.network",
            "vpc": True,
            "edge_service": False,
        }
    },
    {
        "google_compute_address": {
            "resource_name": "google_compute_address.external_ip",
            "import_location": "resource_classes.gcp.network",
            "vpc": False,
            "edge_service": False,
        }
    },
    {
        "google_compute_forwarding_rule": {
            "resource_name": "google_compute_forwarding_rule.lb",
            "import_location": "resource_classes.gcp.network",
            "vpc": True,
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

# List of Group type nodes and order to draw them in
# GCP hierarchy: Project > VPC (Global) > Subnet (Regional) > Zone
GCP_GROUP_NODES = [
    "google_project",
    "google_compute_network",
    "google_compute_subnetwork",
    "google_compute_region",
    "google_compute_zone",
    "tv_gcp_onprem",
]

# Nodes to be drawn first inside the GCP Cloud but outside any VPCs
GCP_EDGE_NODES = [
    "google_dns_managed_zone",
    "google_compute_global_forwarding_rule",
    "google_cdn_backend_bucket",
    "google_compute_vpn_gateway",
]

# Nodes outside Cloud boundary
GCP_OUTER_NODES = ["tv_gcp_users", "tv_gcp_internet"]

# Order to draw nodes - leave empty string list till last to denote everything else
GCP_DRAW_ORDER = [
    GCP_OUTER_NODES,
    GCP_EDGE_NODES,
    GCP_GROUP_NODES,
    GCP_CONSOLIDATED_NODES,
    [""],
]

# List of prefixes where additional nodes should be created automatically
GCP_AUTO_ANNOTATIONS = [
    {"google_dns_managed_zone": {"link": ["tv_gcp_users.users"], "arrow": "reverse"}},
    {
        "google_compute_vpn_gateway": {
            "link": [
                "tv_gcp_onprem.corporate_datacenter",
            ],
            "arrow": "forward",
        }
    },
    {
        "google_compute_address": {
            "link": ["tv_gcp_internet.internet"],
            "arrow": "forward",
        }
    },
    {
        "google_container_cluster": {
            "link": ["google_container_registry.gcr"],
            "arrow": "forward",
        }
    },
    {
        "google_cloud_run_service": {
            "link": ["google_storage_bucket.artifacts"],
            "arrow": "forward",
        }
    },
    {
        "google_compute_instance": {
            "link": ["google_logging_project_sink.logging"],
            "arrow": "forward",
        }
    },
]

# Variant icons for the same service - matches keyword in meta data and changes resource type
GCP_NODE_VARIANTS = {
    "google_compute_instance": {
        "n1": "google_compute_instance_n1",
        "n2": "google_compute_instance_n2",
    },
    "google_sql_database_instance": {
        "mysql": "google_sql_mysql",
        "postgres": "google_sql_postgres",
    },
}

# Automatically reverse arrow direction for these resources when discovered through source
GCP_REVERSE_ARROW_LIST = [
    "google_dns_managed_zone",
    "google_compute_network.",
    "google_compute_subnetwork.",
    "google_project.",
    "google_compute_firewall.",
]

# Force certain resources to be a destination connection only - original TF node relationships only
GCP_FORCED_DEST = [
    "google_sql_database_instance",
    "google_compute_instance",
    "google_storage_bucket",
]

# Force certain resources to be a origin connection only - original TF node relationships only
GCP_FORCED_ORIGIN = ["google_dns_managed_zone", "google_compute_global_forwarding_rule"]

GCP_IMPLIED_CONNECTIONS = {
    "kms_key_name": "google_kms_crypto_key",
    "service_account": "google_service_account",
}

# Special resources that need custom handling
# TODO: Migrate to config-driven approach like AWS (see resource_handler_configs_google.py)
# For now, keeping manual dict until GCP handlers are refactored
from modules.config.resource_handler_configs_google import RESOURCE_HANDLER_CONFIGS

# Generate from config if available, otherwise use manual dict
if RESOURCE_HANDLER_CONFIGS:
    GCP_SPECIAL_RESOURCES = {
        pattern: config.get("additional_handler_function", f"config_handler_{pattern}")
        for pattern, config in RESOURCE_HANDLER_CONFIGS.items()
    }
else:
    # Manual dict (legacy - will be removed once handlers are migrated)
    GCP_SPECIAL_RESOURCES = {
        "google_project": "gcp_handle_project",
        "google_compute_network": "gcp_handle_vpc",
        "google_compute_subnetwork": "gcp_handle_subnet",
        "google_compute_firewall": "gcp_handle_firewall",
        "google_container_cluster": "gcp_handle_gke",
        "google_compute_instance_group": "gcp_handle_instance_group",
        "google_compute_backend_service": "gcp_handle_backend_service",
        "google_": "gcp_handle_sharedgroup",
        "random_string": "random_string_handler",
    }

GCP_SHARED_SERVICES = [
    "google_kms_key_ring",
    "google_logging_project_sink",
    "google_monitoring_dashboard",
    "google_container_registry",
    "google_secret_manager_secret",
]

GCP_ALWAYS_DRAW_LINE = [
    "google_compute_forwarding_rule",
    "google_compute_backend_service",
    "google_container_node_pool",
    "google_compute_instance_group",
]

GCP_NEVER_DRAW_LINE = ["google_project_iam_member"]

GCP_DISCONNECT_LIST = ["google_project_iam_member"]

GCP_ACRONYMS_LIST = [
    "gcp",
    "gce",
    "gcs",
    "gke",
    "gcr",
    "vpc",
    "ip",
    "lb",
    "sql",
    "kms",
    "iam",
    "api",
    "vm",
]

GCP_NAME_REPLACEMENTS = {
    "compute_instance": "VM Instance",
    "compute_network": "VPC",
    "compute_subnetwork": "Subnet",
    "compute_firewall": "Firewall Rule",
    "compute_address": "External IP",
    "container_cluster": "GKE Cluster",
    "storage_bucket": "Cloud Storage",
    "sql_database_instance": "Cloud SQL",
    "kms_key_ring": "KMS",
    "pubsub_topic": "Pub/Sub",
    "bigquery_dataset": "BigQuery",
    "cloud_run_service": "Cloud Run",
    "cloudfunctions_function": "Cloud Function",
    "service_account": "Service Account",
    "this": "",
}

GCP_REFINEMENT_PROMPT = """
You are an expert GCP Solutions Architect. I have a JSON representation of a GCP architecture diagram generated from Terraform code. The diagram may have incorrect resource groupings, missing connections, or layout issues.
INPUT JSON FORMAT: Each key is a Terraform resource ID, and its value is a list of resource IDs it connects to.
SPECIAL CONVENTIONS:
- Resources starting with "tv_" are visual helper nodes (e.g., "tv_gcp_internet.internet" represents the public internet)
- Projects are top-level containers for all GCP resources
- VPCs (Virtual Private Clouds) are global network containers
- Subnets are regional network segments within VPCs
- Firewall Rules are applied at the VPC level
- Zones represent physical data center locations
- Resources ending with ~1, ~2, ~3 (instance number) indicate multiple instances or multi-zone deployments

Please refine this diagram following GCP conventions and industry best practices:
1. Fix resource groupings (Project > VPC > Subnet > Zone > Resources)
2. Add missing logical connections between resources
3. Remove incorrect connections
4. Ensure proper hierarchy and containment
5. Group related resources (e.g., GKE nodes with node pools, Load Balancers with backend services)
6. Add implied connections (e.g., Compute Instances to Cloud Storage, Cloud Run to Artifact Registry)
7. Ensure Firewall Rules are associated with VPCs
8. Group shared services (KMS, Logging, Monitoring, GCR) separately
9. VPN Gateways should connect to on-premises representations
10. External IPs should connect to internet boundary
11. GKE clusters should show connections to GCR and Cloud Storage
12. Consider regional vs global resources (Cloud Storage is global, Subnets are regional)

"""

GCP_DOCUMENTATION_PROMPT = """\
You are a GCP architect that needs to summarise this JSON of Terraform GCP resources and their associations concisely in paragraph form using as few bullet points as possible. Follow these instructions:
1. If you see ~1, ~2, ~3 etc at the end of the resource name it means multiple instances of the same resource are created. Include how many of each resource type are created in the summary.
2. Use only GCP resource names in the text which can be inferred from terraform resource type names. e.g. instead of google_compute_instance.XXX just say a Compute Engine Instance named XXX
3. Mention which resources are associated with each respective Project, VPC, Subnet, and Zone if any.
4. Provide an overall summary of the architecture and what the system does

"""

# Configuration patterns for multi-instance resource detection
# Each pattern defines:
# - resource_types: List of Terraform resource types to check
# - trigger_attributes: Attributes that trigger expansion (e.g., "subnets", "zones")
# - also_expand_attributes: Attributes containing related resources to also expand
# - resource_pattern: Regex pattern to extract resource references from attribute values
GCP_MULTI_INSTANCE_PATTERNS = [
    {
        "resource_types": [
            "google_compute_instance_group_manager",
            "google_compute_region_instance_group_manager",
        ],
        "trigger_attributes": ["zones", "target_pools"],
        "also_expand_attributes": [],
        "resource_pattern": r'"([^"]+)"',
        "description": "GCP Instance Group Manager with multiple zones",
    },
    {
        "resource_types": ["google_compute_forwarding_rule"],
        "trigger_attributes": ["target"],
        "also_expand_attributes": [],
        "resource_pattern": r"\$\{(google_\w+\.\w+)",
        "description": "GCP Forwarding Rule with target pool",
    },
    # Add more GCP patterns as needed
]

# Replace with your OLLAMA server IP and port number
OLLAMA_HOST = "http://localhost:11434"

# Replace with your actual API Gateway endpoint
BEDROCK_API_ENDPOINT = (
    "https://yirz70b5mc.execute-api.us-east-1.amazonaws.com/prod/chat"
)
