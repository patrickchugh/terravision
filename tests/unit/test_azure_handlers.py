"""Unit tests for modules/resource_handlers/azure.py"""

import unittest
import sys
from pathlib import Path
from typing import Dict, Any

# Add modules directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.resource_handlers.azure import (
    azure_handle_vnet_subnets,
    azure_handle_nsg,
    azure_handle_lb,
    azure_handle_app_gateway,
)
from modules.exceptions import MissingResourceError


class TestAzureHandleVnetSubnets(unittest.TestCase):
    """Test azure_handle_vnet_subnets() for VNet/subnet relationships."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_subnets_without_vnets_raise_error(self):
        """Test that subnets without VNets raise MissingResourceError."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {"azurerm_subnet.sub1": []}

        with self.assertRaises(MissingResourceError) as context:
            azure_handle_vnet_subnets(tfdata)

        error = context.exception
        self.assertEqual(error.message, "azurerm_virtual_network")
        self.assertEqual(error.context["handler"], "azure_handle_vnet_subnets")
        self.assertEqual(error.context["subnet_count"], 1)

    def test_subnet_linked_to_matching_vnet(self):
        """Test that subnet with metadata reference links to matching VNet."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_virtual_network.main": [],
            "azurerm_subnet.sub1": [],
        }
        tfdata["meta_data"] = {"azurerm_subnet.sub1": {}}
        tfdata["original_metadata"] = {
            "azurerm_subnet.sub1": {"virtual_network_name": "main"}
        }

        result = azure_handle_vnet_subnets(tfdata)
        # Subnet should now be child of VNet
        self.assertIn(
            "azurerm_subnet.sub1", result["graphdict"]["azurerm_virtual_network.main"]
        )
        # Subnet metadata should include full VNet resource identifier
        self.assertEqual(
            result["meta_data"]["azurerm_subnet.sub1"]["vnet"],
            "azurerm_virtual_network.main",
        )

    def test_missing_virtual_network_reference_logged(self):
        """Test subnets without virtual_network_name are skipped."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_virtual_network.main": [],
            "azurerm_subnet.sub1": [],
        }
        tfdata["meta_data"] = {"azurerm_subnet.sub1": {}}
        tfdata["original_metadata"] = {"azurerm_subnet.sub1": {}}

        result = azure_handle_vnet_subnets(tfdata)
        # Graph should remain unchanged
        self.assertEqual(result["graphdict"], tfdata["graphdict"])


class TestAzureHandleNsg(unittest.TestCase):
    """Test azure_handle_nsg() for NSG association handling."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_nsg_wraps_subnet(self):
        """Test that NSG wraps subnet when association exists."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_network_security_group.nsg1": [],
            "azurerm_subnet.sub1": [],
            "azurerm_subnet_network_security_group_association.assoc1": [
                "azurerm_network_security_group.nsg1"
            ],
        }
        tfdata["original_metadata"] = {
            "azurerm_subnet_network_security_group_association.assoc1": {
                "network_security_group_id": "azurerm_network_security_group.nsg1",
                "subnet_id": "azurerm_subnet.sub1",
            }
        }

        result = azure_handle_nsg(tfdata)
        self.assertIn(
            "azurerm_subnet.sub1",
            result["graphdict"]["azurerm_network_security_group.nsg1"],
        )

    def test_nsg_wraps_network_interface(self):
        """Test that NSG wraps network interface when association exists."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_network_security_group.nsg1": [],
            "azurerm_network_interface.nic1": [],
            "azurerm_network_interface_security_group_association.assoc1": [
                "azurerm_network_security_group.nsg1"
            ],
        }
        tfdata["original_metadata"] = {
            "azurerm_network_interface_security_group_association.assoc1": {
                "network_security_group_id": "azurerm_network_security_group.nsg1",
                "network_interface_id": "azurerm_network_interface.nic1",
            }
        }

        result = azure_handle_nsg(tfdata)
        self.assertIn(
            "azurerm_network_interface.nic1",
            result["graphdict"]["azurerm_network_security_group.nsg1"],
        )

    def test_missing_association_references_skipped(self):
        """Test associations missing references are skipped gracefully."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_network_security_group.nsg1": [],
            "azurerm_subnet_network_security_group_association.assoc1": [],
        }
        tfdata["original_metadata"] = {
            "azurerm_subnet_network_security_group_association.assoc1": {}
        }

        result = azure_handle_nsg(tfdata)
        # Graph should remain unchanged
        self.assertEqual(result["graphdict"], tfdata["graphdict"])


