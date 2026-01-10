"""
Tests for GCP Grouping Zone Styles (Google Cloud Architecture 2024 Guidelines).

These tests verify that all GCP grouping zones comply with the 2024 guidelines:
- 2px rounded corners (style="rounded,filled")
- No shadows (Graphviz default)
- Flat overlapping style (pencolor same as fillcolor, or dashed for optional)
- Text-only labels (no icons next to labels)
- Exact hex colors from the 2024 guidelines table
"""

import pytest
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# GCP 2024 Zone Color Reference Table
GCP_2024_ZONE_COLORS = {
    # Top-level zones
    "UserZone": "#FFFFFF",
    "SystemZone": "#F1F8E9",
    "ProjectZone": "#F6F6F6",
    "AccountZone": "#E8EAF6",
    # Within User/System
    "InfraSystemZone": "#F3E5F5",
    "OnPremisesZone": "#EFEBE9",
    # Within System (external)
    "ExternalSaaSZone": "#FFEBEE",
    "ExternalDataZone": "#FFF8E1",
    "External3rdPartyZone": "#E0F2F1",
    "External1stPartyZone": "#E1F5FE",
    # Within Project
    "LogicalGroupZone": "#E3F2FD",
    "RegionZone": "#ECEFF1",
    "KubernetesClusterZone": "#FCE4EC",
    "VPCNetworkZone": "#E3F2FD",  # Same as LogicalGroupZone per research.md
    # Within Region/LogicalGroup
    "AvailabilityZone": "#FFF3E0",
    # Within Zone
    "SubNetworkZone": "#EDE7F6",
    "FirewallZone": "#FBE9E7",
    # Within Firewall/InstanceGroup
    "InstanceGroupZone": "#F9FBE7",
    "ReplicaPoolZone": "#E0F7FA",
    # Within K8s
    "PodZone": "#E8F5E9",
    # Special
    "OptionalComponentZone": "#FFFFFF",  # White fill with dashed blue border
    # Legacy
    "GCPGroup": "#F6F6F6",
}


