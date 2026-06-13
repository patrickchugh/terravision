"""
Tests for GCP Grouping Zone Styles (Google Cloud reference architecture look).

These tests verify that all GCP grouping zones comply with the reference
architecture styling:
- Cloud boundary: solid Google blue (#1A73E8) with white monochrome logo top-left
- Regions: white fill with solid dark border
- VPC networks: transparent fill with thick black squared border
- Other zones: light blue or light green fill with dashed dark blue/green border
- Text-only labels (no icons next to labels)
"""

import pytest
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# GCP Zone Fill Color Reference Table (reference architecture palette)
GCP_ZONE_COLORS = {
    # Blue family (light blue fill, dashed dark blue border)
    "UserZone": "#E4EEFD",
    "ProjectZone": "#E4EEFD",
    "AccountZone": "#E4EEFD",
    "InfraSystemZone": "#E4EEFD",
    "External3rdPartyZone": "#E4EEFD",
    "External1stPartyZone": "#E4EEFD",
    "LogicalGroupZone": "#E4EEFD",
    "KubernetesClusterZone": "#E4EEFD",
    "SubNetworkZone": "#E4EEFD",
    "InstanceGroupZone": "#E4EEFD",
    # Green family (light green fill, dashed dark green border)
    "SystemZone": "#E8F4EB",
    "OnPremisesZone": "#E8F4EB",
    "ExternalSaaSZone": "#E8F4EB",
    "ExternalDataZone": "#E8F4EB",
    "AvailabilityZone": "#E8F4EB",
    "FirewallZone": "#E8F4EB",
    "ReplicaPoolZone": "#E8F4EB",
    "PodZone": "#E8F4EB",
    # Special zones
    "RegionZone": "#FFFFFF",  # White fill with solid dark border
    "VPCNetworkZone": "none",  # Transparent with thick black squared border
    "OptionalComponentZone": "#FFFFFF",  # White fill with dashed blue border
    "GCPGroup": "#1A73E8",  # Solid Google blue cloud boundary
}


class TestGCPZoneStyleAttributes:
    """Test that all zone classes have correct Graphviz style attributes."""

    def test_filled_zones_use_rounded_filled_style(self):
        """Verify filled zones use rounded+filled style, dashed when bordered."""
        from resource_classes.gcp.groups import (
            _gcp_zone_attrs,
            _gcp_blue_group_attrs,
            _gcp_green_group_attrs,
        )

        # Solid filled zone (e.g. region)
        standard_attrs = _gcp_zone_attrs("#FFFFFF", "#202124")
        assert "rounded" in standard_attrs["style"]
        assert "filled" in standard_attrs["style"]
        assert "dashed" not in standard_attrs["style"]

        # Blue/green groups have dashed borders
        for attrs in (_gcp_blue_group_attrs(), _gcp_green_group_attrs()):
            assert "dashed" in attrs["style"]
            assert "rounded" in attrs["style"]
            assert "filled" in attrs["style"]

    def test_borderless_zones_have_zero_penwidth(self):
        """Zones without a border color get penwidth='0'."""
        from resource_classes.gcp.groups import _gcp_zone_attrs

        attrs = _gcp_zone_attrs("#FFFFFF")
        assert attrs["penwidth"] == "0"

    def test_bordered_zones_have_thick_penwidth(self):
        """Bordered zones default to penwidth='3'."""
        from resource_classes.gcp.groups import _gcp_zone_attrs

        attrs = _gcp_zone_attrs("#FFFFFF", "#202124")
        assert attrs["penwidth"] == "3"

    def test_all_zones_have_label_at_top_left(self):
        """Verify all zones have labels at top-left (labeljust='l', labelloc='t')."""
        from resource_classes.gcp.groups import _gcp_zone_attrs

        attrs = _gcp_zone_attrs("#FFFFFF")
        assert attrs["labeljust"] == "l"
        assert attrs["labelloc"] == "t"

    def test_blue_group_attrs(self):
        """Blue groups: light blue fill with dashed dark blue border."""
        from resource_classes.gcp.groups import _gcp_blue_group_attrs

        attrs = _gcp_blue_group_attrs()
        assert attrs["fillcolor"] == "#E4EEFD"
        assert attrs["pencolor"] == "#174EA6"
        assert "dashed" in attrs["style"]

    def test_green_group_attrs(self):
        """Green groups: light green fill with dashed dark green border."""
        from resource_classes.gcp.groups import _gcp_green_group_attrs

        attrs = _gcp_green_group_attrs()
        assert attrs["fillcolor"] == "#E8F4EB"
        assert attrs["pencolor"] == "#0D652D"
        assert "dashed" in attrs["style"]

    def test_vpc_zone_is_transparent_squared(self):
        """VPC networks: transparent fill, black squared border."""
        from resource_classes.gcp.groups import _gcp_zone_attrs

        attrs = _gcp_zone_attrs("none", "#000000", rounded=False, penwidth="4")
        assert attrs["fillcolor"] == "none"
        assert attrs["pencolor"] == "#000000"
        assert "rounded" not in attrs["style"]
        assert "filled" not in attrs["style"]
        assert attrs["penwidth"] == "4"


