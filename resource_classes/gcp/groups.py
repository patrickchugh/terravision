"""
GCP Grouping Zones following TerraVision's Terraform-centric hierarchy.

NOTE: TerraVision uses a Terraform-centric hierarchy that differs from GCP's
official 2024 guidelines. In Terraform, subnets are regional resources that
contain instances across multiple zones. Our hierarchy reflects this:
  Project > VPC > Region > Subnet > Zone > Resources

GCP's 2024 guidelines use Zone > Subnet, but this doesn't match how
Terraform resources are naturally structured.

Styling follows Google Cloud reference architecture diagrams:
- Cloud boundary: solid Google blue (#1A73E8) with white monochrome logo top-left
- Regions: white fill with solid dark border
- VPC networks: transparent fill with thick black squared border
- Other zones: light blue or light green fill with dashed dark blue/green border
- Text-only labels at top-left (no icons next to labels)

Zone Types (20 total):
- Top-level: User, System, Project, Account
- Within User/System: InfraSystem, OnPremises
- Within System: ExternalSaaS, ExternalData, External3rdParty, External1stParty
- Within Project: LogicalGroup, Region, KubernetesCluster, VPCNetwork
- Within Region/LogicalGroup: SubNetwork (regional resource)
- Within SubNetwork: Zone (Availability Zone), Firewall
- Within Firewall: InstanceGroup
- Within InstanceGroup: ReplicaPool
- Within K8s: Pod
- Any level: OptionalComponent (dashed blue border)
"""

import sys
import os
from pathlib import Path
from resource_classes import Cluster

defaultdir = "LR"
base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent

# Label padding for better visual spacing from zone edges
LABEL_PADDING = "\n  "  # Newline for top padding + 2 spaces for left padding

# Palette taken from Google Cloud reference architecture diagrams
GOOGLE_BLUE = "#1A73E8"  # Cloud boundary fill
BLUE_BORDER = "#174EA6"  # Dark blue dashed group border
BLUE_FILL = "#E4EEFD"  # Light blue group fill (#AECBFA tint)
GREEN_BORDER = "#0D652D"  # Dark green dashed group border
GREEN_FILL = "#E8F4EB"  # Light green group fill (#CFE9D7 tint)
INK = "#202124"  # Google grey 900 (labels, region border)


def _gcp_zone_attrs(
    fillcolor: str = "none",
    pencolor: str = "none",
    dashed: bool = False,
    rounded: bool = True,
    penwidth: str = "3",
) -> dict:
    """
    Generate Graphviz attributes for GCP architecture diagram zones.

    Args:
        fillcolor: Hex color for the zone background ("none" = transparent)
        pencolor: Hex color for the zone border ("none" = no border)
        dashed: If True, use dashed border style
        rounded: If False, use squared corners (e.g. VPC networks)
        penwidth: Border thickness in points (ignored when pencolor is "none")

    Returns:
        Dict of Graphviz graph attributes
    """
    style_parts = []
    if dashed:
        style_parts.append("dashed")
    if rounded:
        style_parts.append("rounded")
    if fillcolor != "none":
        style_parts.append("filled")
    return {
        "style": ",".join(style_parts) if style_parts else "solid",
        "fillcolor": fillcolor,
        "pencolor": pencolor,
        "penwidth": "0" if pencolor == "none" else penwidth,
        "labeljust": "l",
        "labelloc": "t",
        "margin": "70",  # Padding between nodes and cluster edges
        "rank": "same",
        "fontsize": "32",
        "fontname": "Sans-Serif",
        "fontcolor": INK,
    }


def _gcp_blue_group_attrs() -> dict:
    """Light blue zone with dashed dark blue border."""
    return _gcp_zone_attrs(BLUE_FILL, BLUE_BORDER, dashed=True)


def _gcp_green_group_attrs() -> dict:
    """Light green zone with dashed dark green border."""
    return _gcp_zone_attrs(GREEN_FILL, GREEN_BORDER, dashed=True)


# =============================================================================
# Top-Level Zones
# =============================================================================


class GCPGroup(Cluster):
    """GCP Cloud boundary (solid Google blue with white monochrome logo)."""

    def __init__(self, label="Google Cloud", **kwargs):
        # Solid Google blue fill with thin black border
        attrs = _gcp_zone_attrs(GOOGLE_BLUE, "#000000", penwidth="2")
        attrs["_cloudgroup"] = "1"
        attrs["margin"] = "100"
        attrs["fontcolor"] = "#FFFFFF"  # White text on blue background
        # HTML label with white monochrome GCP logo (logo already says "Google Cloud")
        # Logo is 1920x340 (~5.65:1 ratio), scale proportionally to ~180x32
        logo_path = f"{base_path}/resource_images/gcp/gcp_white.png"
        html_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><IMG SRC="{logo_path}" SCALE="TRUE" WIDTH="180" HEIGHT="32"/></TD></TR></TABLE>>'
        attrs["labelloc"] = "t"
        attrs["labeljust"] = "l"  # Logo at top-left
        super().__init__(html_label, defaultdir, attrs)


class ProjectZone(Cluster):
    """GCP Project Zone / Cloud Service Provider boundary (light blue, dashed)."""

    def __init__(self, label="Project", **kwargs):
        attrs = _gcp_blue_group_attrs()
        # Center the label at top (don't use _shift which forces top-left)
        attrs["labeljust"] = "c"
        super().__init__(label, defaultdir, attrs)