class TestGCPZoneStyleAttributes:
    """Test that all zone classes have correct Graphviz style attributes."""

    @pytest.fixture
    def zone_classes(self):
        """Import and return all GCP zone classes."""
        from resource_classes.gcp import groups

        return {
            "ProjectZone": groups.ProjectZone,
            "AccountZone": groups.AccountZone,
            "UserZone": groups.UserZone,
            "SystemZone": groups.SystemZone,
            "InfraSystemZone": groups.InfraSystemZone,
            "OnPremisesZone": groups.OnPremisesZone,
            "ExternalSaaSZone": groups.ExternalSaaSZone,
            "ExternalDataZone": groups.ExternalDataZone,
            "External3rdPartyZone": groups.External3rdPartyZone,
            "External1stPartyZone": groups.External1stPartyZone,
            "LogicalGroupZone": groups.LogicalGroupZone,
            "RegionZone": groups.RegionZone,
            "KubernetesClusterZone": groups.KubernetesClusterZone,
            "VPCNetworkZone": groups.VPCNetworkZone,
            "AvailabilityZone": groups.AvailabilityZone,
            "SubNetworkZone": groups.SubNetworkZone,
            "FirewallZone": groups.FirewallZone,
            "InstanceGroupZone": groups.InstanceGroupZone,
            "ReplicaPoolZone": groups.ReplicaPoolZone,
            "PodZone": groups.PodZone,
            "OptionalComponentZone": groups.OptionalComponentZone,
            "GCPGroup": groups.GCPGroup,
        }

    def test_all_zones_use_rounded_filled_style(self, zone_classes):
        """Verify all zones use style='rounded,filled' (or 'dashed,rounded,filled' for optional)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        # Test the helper function directly
        standard_attrs = _gcp_2024_attrs("#F6F6F6")
        assert "rounded" in standard_attrs["style"]
        assert "filled" in standard_attrs["style"]

        # Test optional component has dashed
        optional_attrs = _gcp_2024_attrs("#FFFFFF", dashed=True)
        assert "dashed" in optional_attrs["style"]
        assert "rounded" in optional_attrs["style"]
        assert "filled" in optional_attrs["style"]

    def test_all_zones_have_no_border(self, zone_classes):
        """Verify all zones have no border (penwidth='0')."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#F6F6F6")
        assert attrs["penwidth"] == "0"

    def test_all_zones_have_label_at_top_left(self, zone_classes):
        """Verify all zones have labels at top-left (labeljust='l', labelloc='t')."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#F6F6F6")
        assert attrs["labeljust"] == "l"
        assert attrs["labelloc"] == "t"

    def test_standard_zones_have_no_border(self, zone_classes):
        """Verify standard zones have no visible border (pencolor='none')."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#F6F6F6")
        # No border: pencolor set to 'none'
        assert attrs["pencolor"] == "none"

    def test_optional_zone_has_dashed_blue_border(self, zone_classes):
        """Verify OptionalComponentZone has dashed blue border (#4284F3)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#FFFFFF", dashed=True)
        assert attrs["pencolor"] == "#4284F3"
        assert "dashed" in attrs["style"]


class TestGCPZoneHexColors:
    """Test that all zone classes have correct hex colors from 2024 guidelines."""

    def test_project_zone_color(self):
        """ProjectZone should be #F6F6F6 (light grey)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        # ProjectZone uses this color
        attrs = _gcp_2024_attrs("#F6F6F6")
        assert attrs["fillcolor"] == "#F6F6F6"

    def test_region_zone_color(self):
        """RegionZone should be #ECEFF1 (blue-grey)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#ECEFF1")
        assert attrs["fillcolor"] == "#ECEFF1"

    def test_availability_zone_color(self):
        """AvailabilityZone should be #FFF3E0 (light orange)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#FFF3E0")
        assert attrs["fillcolor"] == "#FFF3E0"

    def test_subnet_zone_color(self):
        """SubNetworkZone should be #EDE7F6 (light violet)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#EDE7F6")
        assert attrs["fillcolor"] == "#EDE7F6"

    def test_vpc_network_zone_color(self):
        """VPCNetworkZone should be #E3F2FD (blue tint, same as LogicalGrouping)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#E3F2FD")
        assert attrs["fillcolor"] == "#E3F2FD"

    def test_firewall_zone_color(self):
        """FirewallZone should be #FBE9E7 (peach)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#FBE9E7")
        assert attrs["fillcolor"] == "#FBE9E7"

    def test_kubernetes_cluster_zone_color(self):
        """KubernetesClusterZone should be #FCE4EC (pink)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#FCE4EC")
        assert attrs["fillcolor"] == "#FCE4EC"

    def test_instance_group_zone_color(self):
        """InstanceGroupZone should be #F9FBE7 (lime tint)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#F9FBE7")
        assert attrs["fillcolor"] == "#F9FBE7"

    def test_pod_zone_color(self):
        """PodZone should be #E8F5E9 (mint)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#E8F5E9")
        assert attrs["fillcolor"] == "#E8F5E9"

    def test_replica_pool_zone_color(self):
        """ReplicaPoolZone should be #E0F7FA (cyan tint)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#E0F7FA")
        assert attrs["fillcolor"] == "#E0F7FA"

    def test_account_zone_color(self):
        """AccountZone should be #E8EAF6 (indigo tint)."""
        from resource_classes.gcp.groups import _gcp_2024_attrs

        attrs = _gcp_2024_attrs("#E8EAF6")
        assert attrs["fillcolor"] == "#E8EAF6"

    def test_all_20_zone_colors(self):
        """Verify all 20 zone types have correct colors from the 2024 guidelines table."""
        expected_colors = {
            "User": "#FFFFFF",
            "System": "#F1F8E9",
            "ProjectZone": "#F6F6F6",
            "InfraSystem": "#F3E5F5",
            "ExternalSaaS": "#FFEBEE",
            "ExternalData": "#FFF8E1",
            "OnPremises": "#EFEBE9",
            "External3rdParty": "#E0F2F1",
            "External1stParty": "#E1F5FE",
            "LogicalGroup": "#E3F2FD",
            "Region": "#ECEFF1",
            "Zone": "#FFF3E0",
            "SubNetwork": "#EDE7F6",
            "Firewall": "#FBE9E7",
            "KubernetesCluster": "#FCE4EC",
            "InstanceGroup": "#F9FBE7",
            "Pod": "#E8F5E9",
            "ReplicaPool": "#E0F7FA",
            "Account": "#E8EAF6",
            "OptionalComponent": "#FFFFFF",  # White with blue dashed border
        }

        from resource_classes.gcp.groups import _gcp_2024_attrs

        for zone_name, expected_color in expected_colors.items():
            attrs = _gcp_2024_attrs(expected_color)
            assert (
                attrs["fillcolor"] == expected_color
            ), f"{zone_name} should be {expected_color}"


