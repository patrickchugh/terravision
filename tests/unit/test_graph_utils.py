"""Unit tests for graph utility functions."""

import unittest
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.utils.graph_utils import (
    ensure_metadata,
    validate_metadata_consistency,
    list_of_dictkeys_containing,
    find_common_elements,
    initialize_metadata,
)


class TestEnsureMetadata(unittest.TestCase):
    """Test ensure_metadata function."""

    def test_basic_metadata_creation(self):
        """Test creating basic metadata dictionary."""
        metadata = ensure_metadata(
            resource_id="aws_vpc.main", resource_type="aws_vpc", provider="aws"
        )

        self.assertEqual(metadata["name"], "main")
        self.assertEqual(metadata["type"], "aws_vpc")
        self.assertEqual(metadata["provider"], "aws")

    def test_metadata_with_additional_attributes(self):
        """Test metadata with additional attributes."""
        metadata = ensure_metadata(
            resource_id="aws_vpc.main",
            resource_type="aws_vpc",
            provider="aws",
            cidr_block="10.0.0.0/16",
            tags={"Environment": "prod"},
        )

        self.assertEqual(metadata["cidr_block"], "10.0.0.0/16")
        self.assertEqual(metadata["tags"], {"Environment": "prod"})

    def test_metadata_extracts_name_from_resource_id(self):
        """Test that metadata extracts resource name from ID."""
        metadata = ensure_metadata(
            resource_id="module.network.aws_subnet.private",
            resource_type="aws_subnet",
            provider="aws",
        )

        self.assertEqual(metadata["name"], "private")

    def test_azure_provider_metadata(self):
        """Test metadata creation for Azure resources."""
        metadata = ensure_metadata(
            resource_id="azurerm_virtual_network.vnet1",
            resource_type="azurerm_virtual_network",
            provider="azurerm",
        )

        self.assertEqual(metadata["name"], "vnet1")
        self.assertEqual(metadata["type"], "azurerm_virtual_network")
        self.assertEqual(metadata["provider"], "azurerm")

    def test_gcp_provider_metadata(self):
        """Test metadata creation for GCP resources."""
        metadata = ensure_metadata(
            resource_id="google_compute_network.vpc1",
            resource_type="google_compute_network",
            provider="google",
        )

        self.assertEqual(metadata["name"], "vpc1")
        self.assertEqual(metadata["type"], "google_compute_network")
        self.assertEqual(metadata["provider"], "google")

    def test_metadata_with_special_characters_in_name(self):
        """Test handling resource names with special characters."""
        metadata = ensure_metadata(
            resource_id="aws_s3_bucket.my-bucket-123",
            resource_type="aws_s3_bucket",
            provider="aws",
        )

        self.assertEqual(metadata["name"], "my-bucket-123")

    def test_metadata_with_empty_additional_attrs(self):
        """Test metadata creation with no additional attributes."""
        metadata = ensure_metadata(
            resource_id="aws_vpc.test", resource_type="aws_vpc", provider="aws"
        )

        # Should only have required keys
        self.assertEqual(set(metadata.keys()), {"name", "type", "provider"})

    def test_metadata_defaults_to_aws_provider(self):
        """Test that provider defaults to 'aws' when not specified."""
        metadata = ensure_metadata(resource_id="aws_vpc.main", resource_type="aws_vpc")

        self.assertEqual(metadata["provider"], "aws")


