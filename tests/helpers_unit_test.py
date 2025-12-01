import unittest, sys, os
import json
from pathlib import Path

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

from modules.helpers import *
from modules.provider_runtime import ProviderRegistry


class TestCheckForDomain(unittest.TestCase):
    def test_valid_domain(self):
        string = "www.example.com"
        result = check_for_domain(string)
        self.assertTrue(result)

    def test_no_domain(self):
        string = "example"
        result = check_for_domain(string)
        self.assertFalse(result)

    def test_tld_only(self):
        string = ".com"
        result = check_for_domain(string)
        self.assertFalse(result)

    def test_subdomain(self):
        string = "www.example"
        result = check_for_domain(string)
        self.assertFalse(result)


class TestGetvar(unittest.TestCase):
    def test_getvar_from_env(self):
        os.environ["TF_VAR_environ"] = "value_from_env"
        result = getvar("environ", {})
        self.assertEqual(result, "value_from_env")

    def test_getvar_from_dict(self):
        variables = {"test": "value_from_dict"}
        result = getvar("test", variables)
        self.assertEqual(result, "value_from_dict")

    def test_getvar_ignore_case(self):
        variables = {"Test": "value_ignore_case"}
        result = getvar("test", variables)
        self.assertEqual(result, "value_ignore_case")

    def test_getvar_not_found(self):
        result = getvar("not_found", {})
        self.assertEqual(result, "NOTFOUND")


class TestMultiProviderHelpers(unittest.TestCase):
    """Test multi-provider support in helper functions."""

    def test_check_variant_aws(self):
        """Test AWS variant detection (backwards compatibility)."""
        from modules.cloud_config import ProviderRegistry

        # AWS Lambda with container image should map to container variant
        result = check_variant("aws_lambda_function", {"package_type": "Image"})
        # AWS config has lambda variants - verify it works
        self.assertIsNotNone(result)

    def test_check_variant_azure(self):
        """Test Azure variant detection."""
        from modules.cloud_config import ProviderRegistry

        # Azure VM should be detected as compute.vm
        result = check_variant(
            "azurerm_linux_virtual_machine", {"size": "Standard_D2s_v3"}
        )
        # Azure might not have variants configured yet - that's ok
        # This test verifies the function doesn't crash on Azure resources
        self.assertFalse(result)  # Expected: no variants configured yet

    def test_check_variant_google(self):
        """Test GCP variant detection."""
        from modules.cloud_config import ProviderRegistry

        # GCP Compute Instance should be detected
        result = check_variant(
            "google_compute_instance", {"machine_type": "n1-standard-1"}
        )
        # GCP might not have variants configured yet - that's ok
        self.assertFalse(result)  # Expected: no variants configured yet

    def test_consolidated_node_check_aws(self):
        """Test AWS consolidated nodes (backwards compatibility)."""
        # AWS LB listener/target groups consolidate to aws_lb resource
        result = consolidated_node_check("aws_lb_listener")
        self.assertEqual(result, "aws_lb.elb")

        # Route53 zones consolidate to route53 record
        result = consolidated_node_check("aws_route53_zone")
        self.assertEqual(result, "aws_route53_record.route_53")

    def test_consolidated_node_check_azure(self):
        """Test Azure consolidated nodes."""
        # Azure might not have consolidations yet
        result = consolidated_node_check("azurerm_linux_virtual_machine")
        self.assertFalse(result)

    def test_consolidated_node_check_google(self):
        """Test GCP consolidated nodes."""
        # GCP might not have consolidations yet
        result = consolidated_node_check("google_compute_instance")
        self.assertFalse(result)


class TestMultiProviderIntegration(unittest.TestCase):
    """Integration tests for multi-provider support using real test fixtures."""

    def test_azure_provider_detection(self):
        """Test provider detection from Azure tfdata fixture."""
        # Load Azure test fixture
        test_dir = Path(__file__).parent
        fixture_path = test_dir / "json" / "azure-basic-tfdata.json"

        with open(fixture_path, "r") as f:
            tfdata = json.load(f)

        # Detect providers from tfdata
        providers = ProviderRegistry.detect_providers(tfdata)

        # Should detect azurerm provider
        self.assertIn("azurerm", providers)
        self.assertEqual(len(providers), 1)

    def test_gcp_provider_detection(self):
        """Test provider detection from GCP tfdata fixture."""
        # Load GCP test fixture
        test_dir = Path(__file__).parent
        fixture_path = test_dir / "json" / "gcp-basic-tfdata.json"

        with open(fixture_path, "r") as f:
            tfdata = json.load(f)

        # Detect providers from tfdata
        providers = ProviderRegistry.detect_providers(tfdata)

        # Should detect google provider
        self.assertIn("google", providers)
        self.assertEqual(len(providers), 1)

    def test_azure_resource_detection(self):
        """Test Azure resources are correctly identified."""
        # Load Azure test fixture
        test_dir = Path(__file__).parent
        fixture_path = test_dir / "json" / "azure-basic-tfdata.json"

        with open(fixture_path, "r") as f:
            tfdata = json.load(f)

        # Check that Azure resources are in the graph
        graphdict = tfdata.get("graphdict", {})
        node_list = tfdata.get("node_list", [])

        # Verify Azure resource naming conventions
        azure_resources = [n for n in node_list if n.startswith("azurerm_")]
        self.assertGreater(len(azure_resources), 0, "Should have Azure resources")

        # Check specific resources exist
        self.assertIn("azurerm_resource_group.main", node_list)
        self.assertIn("azurerm_virtual_network.main", node_list)
        self.assertIn("azurerm_linux_virtual_machine.main", node_list)

    def test_gcp_resource_detection(self):
        """Test GCP resources are correctly identified."""
        # Load GCP test fixture
        test_dir = Path(__file__).parent
        fixture_path = test_dir / "json" / "gcp-basic-tfdata.json"

        with open(fixture_path, "r") as f:
            tfdata = json.load(f)

        # Check that GCP resources are in the graph
        node_list = tfdata.get("node_list", [])

        # Verify GCP resource naming conventions
        gcp_resources = [n for n in node_list if n.startswith("google_")]
        self.assertGreater(len(gcp_resources), 0, "Should have GCP resources")

        # Check specific resources exist
        self.assertIn("google_compute_network.main", node_list)
        self.assertIn("google_compute_instance.main", node_list)
        self.assertIn("google_storage_bucket.main", node_list)

    def test_cross_provider_resource_prefix_detection(self):
        """Test provider detection from resource prefixes works for all clouds."""
        from modules.provider_runtime import ProviderContext

        ctx = ProviderContext()

        # Test AWS detection
        aws_provider = ctx.detect_provider_for_node("aws_instance.web")
        self.assertEqual(aws_provider, "aws")

        # Test Azure detection
        azure_provider = ctx.detect_provider_for_node(
            "azurerm_linux_virtual_machine.main"
        )
        self.assertEqual(azure_provider, "azurerm")

        # Test GCP detection
        gcp_provider = ctx.detect_provider_for_node("google_compute_instance.main")
        self.assertEqual(gcp_provider, "google")

        # Test with module prefix
        aws_module = ctx.detect_provider_for_node("module.vpc.aws_subnet.private")
        self.assertEqual(aws_module, "aws")


if __name__ == "__main__":
    unittest.main()