class TestGCPZoneHexColors:
    """Test that key zone classes have correct fill colors."""

    @staticmethod
    def _zone_fillcolor(zone_cls):
        """Instantiate a zone inside a throwaway diagram and read its fillcolor."""
        from resource_classes import Canvas, setdiagram

        diagram = Canvas("test", "test_output", outformat="png", show=False)
        setdiagram(diagram)
        try:
            zone = zone_cls()
            return zone.dot.graph_attr["fillcolor"]
        finally:
            setdiagram(None)

    @pytest.mark.parametrize("zone_name,expected_color", GCP_ZONE_COLORS.items())
    def test_zone_fill_colors(self, zone_name, expected_color):
        """Each zone class must use its reference architecture fill color."""
        from resource_classes.gcp import groups

        zone_cls = getattr(groups, zone_name)
        assert self._zone_fillcolor(zone_cls) == expected_color

    def test_cloud_boundary_is_google_blue(self):
        """GCPGroup must be solid Google blue with white label text."""
        from resource_classes import Canvas, setdiagram
        from resource_classes.gcp.groups import GCPGroup

        diagram = Canvas("test", "test_output", outformat="png", show=False)
        setdiagram(diagram)
        try:
            group = GCPGroup()
            assert group.dot.graph_attr["fillcolor"] == "#1A73E8"
            assert group.dot.graph_attr["fontcolor"] == "#FFFFFF"
            # White monochrome logo at top-left
            assert "gcp_white.png" in group.dot.graph_attr["label"]
            assert group.dot.graph_attr["labelloc"] == "t"
            assert group.dot.graph_attr["labeljust"] == "l"
        finally:
            setdiagram(None)

    def test_region_zone_has_solid_dark_border(self):
        """RegionZone must be white with a solid dark border."""
        from resource_classes import Canvas, setdiagram
        from resource_classes.gcp.groups import RegionZone

        diagram = Canvas("test", "test_output", outformat="png", show=False)
        setdiagram(diagram)
        try:
            zone = RegionZone()
            assert zone.dot.graph_attr["fillcolor"] == "#FFFFFF"
            assert zone.dot.graph_attr["pencolor"] == "#202124"
            assert "dashed" not in zone.dot.graph_attr["style"]
        finally:
            setdiagram(None)

    def test_white_logo_asset_exists(self):
        """The white monochrome GCP logo must exist on disk."""
        from resource_classes.gcp.groups import base_path

        logo = os.path.join(base_path, "resource_images", "gcp", "gcp_white.png")
        assert os.path.exists(logo)


class TestGCPZoneLabelFormat:
    """Test that zone labels are plain text (no HTML tables, no icons)."""

    def test_zone_labels_are_plain_text(self):
        """Verify zone style attrs don't contain image-related attributes."""
        from resource_classes.gcp import groups

        # Check that the _gcp_zone_attrs helper doesn't include image-related
        # attributes (the cloud boundary logo is an HTML label, not an attr)
        attrs = groups._gcp_zone_attrs("#FFFFFF")

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