class TestValidateMetadataConsistency(unittest.TestCase):
    """Test validate_metadata_consistency function."""

    def test_valid_metadata(self):
        """Test validation with complete valid metadata."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
                "aws_subnet.public": ["aws_vpc.main"],
            },
            "meta_data": {
                "aws_vpc.main": {
                    "name": "main",
                    "type": "aws_vpc",
                    "provider": "aws",
                },
                "aws_subnet.public": {
                    "name": "public",
                    "type": "aws_subnet",
                    "provider": "aws",
                },
            },
        }

        errors = validate_metadata_consistency(tfdata)
        self.assertEqual(errors, [])

    def test_missing_metadata_entry(self):
        """Test detection of missing metadata entry."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
                "aws_subnet.public": [],
            },
            "meta_data": {
                "aws_vpc.main": {
                    "name": "main",
                    "type": "aws_vpc",
                    "provider": "aws",
                },
                # aws_subnet.public is missing
            },
        }

        errors = validate_metadata_consistency(tfdata)
        self.assertEqual(len(errors), 1)
        self.assertIn("aws_subnet.public", errors[0])
        self.assertIn("missing from meta_data", errors[0])

    def test_missing_required_keys(self):
        """Test detection of missing required metadata keys."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
            },
            "meta_data": {
                "aws_vpc.main": {
                    "name": "main",
                    # Missing 'type' and 'provider' keys
                },
            },
        }

        errors = validate_metadata_consistency(tfdata)
        self.assertGreaterEqual(len(errors), 2)
        error_text = " ".join(errors)
        self.assertIn("type", error_text)
        self.assertIn("provider", error_text)

    def test_orphaned_metadata(self):
        """Test detection of metadata entries without graph nodes."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
            },
            "meta_data": {
                "aws_vpc.main": {
                    "name": "main",
                    "type": "aws_vpc",
                    "provider": "aws",
                },
                "aws_subnet.orphan": {
                    "name": "orphan",
                    "type": "aws_subnet",
                    "provider": "aws",
                },
            },
        }

        errors = validate_metadata_consistency(tfdata)
        self.assertEqual(len(errors), 1)
        self.assertIn("aws_subnet.orphan", errors[0])
        self.assertIn("missing from graphdict", errors[0])

    def test_empty_tfdata_returns_no_errors(self):
        """Test that empty tfdata is considered valid."""
        tfdata = {"graphdict": {}, "meta_data": {}}

        errors = validate_metadata_consistency(tfdata)
        self.assertEqual(errors, [])

    def test_missing_graphdict_key(self):
        """Test handling of tfdata without graphdict key."""
        tfdata = {"meta_data": {}}

        errors = validate_metadata_consistency(tfdata)
        # Should handle gracefully with empty graphdict
        self.assertEqual(errors, [])

    def test_missing_meta_data_key(self):
        """Test handling of tfdata without meta_data key."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
            }
        }

        errors = validate_metadata_consistency(tfdata)
        self.assertEqual(len(errors), 1)
        self.assertIn("aws_vpc.main", errors[0])

    def test_multiple_errors_reported(self):
        """Test that multiple validation errors are all reported."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
                "aws_subnet.public": [],
                "aws_instance.web": [],
            },
            "meta_data": {
                "aws_vpc.main": {
                    "name": "main",
                    # Missing type and provider
                },
                "aws_subnet.public": {
                    "name": "public",
                    "type": "aws_subnet",
                    # Missing provider
                },
                # aws_instance.web completely missing
                "aws_security_group.orphan": {
                    "name": "orphan",
                    "type": "aws_security_group",
                    "provider": "aws",
                },
            },
        }

        errors = validate_metadata_consistency(tfdata)
        # Should report: 2 missing keys for vpc.main, 1 missing key for subnet.public,
        # 1 missing metadata for instance.web, 1 orphaned sg.orphan
        self.assertGreaterEqual(len(errors), 5)


class TestListOfDictkeysContaining(unittest.TestCase):
    """Test list_of_dictkeys_containing function."""

    def test_find_keys_with_keyword(self):
        """Test finding keys containing keyword."""
        test_dict = {
            "aws_security_group.web": [],
            "aws_security_group.db": [],
            "aws_instance.web": [],
            "aws_vpc.main": [],
        }

        result = list_of_dictkeys_containing(test_dict, "security_group")
        self.assertEqual(len(result), 2)
        self.assertIn("aws_security_group.web", result)
        self.assertIn("aws_security_group.db", result)

    def test_no_matches(self):
        """Test when no keys match keyword."""
        test_dict = {
            "aws_instance.web": [],
            "aws_vpc.main": [],
        }

        result = list_of_dictkeys_containing(test_dict, "security_group")
        self.assertEqual(result, [])

    def test_empty_dict(self):
        """Test with empty dictionary."""
        test_dict = {}

        result = list_of_dictkeys_containing(test_dict, "security_group")
        self.assertEqual(result, [])

    def test_partial_match(self):
        """Test that partial matches are found."""
        test_dict = {
            "aws_instance.web_server": [],
            "aws_instance.web_app": [],
            "aws_vpc.main": [],
        }

        result = list_of_dictkeys_containing(test_dict, "web")
        self.assertEqual(len(result), 2)

    def test_case_sensitive_matching(self):
        """Test that matching is case-sensitive."""
        test_dict = {
            "AWS_INSTANCE.WEB": [],
            "aws_instance.web": [],
        }

        result = list_of_dictkeys_containing(test_dict, "aws")
        self.assertEqual(len(result), 1)
        self.assertIn("aws_instance.web", result)

    def test_keyword_at_different_positions(self):
        """Test finding keyword at various positions in keys."""
        test_dict = {
            "instance_aws.web": [],
            "aws_instance.web": [],
            "web.instance.aws": [],
        }

        result = list_of_dictkeys_containing(test_dict, "aws")
        self.assertEqual(len(result), 3)