class AccountZone(Cluster):
    """GCP Account / Billing boundary (light blue, dashed)."""

    def __init__(self, label="Account", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class UserZone(Cluster):
    """User area to clarify user pathways (light blue, dashed)."""

    def __init__(self, label="User", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class SystemZone(Cluster):
    """Primary system boundary (light green, dashed)."""

    def __init__(self, label="System", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within User/System Zones
# =============================================================================


class InfraSystemZone(Cluster):
    """Secondary infrastructure grouping (light blue, dashed)."""

    def __init__(self, label="Infrastructure", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class OnPremisesZone(Cluster):
    """Colocation / Data Center / On-premises infrastructure (light green, dashed)."""

    def __init__(self, label="On-Premises", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within System Zones (External Services)
# =============================================================================


class ExternalSaaSZone(Cluster):
    """Third-party SaaS services (light green, dashed)."""

    def __init__(self, label="External SaaS", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class ExternalDataZone(Cluster):
    """External data sources (light green, dashed)."""

    def __init__(self, label="External Data", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class External3rdPartyZone(Cluster):
    """Third-party external infrastructure (light blue, dashed)."""

    def __init__(self, label="External 3rd Party", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class External1stPartyZone(Cluster):
    """First-party external infrastructure (light blue, dashed)."""

    def __init__(self, label="External 1st Party", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Project Zones
# =============================================================================


class LogicalGroupZone(Cluster):
    """Logical grouping of services / instances (light blue, dashed)."""

    def __init__(self, label="Services", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class RegionZone(Cluster):
    """GCP Region boundary (white fill, solid dark border)."""

    def __init__(self, label="Region", **kwargs):
        attrs = _gcp_zone_attrs("#FFFFFF", INK, penwidth="2")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class KubernetesClusterZone(Cluster):
    """Kubernetes / GKE cluster boundary (light blue, dashed)."""

    def __init__(self, label="Kubernetes Cluster", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class VPCNetworkZone(Cluster):
    """VPC Network boundary (transparent fill, thick black squared border)."""

    def __init__(self, label="VPC Network", **kwargs):
        attrs = _gcp_zone_attrs("none", "#000000", rounded=False, penwidth="4")
        # VPC sits directly on the solid blue cloud boundary, so the
        # transparent fill needs a white label to stay readable
        attrs["fontcolor"] = "#FFFFFF"
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Region/LogicalGroup Zones
# =============================================================================


class AvailabilityZone(Cluster):
    """GCP Zone / Availability Zone (light green, dashed)."""

    def __init__(self, label="Zone", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Zone
# =============================================================================


class SubNetworkZone(Cluster):
    """VPC Subnet (light blue, dashed)."""

    def __init__(self, label="Subnet", **kwargs):
        attrs = _gcp_blue_group_attrs()
        # Don't use _shift - it causes label position conflicts for sibling subnets
        # Instead rely on Graphviz's default label positioning with explicit labeljust/labelloc
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class FirewallZone(Cluster):
    """Firewall rules boundary (light green, dashed)."""

    def __init__(self, label="Firewall", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Firewall / Instance Group
# =============================================================================


class InstanceGroupZone(Cluster):
    """Managed/unmanaged instance group (light blue, dashed)."""

    def __init__(self, label="Instance Group", **kwargs):
        attrs = _gcp_blue_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class ReplicaPoolZone(Cluster):
    """Replica set boundary (light green, dashed)."""

    def __init__(self, label="Replica Pool", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Kubernetes Cluster
# =============================================================================


class PodZone(Cluster):
    """Kubernetes pod (light green, dashed)."""

    def __init__(self, label="Pod", **kwargs):
        attrs = _gcp_green_group_attrs()
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Special Zones
# =============================================================================


class OptionalComponentZone(Cluster):
    """Optional component with dashed dark blue border, white fill."""

    def __init__(self, label="Optional", **kwargs):
        attrs = _gcp_zone_attrs("#FFFFFF", BLUE_BORDER, dashed=True)
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Terraform Resource Aliases
# =============================================================================

# Project and Account
google_project = ProjectZone
tv_gcp_account = AccountZone

# Network resources
google_compute_network = VPCNetworkZone
google_compute_subnetwork = SubNetworkZone
google_compute_firewall = FirewallZone

# Synthetic grouping nodes (tv_ prefix = TerraVision-generated, not real TF resources)
# These are created by resource handlers to insert hierarchy into flat graphdict
tv_gcp_region = RegionZone  # Synthetic region nodes for grouping subnets
tv_gcp_zone = AvailabilityZone  # Synthetic zone nodes for grouping instances

# Compute resources
google_compute_instance_group = InstanceGroupZone
# Note: IGM aliases moved to compute.py since they render as regular nodes (like load balancers)

# Kubernetes resources
google_container_cluster = KubernetesClusterZone
google_container_node_pool = InstanceGroupZone
tv_gcp_k8s_pod = PodZone

# Virtual grouping helpers (tv_ prefix = TerraVision virtual nodes)
tv_gcp_users = UserZone
tv_gcp_system = SystemZone
tv_gcp_infra_system2 = InfraSystemZone
tv_gcp_external_saas = ExternalSaaSZone
tv_gcp_external_data = ExternalDataZone
tv_gcp_onprem = OnPremisesZone
tv_gcp_external_3p = External3rdPartyZone
tv_gcp_external_1p = External1stPartyZone
tv_gcp_logical_group = LogicalGroupZone
tv_gcp_replica_pool = ReplicaPoolZone
tv_gcp_optional = OptionalComponentZone
tv_gcp_load_balancer = SystemZone  # Groups LB components (forwarding_rule, proxy, url_map, backend_service, health_check)

# Legacy compatibility aliases (internal use only)
gcp_group = GCPGroup
gcp_vpc = VPCNetworkZone
gcp_subnet = SubNetworkZone
gcp_region = RegionZone  # For legacy code referencing region zones
gcp_zone = AvailabilityZone  # For legacy code referencing availability zones
gcp_az = AvailabilityZone