class TestAzureHandleLb(unittest.TestCase):
    """Test azure_handle_lb() for load balancer SKU handling."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_lb_renamed_per_sku(self):
        """Test that LB is renamed based on SKU type."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_lb.lb1": ["resource1"],
            "resource1": [],
        }
        tfdata["meta_data"] = {"azurerm_lb.lb1": {"count": 1}}
        tfdata["original_metadata"] = {"azurerm_lb.lb1": {"sku": {"name": "Standard"}}}

        result = azure_handle_lb(tfdata)
        # Renamed node should exist
        self.assertIn("azurerm_lb_standard.lb", result["graphdict"])
        # Renamed node should contain original connections
        self.assertIn("resource1", result["graphdict"]["azurerm_lb_standard.lb"])

    def test_lb_backend_pool_link(self):
        """Test that backend pools link to their load balancer."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_lb.lb1": [],
            "azurerm_lb_backend_address_pool.pool1": [],
        }
        tfdata["original_metadata"] = {
            "azurerm_lb_backend_address_pool.pool1": {
                "loadbalancer_id": "azurerm_lb.lb1"
            }
        }

        result = azure_handle_lb(tfdata)
        self.assertIn(
            "azurerm_lb_backend_address_pool.pool1",
            result["graphdict"]["azurerm_lb.lb1"],
        )


class TestAzureHandleAppGateway(unittest.TestCase):
    """Test azure_handle_app_gateway() for tier and WAF handling."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_app_gateway_renamed_by_tier(self):
        """Test that application gateway is renamed based on tier."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_application_gateway.appgw": ["resource1"],
            "resource1": [],
        }
        tfdata["meta_data"] = {"azurerm_application_gateway.appgw": {"count": 1}}
        tfdata["original_metadata"] = {
            "azurerm_application_gateway.appgw": {
                "sku": {"tier": "WAF_v2", "name": "WAF_v2"},
                "waf_configuration": {"enabled": True, "firewall_mode": "Prevention"},
            }
        }

        result = azure_handle_app_gateway(tfdata)
        # WAF node should exist and maintain connections
        self.assertIn(
            "azurerm_application_gateway_waf.appgw",
            result["graphdict"],
        )
        self.assertIn(
            "resource1",
            result["graphdict"]["azurerm_application_gateway_waf.appgw"],
        )
        # Metadata should include tier and WAF settings
        metadata = result["meta_data"]["azurerm_application_gateway_waf.appgw"]
        self.assertEqual(metadata["tier"], "WAF_v2")
        self.assertTrue(metadata["waf_enabled"])
        self.assertEqual(metadata["waf_mode"], "Prevention")

    def test_app_gateway_backend_pool_link(self):
        """Test backend pool links to application gateway."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "azurerm_application_gateway.appgw": [],
            "azurerm_application_gateway_backend_address_pool.pool1": [],
        }
        tfdata["original_metadata"] = {
            "azurerm_application_gateway_backend_address_pool.pool1": {
                "application_gateway_name": "azurerm_application_gateway.appgw"
            }
        }

        result = azure_handle_app_gateway(tfdata)
        self.assertIn(
            "azurerm_application_gateway_backend_address_pool.pool1",
            result["graphdict"]["azurerm_application_gateway.appgw"],
        )


if __name__ == "__main__":
    unittest.main()
