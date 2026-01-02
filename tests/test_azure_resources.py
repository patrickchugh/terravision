"""
Unit tests for Azure resource handlers and diagram generation.

Tests the Azure-specific functionality including:
- Resource group handling
- VNet and subnet relationships
- NSG associations
- Resource grouping and hierarchy
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any, Callable
from modules.resource_handlers_azure import (
    handle_special_cases,
    azure_handle_resource_group,
    azure_handle_vnet,
    azure_handle_subnet,
    azure_handle_nsg,
    azure_handle_vmss,
    azure_handle_appgw,
    match_resources,
    match_nsg_to_subnets,
    match_nic_to_vm,
    remove_empty_groups,
)
from modules.provider_detector import detect_providers, get_provider_for_resource


# ============================================================================
# Test Utility Functions (T012)
# ============================================================================


def load_tfdata_from_json(filepath: str) -> Dict[str, Any]:
    """Load tfdata from JSON file for testing.

    Args:
        filepath: Path to JSON file containing tfdata

    Returns:
        Loaded tfdata dictionary

    Example:
        >>> tfdata = load_tfdata_from_json("tests/json/test-azure.json")
    """
    with open(filepath, "r") as f:
        return json.load(f)


def run_azure_handler(
    tfdata: Dict[str, Any], handler_func: Callable[[Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """Run an Azure handler function on tfdata.

    Args:
        tfdata: Terraform data dictionary
        handler_func: Handler function to execute

    Returns:
        Updated tfdata after handler execution

    Example:
        >>> result = run_azure_handler(tfdata, azure_handle_resource_group)
    """
    return handler_func(tfdata)


def compare_graphdicts(
    actual: Dict[str, Any], expected: Dict[str, Any], ignore_keys: list = None
) -> bool:
    """Compare two graphdict dictionaries for testing.

    Args:
        actual: Actual graphdict result
        expected: Expected graphdict result
        ignore_keys: Optional list of keys to ignore in comparison

    Returns:
        True if graphdicts match (ignoring specified keys)

    Raises:
        AssertionError: If graphdicts don't match, with detailed diff

    Example:
        >>> assert compare_graphdicts(result["graphdict"], expected, ignore_keys=["random_string"])
    """
    ignore_keys = ignore_keys or []

    # Filter out ignored keys
    actual_filtered = {k: v for k, v in actual.items() if k not in ignore_keys}
    expected_filtered = {k: v for k, v in expected.items() if k not in ignore_keys}

    # Check for missing/extra keys
    actual_keys = set(actual_filtered.keys())
    expected_keys = set(expected_filtered.keys())

    missing_keys = expected_keys - actual_keys
    extra_keys = actual_keys - expected_keys

    if missing_keys or extra_keys:
        msg = []
        if missing_keys:
            msg.append(f"Missing keys: {sorted(missing_keys)}")
        if extra_keys:
            msg.append(f"Extra keys: {sorted(extra_keys)}")
        raise AssertionError("\n".join(msg))

    # Compare values for each key
    for key in actual_keys:
        if sorted(actual_filtered[key]) != sorted(expected_filtered[key]):
            raise AssertionError(
                f"Mismatch for key '{key}':\n"
                f"  Actual: {sorted(actual_filtered[key])}\n"
                f"  Expected: {sorted(expected_filtered[key])}"
            )

    return True


def create_minimal_tfdata(
    resources: list = None, metadata: dict = None
) -> Dict[str, Any]:
    """Create minimal tfdata structure for testing.

    Args:
        resources: List of resource names for graphdict
        metadata: Optional metadata dictionary

    Returns:
        Minimal tfdata dictionary with graphdict and meta_data

    Example:
        >>> tfdata = create_minimal_tfdata(
        ...     resources=["azurerm_resource_group.main", "azurerm_virtual_network.vnet"],
        ...     metadata={"azurerm_virtual_network.vnet": {"resource_group_name": "azurerm_resource_group.main"}}
        ... )
    """
    resources = resources or []
    metadata = metadata or {}

    tfdata = {"graphdict": {}, "meta_data": {}}

    # Initialize graphdict with empty lists
    for resource in resources:
        tfdata["graphdict"][resource] = []

    # Add metadata
    for resource, meta in metadata.items():
        tfdata["meta_data"][resource] = meta

    return tfdata


# ============================================================================
# Test Classes
# ============================================================================


class TestAzureProviderDetection:
    """Tests for Azure provider detection (T048)."""

    def test_detect_azure_provider(self):
        """Test that Azure resources are correctly detected as Azure provider."""
        tfdata = {
            "all_resource": [
                "azurerm_resource_group.test",
                "azurerm_virtual_network.test",
                "azurerm_subnet.test",
                "azurerm_storage_account.test",
                "azurerm_network_security_group.test",
            ]
        }

        result = detect_providers(tfdata)

        assert result["providers"] == ["azure"]
        assert result["primary_provider"] == "azure"
        assert result["resource_counts"]["azure"] == 5
        assert result["confidence"] == 1.0

    def test_detect_azuread_resources(self):
        """Test that AzureAD resources are detected as Azure."""
        tfdata = {
            "all_resource": [
                "azuread_user.admin",
                "azuread_group.developers",
                "azuread_application.app",
            ]
        }

        result = detect_providers(tfdata)

        assert result["primary_provider"] == "azure"
        assert result["resource_counts"]["azure"] == 3

    def test_detect_azurestack_resources(self):
        """Test that AzureStack resources are detected as Azure."""
        tfdata = {
            "all_resource": [
                "azurestack_virtual_network.vnet",
                "azurestack_virtual_machine.vm",
            ]
        }

        result = detect_providers(tfdata)

        assert result["primary_provider"] == "azure"
        assert result["resource_counts"]["azure"] == 2

    def test_detect_azapi_resources(self):
        """Test that AzAPI resources are detected as Azure."""
        tfdata = {
            "all_resource": ["azapi_resource.custom", "azapi_update_resource.update"]
        }

        result = detect_providers(tfdata)

        assert result["primary_provider"] == "azure"

    def test_get_provider_for_azure_resources(self):
        """Test get_provider_for_resource with various Azure resource types."""
        assert get_provider_for_resource("azurerm_virtual_machine.vm") == "azure"
        assert get_provider_for_resource("azurerm_resource_group.rg") == "azure"
        assert get_provider_for_resource("azuread_user.user") == "azure"
        assert get_provider_for_resource("azurestack_virtual_network.vnet") == "azure"
        assert get_provider_for_resource("azapi_resource.custom") == "azure"

    def test_mixed_azure_aws_detection(self):
        """Test detection with mixed Azure and AWS resources."""
        tfdata = {
            "all_resource": [
                "azurerm_resource_group.main",
                "azurerm_virtual_machine.vm1",
                "azurerm_virtual_machine.vm2",
                "aws_instance.web",
                "random_string.id",
            ]
        }

        result = detect_providers(tfdata)

        # Azure should be primary (3 vs 1 AWS)
        assert result["primary_provider"] == "azure"
        assert result["resource_counts"]["azure"] == 3
        assert result["resource_counts"]["aws"] == 1


class TestAzureResourceGrouping:
    """Tests for Azure resource grouping (T049)."""

    def test_azure_resource_grouping_basic(self):
        """Test basic resource grouping under resource groups."""
        tfdata = {
            "graphdict": {
                "azurerm_resource_group.main": [],
                "azurerm_virtual_network.vnet": [],
                "azurerm_storage_account.storage": [],
            },
            "meta_data": {
                "azurerm_resource_group.main": {},
                "azurerm_virtual_network.vnet": {
                    "resource_group_name": "azurerm_resource_group.main"
                },
                "azurerm_storage_account.storage": {
                    "resource_group_name": "azurerm_resource_group.main"
                },
            },
        }

        result = azure_handle_resource_group(tfdata)

        # VNet should be under resource group
        assert (
            "azurerm_virtual_network.vnet"
            in result["graphdict"]["azurerm_resource_group.main"]
        )

    def test_vnet_subnet_hierarchy(self):
        """Test VNet-Subnet hierarchy."""
        tfdata = {
            "graphdict": {
                "azurerm_virtual_network.vnet": [],
                "azurerm_subnet.subnet1": [],
                "azurerm_subnet.subnet2": [],
            },
            "meta_data": {
                "azurerm_virtual_network.vnet": {},
                "azurerm_subnet.subnet1": {
                    "virtual_network_name": "azurerm_virtual_network.vnet"
                },
                "azurerm_subnet.subnet2": {
                    "virtual_network_name": "azurerm_virtual_network.vnet"
                },
            },
        }

        result = azure_handle_vnet(tfdata)

        # Both subnets should be under VNet
        assert (
            "azurerm_subnet.subnet1"
            in result["graphdict"]["azurerm_virtual_network.vnet"]
        )
        assert (
            "azurerm_subnet.subnet2"
            in result["graphdict"]["azurerm_virtual_network.vnet"]
        )

    def test_nsg_subnet_association(self):
        """Test NSG-Subnet association handling."""
        tfdata = {
            "graphdict": {
                "azurerm_subnet.test": [],
                "azurerm_network_security_group.nsg": [],
                "azurerm_subnet_network_security_group_association.assoc": [],
            },
            "meta_data": {
                "azurerm_subnet.test": {},
                "azurerm_network_security_group.nsg": {},
                "azurerm_subnet_network_security_group_association.assoc": {
                    "subnet_id": "azurerm_subnet.test",
                    "network_security_group_id": "azurerm_network_security_group.nsg",
                },
            },
        }

        result = azure_handle_nsg(tfdata)

        # NSG should be under subnet
        assert (
            "azurerm_network_security_group.nsg"
            in result["graphdict"]["azurerm_subnet.test"]
        )
        # Association should be removed
        assert (
            "azurerm_subnet_network_security_group_association.assoc"
            not in result["graphdict"]
        )


class TestAzureResourceHandlers:
    """Tests for individual Azure resource handlers."""

    def test_handle_special_cases_disconnects_role_assignments(self):
        """Test that role assignments are disconnected."""
        tfdata = {
            "graphdict": {
                "azurerm_role_assignment.reader": ["azurerm_storage_account.storage"],
                "azurerm_storage_account.storage": [],
            },
            "meta_data": {},
        }

        result = handle_special_cases(tfdata)

        # Role assignment should have empty connections
        assert result["graphdict"]["azurerm_role_assignment.reader"] == []

    def test_azure_handle_vmss(self):
        """Test VMSS handler links to subnet."""
        tfdata = {
            "graphdict": {
                "azurerm_subnet.app_subnet": [],
                "azurerm_virtual_machine_scale_set.vmss": [],
            },
            "meta_data": {
                "azurerm_subnet.app_subnet": {},
                "azurerm_virtual_machine_scale_set.vmss": {
                    "network_profile": "subnet_id = azurerm_subnet.app_subnet.id"
                },
            },
        }

        result = azure_handle_vmss(tfdata)

        assert (
            "azurerm_virtual_machine_scale_set.vmss"
            in result["graphdict"]["azurerm_subnet.app_subnet"]
        )

    def test_azure_handle_appgw(self):
        """Test Application Gateway handler links to subnet."""
        tfdata = {
            "graphdict": {
                "azurerm_subnet.appgw_subnet": [],
                "azurerm_application_gateway.appgw": [],
            },
            "meta_data": {
                "azurerm_subnet.appgw_subnet": {},
                "azurerm_application_gateway.appgw": {
                    "gateway_ip_configuration": "subnet_id = azurerm_subnet.appgw_subnet.id"
                },
            },
        }

        result = azure_handle_appgw(tfdata)

        assert (
            "azurerm_application_gateway.appgw"
            in result["graphdict"]["azurerm_subnet.appgw_subnet"]
        )


class TestMatchResources:
    """Tests for match_resources helper functions."""

    def test_match_nsg_to_subnets_by_suffix(self):
        """Test NSG-Subnet matching by suffix pattern."""
        graphdict = {
            "azurerm_subnet.app~1": ["azurerm_network_security_group.nsg~1"],
            "azurerm_subnet.app~2": [],
            "azurerm_network_security_group.nsg~1": [],
            "azurerm_network_security_group.nsg~2": [],
        }

        result = match_nsg_to_subnets(graphdict)

        # NSG~2 should be matched to subnet~2
        assert "azurerm_network_security_group.nsg~2" in result["azurerm_subnet.app~2"]

    def test_match_nic_to_vm(self):
        """Test NIC-VM matching."""
        graphdict = {
            "azurerm_network_interface.nic": [],
            "azurerm_virtual_machine.vm": [],
        }
        meta_data = {
            "azurerm_virtual_machine.vm": {
                "network_interface_ids": "azurerm_network_interface.nic.id"
            }
        }

        result = match_nic_to_vm(graphdict, meta_data)

        assert "azurerm_virtual_machine.vm" in result["azurerm_network_interface.nic"]

    def test_remove_empty_groups(self):
        """Test removal of empty group nodes."""
        graphdict = {
            "azurerm_resource_group.empty": [],
            "azurerm_virtual_network.empty": [],
            "azurerm_storage_account.storage": [],
        }

        result = remove_empty_groups(graphdict)

        # Empty resource group should be removed
        assert "azurerm_resource_group.empty" not in result
        # Empty VNet should be removed
        assert "azurerm_virtual_network.empty" not in result
        # Non-group resource should remain
        assert "azurerm_storage_account.storage" in result


class TestAzureSubnetHandling:
    """Tests for Azure subnet resource handling."""

    def test_subnet_nic_linking(self):
        """Test NIC linking to subnets."""
        tfdata = {
            "graphdict": {
                "azurerm_subnet.web": [],
                "azurerm_network_interface.web_nic": [],
            },
            "meta_data": {
                "azurerm_subnet.web": {},
                "azurerm_network_interface.web_nic": {
                    "ip_configuration": "subnet_id = azurerm_subnet.web.id"
                },
            },
        }

        result = azure_handle_subnet(tfdata)

        assert (
            "azurerm_network_interface.web_nic"
            in result["graphdict"]["azurerm_subnet.web"]
        )

    def test_vm_linking_through_nic(self):
        """Test VM linking to subnet through NIC."""
        tfdata = {
            "graphdict": {
                "azurerm_subnet.web": ["azurerm_network_interface.nic"],
                "azurerm_network_interface.nic": [],
                "azurerm_virtual_machine.vm": [
                    "azurerm_network_interface.nic"
                ],  # VM -> NIC (correct direction)
            },
            "meta_data": {
                "azurerm_subnet.web": {},
                "azurerm_network_interface.nic": {
                    "ip_configuration": "subnet_id = azurerm_subnet.web.id"
                },
                "azurerm_virtual_machine.vm": {
                    "network_interface_ids": ["azurerm_network_interface.nic.id"]
                },
            },
        }

        # First link NICs to subnet
        result = azure_handle_subnet(tfdata)

        # Then place VMs into subnets (happens after numbering in real pipeline)
        from modules.resource_handlers_azure import place_vms_in_subnets

        result = place_vms_in_subnets(result)

        # VM should be linked to subnet (through NIC relationship)
        assert "azurerm_virtual_machine.vm" in result["graphdict"]["azurerm_subnet.web"]