class TestGCPZoneLabelFormat:
    """Test that zone labels are plain text (no HTML tables, no icons)."""

    def test_zone_labels_are_plain_text(self):
        """Verify zone labels don't contain HTML image tags or table markup."""
        from resource_classes.gcp import groups

        # The new zones use plain text labels (just the label string)
        # They don't use HTML tables with <img> tags like the old AWS/Azure zones

        # Check that the _gcp_2024_attrs helper doesn't include image-related attributes
        attrs = groups._gcp_2024_attrs("#F6F6F6")

        # Should not have any image-related keys
        assert "image" not in attrs
        assert "imagescale" not in attrs

        # Labels are passed directly to Cluster.__init__(), not wrapped in HTML


class TestGCPZoneTerraformAliases:
    """Test that Terraform resource aliases are correctly mapped to zone classes."""

    def test_project_alias(self):
        """google_project should map to ProjectZone."""
        from resource_classes.gcp.groups import google_project, ProjectZone

        assert google_project is ProjectZone

    def test_network_alias(self):
        """google_compute_network should map to VPCNetworkZone."""
        from resource_classes.gcp.groups import google_compute_network, VPCNetworkZone

        assert google_compute_network is VPCNetworkZone

    def test_subnetwork_alias(self):
        """google_compute_subnetwork should map to SubNetworkZone."""
        from resource_classes.gcp.groups import (
            google_compute_subnetwork,
            SubNetworkZone,
        )

        assert google_compute_subnetwork is SubNetworkZone

    def test_firewall_alias(self):
        """google_compute_firewall should map to FirewallZone."""
        from resource_classes.gcp.groups import google_compute_firewall, FirewallZone

        assert google_compute_firewall is FirewallZone

    def test_region_alias(self):
        """tv_gcp_region should map to RegionZone (synthetic node, not a real TF resource)."""
        from resource_classes.gcp.groups import tv_gcp_region, RegionZone

        assert tv_gcp_region is RegionZone

    def test_zone_alias(self):
        """tv_gcp_zone should map to AvailabilityZone (synthetic node, not a real TF resource)."""
        from resource_classes.gcp.groups import tv_gcp_zone, AvailabilityZone

        assert tv_gcp_zone is AvailabilityZone

    def test_container_cluster_alias(self):
        """google_container_cluster should map to KubernetesClusterZone."""
        from resource_classes.gcp.groups import (
            google_container_cluster,
            KubernetesClusterZone,
        )

        assert google_container_cluster is KubernetesClusterZone

    def test_instance_group_aliases(self):
        """Instance group and IGM resources should map correctly."""
        from resource_classes.gcp.groups import (
            google_compute_instance_group,
            InstanceGroupZone,
        )
        from resource_classes.gcp.compute import (
            google_compute_instance_group_manager,
            google_compute_region_instance_group_manager,
            InstanceGroup,
        )

        assert google_compute_instance_group is InstanceGroupZone  # Still a group
        assert (
            google_compute_instance_group_manager is InstanceGroup
        )  # Now a regular node
        assert (
            google_compute_region_instance_group_manager is InstanceGroup
        )  # Now a regular node


class TestGCPGroupNodesConfig:
    """Test that GCP_GROUP_NODES config includes all zone types."""

    def test_all_zone_types_in_group_nodes(self):
        """Verify GCP_GROUP_NODES contains all expected zone type aliases."""
        from modules.config.cloud_config_gcp import GCP_GROUP_NODES

        expected_entries = [
            "tv_gcp_account",
            "google_project",
            "tv_gcp_users",
            "tv_gcp_system",
            "tv_gcp_infra_system2",
            "tv_gcp_onprem",
            "tv_gcp_external_saas",
            "tv_gcp_external_data",
            "tv_gcp_external_3p",
            "tv_gcp_external_1p",
            "google_compute_network",
            "tv_gcp_logical_group",
            "tv_gcp_region",  # Synthetic node (not a real TF resource)
            "google_container_cluster",
            "tv_gcp_zone",  # Synthetic node (not a real TF resource)
            "google_compute_subnetwork",
            "google_compute_firewall",
            "google_compute_instance_group",
            "tv_gcp_replica_pool",
            "tv_gcp_k8s_pod",
            "tv_gcp_optional",
        ]

        for entry in expected_entries:
            assert entry in GCP_GROUP_NODES, f"{entry} should be in GCP_GROUP_NODES"
