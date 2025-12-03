"""Integration tests for multi-cloud Terraform configurations.

Tests proper handling of Azure and GCP resources in the same configuration.
AWS handlers have pre-existing test coverage in unit tests.
"""

import sys
import unittest
from pathlib import Path
from typing import Any, Dict

# Add modules directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.resource_handlers.azure import (azure_handle_lb, azure_handle_nsg,
                                             azure_handle_vnet_subnets)
from modules.resource_handlers.gcp import (gcp_handle_firewall, gcp_handle_lb,
                                           gcp_handle_network_subnets)


class TestMultiCloudConfigurations(unittest.TestCase):
    """Test processing of multi-cloud Terraform configurations."""

    def _base_tfdata(self) -> Dict[str, Any]:
        """Base tfdata structure for tests."""
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_azure_gcp_mixed_config(self):
        """Test processing Terraform config with both Azure and GCP resources."""
        tfdata = self._base_tfdata()

        # Azure VNet and subnet
        tfdata["graphdict"]["azurerm_virtual_network.vnet"] = []
        tfdata["graphdict"]["azurerm_subnet.subnet1"] = []
        tfdata["meta_data"]["azurerm_subnet.subnet1"] = {}
        tfdata["original_metadata"]["azurerm_subnet.subnet1"] = {
            "virtual_network_name": "vnet"
        }

        # GCP network and subnet
        tfdata["graphdict"]["google_compute_network.main"] = []
        tfdata["graphdict"]["google_compute_subnetwork.sub1"] = []
        tfdata["meta_data"]["google_compute_subnetwork.sub1"] = {}
        tfdata["original_metadata"]["google_compute_subnetwork.sub1"] = {
            "network": "main",
            "region": "us-central1",
        }

        # Process Azure handlers
        result = azure_handle_vnet_subnets(tfdata)

        # Process GCP handlers
        result = gcp_handle_network_subnets(result)

        # Verify Azure subnet grouped under VNet
        self.assertIn(
            "azurerm_subnet.subnet1",
            result["graphdict"]["azurerm_virtual_network.vnet"],
            "Azure subnet should be grouped under VNet",
        )

        # Verify GCP subnet grouped under network
        self.assertIn(
            "google_compute_subnetwork.sub1",
            result["graphdict"]["google_compute_network.main"],
            "GCP subnet should be grouped under network",
        )

        # Verify both providers' resources coexist
        self.assertIn("azurerm_virtual_network.vnet", result["graphdict"])
        self.assertIn("google_compute_network.main", result["graphdict"])

    def test_azure_gcp_security_mixed(self):
        """Test Azure NSG and GCP firewall coexisting."""
        tfdata = self._base_tfdata()

        # Azure NSG and subnet association
        tfdata["graphdict"]["azurerm_network_security_group.nsg1"] = []
        tfdata["graphdict"]["azurerm_subnet.sub1"] = []
        tfdata["graphdict"][
            "azurerm_subnet_network_security_group_association.assoc1"
        ] = []
        tfdata["original_metadata"][
            "azurerm_subnet_network_security_group_association.assoc1"
        ] = {
            "network_security_group_id": "azurerm_network_security_group.nsg1",
            "subnet_id": "azurerm_subnet.sub1",
        }

        # GCP firewall and instance
        tfdata["graphdict"]["google_compute_network.main"] = []
        tfdata["graphdict"]["google_compute_firewall.allow_http"] = []
        tfdata["graphdict"]["google_compute_instance.web"] = []
        tfdata["meta_data"]["google_compute_firewall.allow_http"] = {}
        tfdata["original_metadata"]["google_compute_firewall.allow_http"] = {
            "network": "main",
            "target_tags": ["http-server"],
        }
        tfdata["original_metadata"]["google_compute_instance.web"] = {
            "network": "main",
            "tags": ["http-server"],
        }

        # Process handlers
        result = azure_handle_nsg(tfdata)
        result = gcp_handle_firewall(result)

        # Verify Azure NSG wraps subnet
        self.assertIn(
            "azurerm_subnet.sub1",
            result["graphdict"]["azurerm_network_security_group.nsg1"],
            "Azure NSG should wrap subnet",
        )

        # Verify GCP firewall wraps instance
        self.assertIn(
            "google_compute_instance.web",
            result["graphdict"]["google_compute_firewall.allow_http"],
            "GCP firewall should wrap instance with matching tag",
        )

        # Verify both security resources coexist
        self.assertIn("azurerm_network_security_group.nsg1", result["graphdict"])
        self.assertIn("google_compute_firewall.allow_http", result["graphdict"])

    def test_azure_gcp_load_balancers(self):
        """Test Azure and GCP load balancers together."""
        tfdata = self._base_tfdata()

        # Azure load balancer
        tfdata["graphdict"]["azurerm_lb.web"] = []
        tfdata["meta_data"]["azurerm_lb.web"] = {"count": 1}
        tfdata["original_metadata"]["azurerm_lb.web"] = {"sku": {"name": "Standard"}}

        # GCP load balancer (backend service)
        tfdata["graphdict"]["google_compute_backend_service.api"] = []
        tfdata["meta_data"]["google_compute_backend_service.api"] = {"count": 1}
        tfdata["original_metadata"]["google_compute_backend_service.api"] = {
            "load_balancing_scheme": "EXTERNAL",
            "protocol": "HTTP",
        }

        # Process handlers
        result = azure_handle_lb(tfdata)
        result = gcp_handle_lb(result)

        # Verify Azure Standard LB created
        self.assertIn(
            "azurerm_lb_standard.lb",
            result["graphdict"],
            "Azure Standard Load Balancer should be created",
        )

        # Verify GCP HTTP LB created
        self.assertIn(
            "google_compute_http_lb.lb",
            result["graphdict"],
            "GCP HTTP Load Balancer should be created",
        )

        # Verify both original resources still exist
        self.assertIn("azurerm_lb.web", result["graphdict"])
        self.assertIn("google_compute_backend_service.api", result["graphdict"])

    def test_mixed_provider_networking(self):
        """Test complex multi-cloud scenario with networking resources."""
        tfdata = self._base_tfdata()

        # Azure VNet with subnet
        tfdata["graphdict"]["azurerm_virtual_network.hub"] = []
        tfdata["graphdict"]["azurerm_subnet.gateway"] = []
        tfdata["meta_data"]["azurerm_subnet.gateway"] = {}
        tfdata["original_metadata"]["azurerm_subnet.gateway"] = {
            "virtual_network_name": "hub"
        }

        # GCP VPC with subnets
        tfdata["graphdict"]["google_compute_network.global"] = []
        tfdata["graphdict"]["google_compute_subnetwork.us_central"] = []
        tfdata["graphdict"]["google_compute_subnetwork.us_east"] = []
        tfdata["meta_data"]["google_compute_subnetwork.us_central"] = {}
        tfdata["meta_data"]["google_compute_subnetwork.us_east"] = {}
        tfdata["original_metadata"]["google_compute_subnetwork.us_central"] = {
            "network": "global",
            "region": "us-central1",
        }
        tfdata["original_metadata"]["google_compute_subnetwork.us_east"] = {
            "network": "global",
            "region": "us-east1",
        }

        # Process handlers
        result = azure_handle_vnet_subnets(tfdata)
        result = gcp_handle_network_subnets(result)

        # Verify Azure VNet structure
        azure_vnet_children = result["graphdict"]["azurerm_virtual_network.hub"]
        self.assertIn("azurerm_subnet.gateway", azure_vnet_children)

        # Verify GCP VPC structure
        gcp_network_children = result["graphdict"]["google_compute_network.global"]
        self.assertIn("google_compute_subnetwork.us_central", gcp_network_children)
        self.assertIn("google_compute_subnetwork.us_east", gcp_network_children)

        # Verify metadata preserves region info for GCP
        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.us_central"]["region"],
            "us-central1",
        )

    def test_provider_isolation(self):
        """Test that Azure and GCP handlers don't interfere with each other."""
        tfdata = self._base_tfdata()

        # Azure NSG - standalone
        tfdata["graphdict"]["azurerm_network_security_group.nsg1"] = []
        tfdata["meta_data"]["azurerm_network_security_group.nsg1"] = {}

        # GCP firewall - standalone
        tfdata["graphdict"]["google_compute_firewall.fw1"] = []
        tfdata["meta_data"]["google_compute_firewall.fw1"] = {}
        tfdata["original_metadata"]["google_compute_firewall.fw1"] = {
            "network": "nonexistent"
        }

        # Process all handlers
        result = azure_handle_nsg(tfdata)
        result = gcp_handle_firewall(result)

        # Verify Azure NSG exists independently
        self.assertIn("azurerm_network_security_group.nsg1", result["graphdict"])

        # Verify GCP firewall exists independently
        self.assertIn("google_compute_firewall.fw1", result["graphdict"])

        # Verify no cross-contamination
        self.assertEqual(
            len(result["graphdict"]["azurerm_network_security_group.nsg1"]), 0
        )
        self.assertEqual(len(result["graphdict"]["google_compute_firewall.fw1"]), 0)


if __name__ == "__main__":
    unittest.main()