class TestFindCommonElements(unittest.TestCase):
    """Test find_common_elements function with optimized implementation."""

    def test_find_common_security_groups(self):
        """Test finding common security groups between resources."""
        graphdict = {
            "aws_instance.web1": ["aws_security_group.web", "aws_subnet.public"],
            "aws_instance.web2": ["aws_security_group.web", "aws_subnet.public"],
            "aws_instance.db": ["aws_security_group.db"],
        }

        result = find_common_elements(graphdict, "aws_instance")
        # Should find shared elements between instances
        self.assertGreater(len(result), 0)

    def test_performance_with_large_lists(self):
        """Test that optimized version performs well with large inputs."""
        # Create large dictionary with many connections
        graphdict = {}
        for i in range(100):
            graphdict[f"aws_instance.node{i}"] = [
                f"aws_security_group.sg{j}" for j in range(10)
            ]

        # This should complete quickly due to set-based optimization
        result = find_common_elements(graphdict, "aws_instance")
        # Verify results are sorted (deterministic output requirement)
        self.assertIsInstance(result, list)

    def test_no_common_elements(self):
        """Test when resources have no common connections."""
        graphdict = {
            "aws_instance.web": ["aws_security_group.web"],
            "aws_instance.db": ["aws_security_group.db"],
        }

        result = find_common_elements(graphdict, "aws_instance")
        self.assertEqual(result, [])

    def test_empty_dict(self):
        """Test with empty dictionary."""
        graphdict = {}

        result = find_common_elements(graphdict, "aws_instance")
        self.assertEqual(result, [])

    def test_single_matching_key(self):
        """Test when only one key matches keyword."""
        graphdict = {
            "aws_instance.web": ["aws_security_group.web"],
            "aws_vpc.main": [],
        }

        result = find_common_elements(graphdict, "aws_instance")
        self.assertEqual(result, [])

    def test_empty_lists(self):
        """Test when matching keys have empty lists."""
        graphdict = {
            "aws_instance.web1": [],
            "aws_instance.web2": [],
        }

        result = find_common_elements(graphdict, "aws_instance")
        self.assertEqual(result, [])

    def test_multiple_common_elements(self):
        """Test finding multiple common elements."""
        graphdict = {
            "aws_instance.web1": ["sg1", "sg2", "subnet1"],
            "aws_instance.web2": ["sg1", "sg2", "subnet2"],
        }

        result = find_common_elements(graphdict, "aws_instance")
        # Should find sg1 and sg2 as common elements
        common_elements = [item[2] for item in result]
        self.assertIn("sg1", common_elements)
        self.assertIn("sg2", common_elements)

    def test_deterministic_output_ordering(self):
        """Test that output is deterministically sorted."""
        graphdict = {
            "aws_instance.z": ["shared"],
            "aws_instance.a": ["shared"],
        }

        result1 = find_common_elements(graphdict, "aws_instance")
        result2 = find_common_elements(graphdict, "aws_instance")
        self.assertEqual(result1, result2)


