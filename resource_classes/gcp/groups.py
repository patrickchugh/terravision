"""
GCP Grouping Zones following TerraVision's Terraform-centric hierarchy.

NOTE: TerraVision uses a Terraform-centric hierarchy that differs from GCP's
official 2024 guidelines. In Terraform, subnets are regional resources that
contain instances across multiple zones. Our hierarchy reflects this:
  Project > VPC > Region > Subnet > Zone > Resources

GCP's 2024 guidelines use Zone > Subnet, but this doesn't match how
Terraform resources are naturally structured.

All zones use:
- 2px rounded corners (style="rounded,filled")
- No shadows (Graphviz default)
- Flat overlapping style (pencolor same as fillcolor)
- Text-only labels at top-left (no icons next to labels)
- Exact hex colors from Google 2024 guidelines

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


def _gcp_2024_attrs(fillcolor: str, dashed: bool = False) -> dict:
    """
    Generate Graphviz attributes for GCP 2024 style zones.

    Args:
        fillcolor: Hex color for the zone background
        dashed: If True, use dashed border style (for optional components)

    Returns:
        Dict of Graphviz graph attributes
    """
    style = "dashed,rounded,filled" if dashed else "rounded,filled"
    border_color = "#4284F3" if dashed else "none"
    return {
        "style": style,
        "fillcolor": fillcolor,
        "pencolor": border_color,
        "penwidth": "0",
        "labeljust": "l",
        "labelloc": "t",
        "margin": "70",  # Padding between nodes and cluster edges
        "rank": "same",
        "fontsize": "18",
        "fontname": "Sans-Serif",
        "fontcolor": "#202124",  # Google grey 900
    }


# =============================================================================
# Top-Level Zones
# =============================================================================


class GCPGroup(Cluster):
    """GCP Cloud boundary (legacy compatibility - now uses 2024 styling)."""

    def __init__(self, label="Google Cloud", **kwargs):
        # GCP 2024: Use Project Zone color for cloud boundary
        attrs = _gcp_2024_attrs("#F6F6F6")
        attrs["_cloudgroup"] = "1"
        # Note: Don't set _shift - it moves labels to top-left via shiftLabel.gvpr
        # We want the logo at bottom-right, so use labelloc/labeljust instead
        attrs["margin"] = "100"
        # HTML label with GCP logo only (logo already says "Google Cloud")
        # Logo is 1920x340 (~5.65:1 ratio), scale proportionally to ~180x32
        logo_path = f"{base_path}/resource_images/gcp/gcp.png"
        html_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><IMG SRC="{logo_path}" SCALE="TRUE" WIDTH="180" HEIGHT="32"/></TD></TR></TABLE>>'
        attrs["labelloc"] = "b"
        attrs["labeljust"] = "l"  # Left-justify at bottom
        super().__init__(html_label, defaultdir, attrs)


class ProjectZone(Cluster):
    """GCP Project Zone / Cloud Service Provider boundary (#F6F6F6 light grey)."""

    def __init__(self, label="Project", **kwargs):
        attrs = _gcp_2024_attrs("#F6F6F6")
        # Center the label at top (don't use _shift which forces top-left)
        attrs["labeljust"] = "c"
        super().__init__(label, defaultdir, attrs)


class AccountZone(Cluster):
    """GCP Account / Billing boundary (#E8EAF6 indigo tint)."""

    def __init__(self, label="Account", **kwargs):
        attrs = _gcp_2024_attrs("#E8EAF6")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class UserZone(Cluster):
    """User area to clarify user pathways (#FFFFFF white)."""

    def __init__(self, label="User", **kwargs):
        attrs = _gcp_2024_attrs("#FFFFFF")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class SystemZone(Cluster):
    """Primary system boundary (#F1F8E9 light green)."""

    def __init__(self, label="System", **kwargs):
        attrs = _gcp_2024_attrs("#F1F8E9")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within User/System Zones
# =============================================================================


class InfraSystemZone(Cluster):
    """Secondary infrastructure grouping (#F3E5F5 light purple)."""

    def __init__(self, label="Infrastructure", **kwargs):
        attrs = _gcp_2024_attrs("#F3E5F5")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class OnPremisesZone(Cluster):
    """Colocation / Data Center / On-premises infrastructure (#EFEBE9 light brown)."""

    def __init__(self, label="On-Premises", **kwargs):
        attrs = _gcp_2024_attrs("#EFEBE9")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within System Zones (External Services)
# =============================================================================


class ExternalSaaSZone(Cluster):
    """Third-party SaaS services (#FFEBEE light pink)."""

    def __init__(self, label="External SaaS", **kwargs):
        attrs = _gcp_2024_attrs("#FFEBEE")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class ExternalDataZone(Cluster):
    """External data sources (#FFF8E1 light amber)."""

    def __init__(self, label="External Data", **kwargs):
        attrs = _gcp_2024_attrs("#FFF8E1")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class External3rdPartyZone(Cluster):
    """Third-party external infrastructure (#E0F2F1 light teal)."""

    def __init__(self, label="External 3rd Party", **kwargs):
        attrs = _gcp_2024_attrs("#E0F2F1")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class External1stPartyZone(Cluster):
    """First-party external infrastructure (#E1F5FE light blue)."""

    def __init__(self, label="External 1st Party", **kwargs):
        attrs = _gcp_2024_attrs("#E1F5FE")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Project Zones
# =============================================================================


class LogicalGroupZone(Cluster):
    """Logical grouping of services / instances (#E3F2FD blue tint)."""

    def __init__(self, label="Services", **kwargs):
        attrs = _gcp_2024_attrs("#E3F2FD")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class RegionZone(Cluster):
    """GCP Region boundary (#ECEFF1 blue-grey)."""

    def __init__(self, label="Region", **kwargs):
        attrs = _gcp_2024_attrs("#ECEFF1")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class KubernetesClusterZone(Cluster):
    """Kubernetes / GKE cluster boundary (#FCE4EC pink)."""

    def __init__(self, label="Kubernetes Cluster", **kwargs):
        attrs = _gcp_2024_attrs("#FCE4EC")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class VPCNetworkZone(Cluster):
    """VPC Network boundary - uses Logical Grouping color (#E3F2FD blue tint)."""

    def __init__(self, label="VPC Network", **kwargs):
        attrs = _gcp_2024_attrs("#E3F2FD")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Region/LogicalGroup Zones
# =============================================================================


class AvailabilityZone(Cluster):
    """GCP Zone / Availability Zone (#FFF3E0 light orange)."""

    def __init__(self, label="Zone", **kwargs):
        attrs = _gcp_2024_attrs("#FFF3E0")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Zone
# =============================================================================


class SubNetworkZone(Cluster):
    """VPC Subnet (#EDE7F6 light violet)."""

    def __init__(self, label="Subnet", **kwargs):
        attrs = _gcp_2024_attrs("#EDE7F6")
        # Don't use _shift - it causes label position conflicts for sibling subnets
        # Instead rely on Graphviz's default label positioning with explicit labeljust/labelloc
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class FirewallZone(Cluster):
    """Firewall rules boundary (#FBE9E7 peach)."""

    def __init__(self, label="Firewall", **kwargs):
        attrs = _gcp_2024_attrs("#FBE9E7")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Firewall / Instance Group
# =============================================================================


class InstanceGroupZone(Cluster):
    """Managed/unmanaged instance group (#F9FBE7 lime tint)."""

    def __init__(self, label="Instance Group", **kwargs):
        attrs = _gcp_2024_attrs("#F9FBE7")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


class ReplicaPoolZone(Cluster):
    """Replica set boundary (#E0F7FA cyan tint)."""

    def __init__(self, label="Replica Pool", **kwargs):
        attrs = _gcp_2024_attrs("#E0F7FA")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Within Kubernetes Cluster
# =============================================================================


class PodZone(Cluster):
    """Kubernetes pod (#E8F5E9 mint)."""

    def __init__(self, label="Pod", **kwargs):
        attrs = _gcp_2024_attrs("#E8F5E9")
        super().__init__(LABEL_PADDING + label, defaultdir, attrs)


# =============================================================================
# Special Zones
# =============================================================================


class OptionalComponentZone(Cluster):
    """Optional component with dashed blue border (#4284F3 Google blue, 2pt dashed)."""

    def __init__(self, label="Optional", **kwargs):
        attrs = _gcp_2024_attrs("#FFFFFF", dashed=True)
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
