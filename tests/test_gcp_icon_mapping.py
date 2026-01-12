"""
Tests for GCP Icon System (Google Cloud 2025 Simplified Icons).

These tests verify:
1. All icon files exist in the correct directories
2. Icon resolution follows 3-tier priority (unique → category → generic)
3. Terraform resource types map to correct icons
"""

import os
import pytest
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Expected unique icons (19 flagship 4-color products)
EXPECTED_UNIQUE_ICONS = [
    "compute-engine.png",
    "cloud-storage.png",
    "bigquery.png",
    "gke.png",
    "cloud-sql.png",
    "cloud-run.png",
    "cloud-spanner.png",
    "alloydb.png",
    "apigee.png",
    "anthos.png",
    "looker.png",
    "hyperdisk.png",
    "mandiant.png",
    "security-command-center.png",
    "ai-hypercomputer.png",
    "distributed-cloud.png",
    "vertex-ai.png",
    "secops.png",
    "threat-intelligence.png",
]

# Expected category icons (26 service families)
EXPECTED_CATEGORY_ICONS = [
    "compute.png",
    "networking.png",
    "storage.png",
    "databases.png",
    "ai-ml.png",
    "analytics.png",
    "containers.png",
    "serverless.png",
    "security.png",
    "management.png",
    "devops.png",
    "migration.png",
    "media.png",
    "integration.png",
    "business-intelligence.png",
    "collaboration.png",
    "hybrid-multicloud.png",
    "developer-tools.png",
    "observability.png",
    "operations.png",
    "agents.png",
    "maps.png",
    "marketplace.png",
    "mixed-reality.png",
    "web-mobile.png",
    "web3.png",
]


class TestIconFileExistence:
    """Test that all expected icon files exist."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_unique_icons_directory_exists(self, project_root):
        """Verify resource_images/gcp/unique/ directory exists."""
        unique_dir = os.path.join(project_root, "resource_images/gcp/unique")
        assert os.path.isdir(unique_dir), f"Directory {unique_dir} should exist"

    def test_category_icons_directory_exists(self, project_root):
        """Verify resource_images/gcp/category/ directory exists."""
        category_dir = os.path.join(project_root, "resource_images/gcp/category")
        assert os.path.isdir(category_dir), f"Directory {category_dir} should exist"

    def test_all_19_unique_icons_exist(self, project_root):
        """Verify all 19 unique icons exist."""
        unique_dir = os.path.join(project_root, "resource_images/gcp/unique")
        missing = []
        for icon in EXPECTED_UNIQUE_ICONS:
            icon_path = os.path.join(unique_dir, icon)
            if not os.path.isfile(icon_path):
                missing.append(icon)
        assert not missing, f"Missing unique icons: {missing}"

    def test_all_26_category_icons_exist(self, project_root):
        """Verify all 26 category icons exist."""
        category_dir = os.path.join(project_root, "resource_images/gcp/category")
        missing = []
        for icon in EXPECTED_CATEGORY_ICONS:
            icon_path = os.path.join(category_dir, icon)
            if not os.path.isfile(icon_path):
                missing.append(icon)
        assert not missing, f"Missing category icons: {missing}"

    def test_generic_fallback_icon_exists(self, project_root):
        """Verify generic fallback icon exists."""
        generic_path = os.path.join(project_root, "resource_images/generic/generic.png")
        assert os.path.isfile(
            generic_path
        ), f"Generic fallback icon should exist at {generic_path}"

    def test_unique_icons_count(self, project_root):
        """Verify we have exactly 19 unique icons."""
        unique_dir = os.path.join(project_root, "resource_images/gcp/unique")
        icons = [f for f in os.listdir(unique_dir) if f.endswith(".png")]
        assert (
            len(icons) == 19
        ), f"Should have 19 unique icons, found {len(icons)}: {icons}"

    def test_category_icons_count(self, project_root):
        """Verify we have exactly 26 category icons."""
        category_dir = os.path.join(project_root, "resource_images/gcp/category")
        icons = [f for f in os.listdir(category_dir) if f.endswith(".png")]
        assert (
            len(icons) == 26
        ), f"Should have 26 category icons, found {len(icons)}: {icons}"


class TestIconResolutionPriority:
    """Test the 3-tier icon resolution priority system."""

    def test_load_icon_method_exists(self):
        """Verify _load_icon method exists on Node class."""
        from resource_classes import Node

        assert hasattr(Node, "_load_icon"), "Node class should have _load_icon method"

    def test_gcp_provider_has_fallback_logic(self):
        """Verify _load_icon has GCP-specific fallback logic."""
        from resource_classes import Node
        import inspect

        source = inspect.getsource(Node._load_icon)
        assert "gcp" in source.lower(), "_load_icon should have GCP-specific handling"
        assert "unique" in source, "_load_icon should check unique icons"
        assert (
            "category" in source.lower() or "_icon_dir" in source
        ), "_load_icon should check category/icon_dir"
        assert "generic" in source, "_load_icon should fall back to generic"


class TestTerraformResourceMappings:
    """Test that Terraform resource types have correct icon mappings."""

    def test_compute_instance_uses_compute_engine_icon(self):
        """google_compute_instance should resolve to compute-engine.png."""
        from resource_classes.gcp.compute import ComputeEngine

        assert ComputeEngine._icon == "compute-engine.png"

    def test_storage_bucket_uses_cloud_storage_icon(self):
        """google_storage_bucket should resolve to cloud-storage.png."""
        from resource_classes.gcp.storage import Bucket

        assert Bucket._icon == "cloud-storage.png"

    def test_sql_database_uses_cloud_sql_icon(self):
        """google_sql_database_instance should resolve to cloud-sql.png."""
        from resource_classes.gcp.databases import SQL

        assert SQL._icon == "cloud-sql.png"

    def test_container_cluster_uses_gke_icon(self):
        """google_container_cluster should resolve to gke.png."""
        from resource_classes.gcp.containers import KubernetesEngine

        assert KubernetesEngine._icon == "gke.png"

    def test_cloud_run_service_uses_cloud_run_icon(self):
        """google_cloud_run_service should resolve to cloud-run.png."""
        from resource_classes.gcp.serverless import CloudRun

        assert CloudRun._icon == "cloud-run.png"

    def test_bigquery_dataset_uses_bigquery_icon(self):
        """google_bigquery_dataset should resolve to bigquery.png."""
        from resource_classes.gcp.analytics import BigQuery

        assert BigQuery._icon == "bigquery.png"

    def test_spanner_instance_uses_cloud_spanner_icon(self):
        """google_spanner_instance should resolve to cloud-spanner.png."""
        from resource_classes.gcp.databases import Spanner

        assert Spanner._icon == "cloud-spanner.png"


class TestGCPBaseClass:
    """Test GCP base class configuration."""

    def test_gcp_base_class_icon_dir(self):
        """_GCP base class should use category as default icon_dir."""
        from resource_classes.gcp import _GCP

        assert "category" in _GCP._icon_dir, "_GCP should default to category icons"

    def test_gcp_provider_identifier(self):
        """_GCP should have provider set to 'gcp'."""
        from resource_classes.gcp import _GCP

        assert _GCP._provider == "gcp"