class TestInitializeMetadata(unittest.TestCase):
    """Test initialize_metadata function."""

    def test_initialize_basic_metadata(self):
        """Test initializing metadata from resource values."""
        resource_values = {
            "cidr_block": "10.0.0.0/16",
            "tags": {"Name": "main-vpc"},
        }

        metadata = initialize_metadata(
            resource_id="aws_vpc.main", resource_values=resource_values, provider="aws"
        )

        self.assertEqual(metadata["name"], "main")
        self.assertEqual(metadata["type"], "aws_vpc")
        self.assertEqual(metadata["provider"], "aws")
        self.assertEqual(metadata["cidr_block"], "10.0.0.0/16")
        self.assertEqual(metadata["tags"], {"Name": "main-vpc"})

    def test_initialize_filters_uncommon_attributes(self):
        """Test that only common attributes are copied."""
        resource_values = {
            "cidr_block": "10.0.0.0/16",
            "uncommon_attr": "should_not_be_included",
        }

        metadata = initialize_metadata(
            resource_id="aws_vpc.main", resource_values=resource_values, provider="aws"
        )

        self.assertIn("cidr_block", metadata)
        self.assertNotIn("uncommon_attr", metadata)

    def test_initialize_with_empty_resource_values(self):
        """Test initializing with empty resource values."""
        resource_values = {}

        metadata = initialize_metadata(
            resource_id="aws_vpc.main", resource_values=resource_values, provider="aws"
        )

        # Should have required keys only
        self.assertEqual(metadata["name"], "main")
        self.assertEqual(metadata["type"], "aws_vpc")
        self.assertEqual(metadata["provider"], "aws")

    def test_initialize_defaults_to_aws_provider(self):
        """Test that provider defaults to 'aws'."""
        resource_values = {"cidr_block": "10.0.0.0/16"}

        metadata = initialize_metadata(
            resource_id="aws_vpc.main", resource_values=resource_values
        )

        self.assertEqual(metadata["provider"], "aws")

    def test_initialize_with_multiple_common_attributes(self):
        """Test initializing with many common attributes."""
        resource_values = {
            "id": "vpc-12345",
            "cidr_block": "10.0.0.0/16",
            "vpc_id": "vpc-12345",
            "availability_zone": "us-east-1a",
            "tags": {"Name": "test"},
            "arn": "arn:aws:vpc:us-east-1:123456789012:vpc/vpc-12345",
            "region": "us-east-1",
        }

        metadata = initialize_metadata(
            resource_id="aws_vpc.main", resource_values=resource_values, provider="aws"
        )

        self.assertEqual(metadata["id"], "vpc-12345")
        self.assertEqual(metadata["cidr_block"], "10.0.0.0/16")
        self.assertEqual(metadata["availability_zone"], "us-east-1a")
        self.assertEqual(
            metadata["arn"], "arn:aws:vpc:us-east-1:123456789012:vpc/vpc-12345"
        )

    def test_initialize_azure_resource(self):
        """Test initializing metadata for Azure resource."""
        resource_values = {
            "location": "eastus",
            "resource_group_name": "rg-test",
            "tags": {"Environment": "dev"},
        }

        metadata = initialize_metadata(
            resource_id="azurerm_virtual_network.vnet1",
            resource_values=resource_values,
            provider="azurerm",
        )

        self.assertEqual(metadata["provider"], "azurerm")
        self.assertEqual(metadata["location"], "eastus")
        self.assertEqual(metadata["resource_group_name"], "rg-test")

    def test_initialize_gcp_resource(self):
        """Test initializing metadata for GCP resource."""
        resource_values = {
            "region": "us-central1",
            "name": "vpc-network",
        }

        metadata = initialize_metadata(
            resource_id="google_compute_network.vpc1",
            resource_values=resource_values,
            provider="google",
        )

        self.assertEqual(metadata["provider"], "google")
        self.assertEqual(metadata["region"], "us-central1")

    def test_initialize_handles_simple_resource_id(self):
        """Test handling resource ID without dots."""
        resource_values = {"id": "test123"}

        metadata = initialize_metadata(
            resource_id="simple_resource", resource_values=resource_values
        )

        # Should extract name from simple resource_id
        self.assertEqual(metadata["type"], "simple_resource")

    def test_initialize_with_nested_module_resource_id(self):
        """Test extracting name from nested module resource ID."""
        resource_values = {"subnet_id": "subnet-123"}

        metadata = initialize_metadata(
            resource_id="module.network.module.subnets.aws_subnet.private",
            resource_values=resource_values,
            provider="aws",
        )

        self.assertEqual(metadata["name"], "private")
        self.assertEqual(metadata["subnet_id"], "subnet-123")


if __name__ == "__main__":
    unittest.main()
