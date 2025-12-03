import unittest
import sys
import os
import time
import json
from pathlib import Path

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

from modules.provider_runtime import ProviderRegistry, ProviderContext
from modules.helpers import check_variant, consolidated_node_check


class TestProviderPerformance(unittest.TestCase):
    """Performance tests for multi-provider operations."""

    def setUp(self):
        """Load test fixtures once for all tests."""
        test_dir = Path(__file__).parent

        # Load Azure fixture
        with open(test_dir / "json" / "azure-basic-tfdata.json", "r") as f:
            self.azure_tfdata = json.load(f)

        # Load GCP fixture
        with open(test_dir / "json" / "gcp-basic-tfdata.json", "r") as f:
            self.gcp_tfdata = json.load(f)

    def test_provider_detection_performance(self):
        """Test provider detection completes within 50ms."""
        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            ProviderRegistry.detect_providers(self.azure_tfdata)
            ProviderRegistry.detect_providers(self.gcp_tfdata)
        end = time.perf_counter()

        avg_time_ms = ((end - start) / iterations / 2) * 1000

        print(
            f"\nProvider detection: {avg_time_ms:.2f}ms avg ({iterations} iterations)"
        )

        # Should be under 50ms per detection
        self.assertLess(
            avg_time_ms,
            50,
            f"Provider detection took {avg_time_ms:.2f}ms (target: <50ms)",
        )

    def test_provider_context_creation_performance(self):
        """Test ProviderContext creation is fast (<10ms)."""
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            ctx = ProviderContext()
        end = time.perf_counter()

        avg_time_ms = ((end - start) / iterations) * 1000

        print(
            f"\nProviderContext creation: {avg_time_ms:.4f}ms avg ({iterations} iterations)"
        )

        # Should be under 10ms
        self.assertLess(
            avg_time_ms,
            10,
            f"ProviderContext creation took {avg_time_ms:.4f}ms (target: <10ms)",
        )

    def test_provider_config_loading_performance(self):
        """Test provider config loading with caching (<5ms after first load)."""
        ctx = ProviderContext()

        # First load (uncached)
        start = time.perf_counter()
        ctx.get_config("aws")
        ctx.get_config("azurerm")
        ctx.get_config("google")
        end = time.perf_counter()

        first_load_ms = (end - start) * 1000
        print(f"\nFirst config load (uncached): {first_load_ms:.2f}ms")

        # Cached loads
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            ctx.get_config("aws")
            ctx.get_config("azurerm")
            ctx.get_config("google")
        end = time.perf_counter()

        cached_avg_ms = ((end - start) / iterations / 3) * 1000

        print(
            f"Cached config load: {cached_avg_ms:.4f}ms avg ({iterations} iterations)"
        )

        # Cached loads should be under 5ms
        self.assertLess(
            cached_avg_ms,
            5,
            f"Cached config load took {cached_avg_ms:.4f}ms (target: <5ms)",
        )

    def test_check_variant_performance(self):
        """Test check_variant across providers (<2ms)."""
        test_cases = [
            ("aws_lambda_function", {"package_type": "Image"}),
            ("azurerm_linux_virtual_machine", {"size": "Standard_D2s_v3"}),
            ("google_compute_instance", {"machine_type": "n1-standard-1"}),
        ]

        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            for resource, metadata in test_cases:
                check_variant(resource, metadata)
        end = time.perf_counter()

        avg_time_ms = ((end - start) / iterations / len(test_cases)) * 1000

        print(f"\ncheck_variant: {avg_time_ms:.4f}ms avg ({iterations} iterations)")

        # Should be under 2ms per call
        self.assertLess(
            avg_time_ms, 2, f"check_variant took {avg_time_ms:.4f}ms (target: <2ms)"
        )

    def test_consolidated_node_check_performance(self):
        """Test consolidated_node_check across providers (<2ms)."""
        test_cases = [
            "aws_lb_listener",
            "aws_route53_zone",
            "azurerm_linux_virtual_machine",
            "google_compute_instance",
        ]

        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            for resource in test_cases:
                consolidated_node_check(resource)
        end = time.perf_counter()

        avg_time_ms = ((end - start) / iterations / len(test_cases)) * 1000

        print(
            f"\nconsolidated_node_check: {avg_time_ms:.4f}ms avg ({iterations} iterations)"
        )

        # Should be under 2ms per call
        self.assertLess(
            avg_time_ms,
            2,
            f"consolidated_node_check took {avg_time_ms:.4f}ms (target: <2ms)",
        )

    def test_end_to_end_overhead(self):
        """Test total overhead of multi-provider operations (<200ms)."""
        # Simulate processing a multi-provider graph
        iterations = 100

        test_nodes = [
            "aws_instance.web",
            "aws_lb_listener.main",
            "azurerm_linux_virtual_machine.main",
            "azurerm_virtual_network.main",
            "google_compute_instance.main",
            "google_storage_bucket.main",
        ]

        start = time.perf_counter()
        for _ in range(iterations):
            # Detect providers
            providers = ProviderRegistry.detect_providers(self.azure_tfdata)

            # Create context
            ctx = ProviderContext()

            # Process each node
            for node in test_nodes:
                provider = ctx.detect_provider_for_node(node)
                if provider:
                    config = ctx.get_config(provider)
                    # Simulate variant and consolidation checks
                    check_variant(node.split(".")[0], {})
                    consolidated_node_check(node.split(".")[0])

        end = time.perf_counter()

        avg_time_ms = ((end - start) / iterations) * 1000

        print(
            f"\nEnd-to-end overhead: {avg_time_ms:.2f}ms avg ({iterations} iterations)"
        )
        print(f"  - Nodes per iteration: {len(test_nodes)}")
        print(f"  - Per-node overhead: {avg_time_ms / len(test_nodes):.2f}ms")

        # Total overhead should be under 200ms
        self.assertLess(
            avg_time_ms,
            200,
            f"End-to-end overhead was {avg_time_ms:.2f}ms (target: <200ms)",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
