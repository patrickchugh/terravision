"""
Tests for GCP hierarchy validation functions.

Validates FR-008a and FR-008b requirements:
- FR-008a: Zones MUST have subnet parents
- FR-008b: No hierarchy gaps in GCP resource grouping
"""

import pytest
from tests.validation_helpers import (
    validate_gcp_hierarchy_integrity,
    validate_no_shared_gcp_connections,
)


class TestGCPHierarchyValidation:
    """Test GCP hierarchy validation functions."""

    def test_valid_hierarchy_no_errors(self):
        """Valid hierarchy with zones having subnet parents should pass."""
        tfdata = {
            "graphdict": {
                "google_project.my_project": ["google_compute_network.vpc"],
                "google_compute_network.vpc": ["tv_gcp_region.us-central1"],
                "tv_gcp_region.us-central1": ["google_compute_subnetwork.subnet_a"],
                "google_compute_subnetwork.subnet_a": ["tv_gcp_zone.us-central1-a"],
                "tv_gcp_zone.us-central1-a": [
                    "google_compute_instance.vm~1",
                    "google_compute_instance.vm~2",
                ],
                "google_compute_instance.vm~1": [],
                "google_compute_instance.vm~2": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_zone_without_subnet_parent_fails_fr008a(self):
        """Zone without subnet parent should fail FR-008a validation."""
        tfdata = {
            "graphdict": {
                "google_project.my_project": ["tv_gcp_zone.us-central1-a"],
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm"],
                "google_compute_instance.vm": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert len(errors) > 0, "Expected FR-008a violation error"
        assert "tv_gcp_zone.us-central1-a" in errors[0]
        assert "FR-008a" in errors[0]
        assert "no subnet parent" in errors[0]

    def test_subnet_without_vpc_parent_fails_fr008b(self):
        """Subnet without VPC/region parent should fail FR-008b validation."""
        tfdata = {
            "graphdict": {
                "google_project.my_project": ["google_compute_subnetwork.subnet_a"],
                "google_compute_subnetwork.subnet_a": ["tv_gcp_zone.us-central1-a"],
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm"],
                "google_compute_instance.vm": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert len(errors) > 0, "Expected FR-008b violation error"
        assert "google_compute_subnetwork.subnet_a" in errors[0]
        assert "FR-008b" in errors[0]
        assert "no region/VPC parent" in errors[0]

    def test_multiple_hierarchy_violations(self):
        """Multiple hierarchy violations should all be reported."""
        tfdata = {
            "graphdict": {
                # Zone without subnet (FR-008a violation)
                "google_project.my_project": ["tv_gcp_zone.zone1"],
                "tv_gcp_zone.zone1": ["google_compute_instance.vm1"],
                # Subnet without VPC/region (FR-008b violation)
                "google_compute_subnetwork.orphan_subnet": ["tv_gcp_zone.zone2"],
                "tv_gcp_zone.zone2": ["google_compute_instance.vm2"],
                "google_compute_instance.vm1": [],
                "google_compute_instance.vm2": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert len(errors) >= 2, f"Expected at least 2 errors, got {len(errors)}"
        # Check both violations present
        error_text = " ".join(errors)
        assert "tv_gcp_zone.zone1" in error_text
        # zone2 has orphan_subnet as parent, so only zone1 and orphan_subnet reported
        assert "google_compute_subnetwork.orphan_subnet" in error_text

    def test_multiple_zones_with_different_subnet_parents_valid(self):
        """Multiple zones with different subnet parents should be valid."""
        tfdata = {
            "graphdict": {
                "google_project.my_project": ["google_compute_network.vpc"],
                "google_compute_network.vpc": [
                    "google_compute_subnetwork.subnet_a",
                    "google_compute_subnetwork.subnet_b",
                ],
                "google_compute_subnetwork.subnet_a": ["tv_gcp_zone.us-central1-a"],
                "google_compute_subnetwork.subnet_b": ["tv_gcp_zone.us-central1-b"],
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm~1"],
                "tv_gcp_zone.us-central1-b": ["google_compute_instance.vm~2"],
                "google_compute_instance.vm~1": [],
                "google_compute_instance.vm~2": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert (
            errors == []
        ), f"Expected no errors for valid multi-zone setup, got: {errors}"

    def test_region_without_vpc_parent_fails_fr008b(self):
        """Region without VPC/Project parent should fail FR-008b validation."""
        tfdata = {
            "graphdict": {
                "tv_gcp_region.us-central1": ["google_compute_subnetwork.subnet"],
                "google_compute_subnetwork.subnet": ["tv_gcp_zone.us-central1-a"],
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm"],
                "google_compute_instance.vm": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert len(errors) > 0, "Expected FR-008b violation error"
        assert "tv_gcp_region.us-central1" in errors[0]
        assert "FR-008b" in errors[0]
        assert "no VPC/Project parent" in errors[0]

    def test_vpc_without_project_parent_fails_fr008b(self):
        """VPC without Project/Account parent should fail FR-008b validation."""
        tfdata = {
            "graphdict": {
                "google_compute_network.vpc": ["google_compute_subnetwork.subnet"],
                "google_compute_subnetwork.subnet": ["tv_gcp_zone.us-central1-a"],
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm"],
                "google_compute_instance.vm": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert len(errors) > 0, "Expected FR-008b violation error"
        assert "google_compute_network.vpc" in errors[0]
        assert "FR-008b" in errors[0]
        assert "no Project/Account parent" in errors[0]

    def test_complete_hierarchy_valid(self):
        """Complete hierarchy chain should be valid."""
        tfdata = {
            "graphdict": {
                "google_project.my_project": ["google_compute_network.vpc"],
                "google_compute_network.vpc": ["tv_gcp_region.us-central1"],
                "tv_gcp_region.us-central1": ["google_compute_subnetwork.subnet"],
                "google_compute_subnetwork.subnet": ["tv_gcp_zone.us-central1-a"],
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm"],
                "google_compute_instance.vm": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert errors == [], f"Expected no errors for complete hierarchy, got: {errors}"


class TestGCPSharedConnectionValidation:
    """Test GCP shared connection validation."""

    def test_no_shared_connections_valid(self):
        """Resources with numbered instances should pass validation."""
        tfdata = {
            "graphdict": {
                "google_compute_subnetwork.subnet_a": ["google_compute_instance.vm~1"],
                "google_compute_subnetwork.subnet_b": ["google_compute_instance.vm~2"],
                "google_compute_instance.vm~1": [],
                "google_compute_instance.vm~2": [],
            }
        }

        errors = validate_no_shared_gcp_connections(tfdata)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_shared_connection_violation_detected(self):
        """Multiple zones pointing to same resource should fail."""
        tfdata = {
            "graphdict": {
                "tv_gcp_zone.us-central1-a": ["google_compute_instance.vm"],
                "tv_gcp_zone.us-central1-b": ["google_compute_instance.vm"],
                "google_compute_instance.vm": [],
            }
        }

        errors = validate_no_shared_gcp_connections(tfdata)
        assert len(errors) > 0, "Expected shared connection violation error"
        assert "google_compute_instance.vm" in errors[0]
        assert "multiple zone/subnet parents" in errors[0]

    def test_shared_connection_across_subnets_detected(self):
        """Multiple subnets pointing to same resource should fail."""
        tfdata = {
            "graphdict": {
                "google_compute_subnetwork.subnet_a": [
                    "google_compute_instance_group.ig"
                ],
                "google_compute_subnetwork.subnet_b": [
                    "google_compute_instance_group.ig"
                ],
                "google_compute_instance_group.ig": [],
            }
        }

        errors = validate_no_shared_gcp_connections(tfdata)
        assert len(errors) > 0, "Expected shared connection violation error"
        assert "google_compute_instance_group.ig" in errors[0]

    def test_numbered_instances_ignored(self):
        """Numbered instances (~1, ~2) should be ignored by validation."""
        tfdata = {
            "graphdict": {
                "tv_gcp_zone.us-central1-a": [
                    "google_compute_instance.vm~1",
                    "google_compute_instance.vm~2",
                ],
                "tv_gcp_zone.us-central1-b": [
                    "google_compute_instance.vm~3",
                    "google_compute_instance.vm~4",
                ],
                "google_compute_instance.vm~1": [],
                "google_compute_instance.vm~2": [],
                "google_compute_instance.vm~3": [],
                "google_compute_instance.vm~4": [],
            }
        }

        errors = validate_no_shared_gcp_connections(tfdata)
        assert errors == [], f"Numbered instances should be ignored, got: {errors}"

    def test_mixed_shared_and_valid_connections(self):
        """Mix of valid numbered and invalid shared connections."""
        tfdata = {
            "graphdict": {
                # Valid: numbered instances
                "google_compute_subnetwork.subnet_a": ["google_compute_instance.web~1"],
                "google_compute_subnetwork.subnet_b": ["google_compute_instance.web~2"],
                # Invalid: shared connection
                "tv_gcp_zone.us-central1-a": ["google_sql_database_instance.db"],
                "tv_gcp_zone.us-central1-b": ["google_sql_database_instance.db"],
                "google_compute_instance.web~1": [],
                "google_compute_instance.web~2": [],
                "google_sql_database_instance.db": [],
            }
        }

        errors = validate_no_shared_gcp_connections(tfdata)
        assert len(errors) == 1, f"Expected 1 error (db only), got {len(errors)}"
        assert "google_sql_database_instance.db" in errors[0]
        assert "google_compute_instance.web" not in errors[0]

    def test_empty_graphdict(self):
        """Empty graphdict should pass validation."""
        tfdata = {"graphdict": {}}
        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert errors == []

        errors = validate_no_shared_gcp_connections(tfdata)
        assert errors == []

    def test_non_gcp_resources_ignored(self):
        """Non-GCP resources should not trigger validation errors."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": ["aws_subnet.a"],
                "aws_subnet.a": ["aws_instance.web"],
                "aws_instance.web": [],
            }
        }

        errors = validate_gcp_hierarchy_integrity(tfdata)
        assert errors == [], "Non-GCP resources should be ignored"

        errors = validate_no_shared_gcp_connections(tfdata)
        assert errors == [], "Non-GCP resources should be ignored"


class TestIntegrationWithExistingFixtures:
    """Integration tests using existing GCP test fixtures."""
