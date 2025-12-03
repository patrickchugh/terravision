"""Unit tests for modules/resource_handlers/gcp.py"""

import sys
import unittest
from pathlib import Path
from typing import Any, Dict

# Add modules directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.exceptions import MissingResourceError
from modules.resource_handlers.gcp import (gcp_handle_cloud_dns,
                                           gcp_handle_firewall, gcp_handle_lb,
                                           gcp_handle_network_subnets)


class TestGCPHandleNetworkSubnets(unittest.TestCase):
    """Test gcp_handle_network_subnets() for VPC network/subnet relationships."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_no_network_raises_error(self):
        """Test that subnets without VPC networks raise MissingResourceError."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {"google_compute_subnetwork.sub1": []}

        with self.assertRaises(MissingResourceError) as context:
            gcp_handle_network_subnets(tfdata)

        error = context.exception
        self.assertEqual(error.message, "google_compute_network")
        self.assertEqual(error.context["handler"], "gcp_handle_network_subnets")
        self.assertEqual(error.context["subnet_count"], 1)

    def test_groups_subnets_under_network(self):
        """Test that subnets are correctly grouped under VPC networks."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_subnetwork.sub1": [],
        }
        tfdata["meta_data"] = {"google_compute_subnetwork.sub1": {}}
        tfdata["original_metadata"] = {
            "google_compute_subnetwork.sub1": {
                "network": "main",
                "region": "us-central1",
            }
        }

        result = gcp_handle_network_subnets(tfdata)

        # Subnet should be child of network
        self.assertIn(
            "google_compute_subnetwork.sub1",
            result["graphdict"]["google_compute_network.main"],
        )
        # Subnet metadata should include network reference
        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.sub1"]["network"],
            "google_compute_network.main",
        )
        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.sub1"]["region"],
            "us-central1",
        )

    def test_matches_by_network_attribute(self):
        """Test subnet matching using network attribute from metadata."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.vpc1": [],
            "google_compute_subnetwork.subnet_a": [],
            "google_compute_subnetwork.subnet_b": [],
        }
        tfdata["meta_data"] = {
            "google_compute_subnetwork.subnet_a": {},
            "google_compute_subnetwork.subnet_b": {},
        }
        tfdata["original_metadata"] = {
            "google_compute_subnetwork.subnet_a": {"network": "vpc1"},
            "google_compute_subnetwork.subnet_b": {"network": "vpc1"},
        }

        result = gcp_handle_network_subnets(tfdata)

        # Both subnets should be children of vpc1
        self.assertIn(
            "google_compute_subnetwork.subnet_a",
            result["graphdict"]["google_compute_network.vpc1"],
        )
        self.assertIn(
            "google_compute_subnetwork.subnet_b",
            result["graphdict"]["google_compute_network.vpc1"],
        )

    def test_preserves_subnet_metadata(self):
        """Test that subnet metadata is preserved during processing."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_subnetwork.sub1": [],
        }
        tfdata["meta_data"] = {
            "google_compute_subnetwork.sub1": {"count": 1, "label": "test"}
        }
        tfdata["original_metadata"] = {
            "google_compute_subnetwork.sub1": {
                "network": "main",
                "region": "us-west1",
            },
            "google_compute_network.main": {"auto_create_subnetworks": False},
        }

        result = gcp_handle_network_subnets(tfdata)

        # Original metadata should be preserved
        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.sub1"]["count"], 1
        )
        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.sub1"]["label"], "test"
        )
        # New metadata should be added
        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.sub1"]["mode"], "custom"
        )

    def test_auto_mode_network_detection(self):
        """Test auto-mode network detection sets mode='auto' on subnets."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.auto_net": [],
            "google_compute_subnetwork.auto_sub": [],
        }
        tfdata["meta_data"] = {"google_compute_subnetwork.auto_sub": {}}
        tfdata["original_metadata"] = {
            "google_compute_subnetwork.auto_sub": {"network": "auto_net"},
            "google_compute_network.auto_net": {"auto_create_subnetworks": True},
        }

        result = gcp_handle_network_subnets(tfdata)

        self.assertEqual(
            result["meta_data"]["google_compute_subnetwork.auto_sub"]["mode"], "auto"
        )


class TestGCPHandleFirewall(unittest.TestCase):
    """Test gcp_handle_firewall() for firewall rule processing."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_adds_direction_to_metadata(self):
        """Test that firewall direction is added to metadata."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_firewall.fw1": [],
        }
        tfdata["meta_data"] = {"google_compute_firewall.fw1": {}}
        tfdata["original_metadata"] = {
            "google_compute_firewall.fw1": {
                "network": "main",
                "direction": "INGRESS",
            }
        }

        result = gcp_handle_firewall(tfdata)

        self.assertEqual(
            result["meta_data"]["google_compute_firewall.fw1"]["direction"], "INGRESS"
        )
        self.assertEqual(
            result["meta_data"]["google_compute_firewall.fw1"]["network"],
            "google_compute_network.main",
        )

    def test_handles_ingress_rules(self):
        """Test processing of INGRESS firewall rules."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_firewall.allow_ssh": [],
            "google_compute_instance.vm1": [],
        }
        tfdata["meta_data"] = {"google_compute_firewall.allow_ssh": {}}
        tfdata["original_metadata"] = {
            "google_compute_firewall.allow_ssh": {
                "network": "main",
                "direction": "INGRESS",
                "target_tags": ["ssh-server"],
            },
            "google_compute_instance.vm1": {
                "network": "main",
                "tags": ["ssh-server", "web-server"],
            },
        }

        result = gcp_handle_firewall(tfdata)

        # Firewall should wrap instance with matching tag
        self.assertIn(
            "google_compute_instance.vm1",
            result["graphdict"]["google_compute_firewall.allow_ssh"],
        )
        # Target tags should be in metadata
        self.assertEqual(
            result["meta_data"]["google_compute_firewall.allow_ssh"]["target_tags"],
            ["ssh-server"],
        )

    def test_handles_egress_rules(self):
        """Test processing of EGRESS firewall rules."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_firewall.deny_all": [],
        }
        tfdata["meta_data"] = {"google_compute_firewall.deny_all": {}}
        tfdata["original_metadata"] = {
            "google_compute_firewall.deny_all": {
                "network": "main",
                "direction": "EGRESS",
            }
        }

        result = gcp_handle_firewall(tfdata)

        self.assertEqual(
            result["meta_data"]["google_compute_firewall.deny_all"]["direction"],
            "EGRESS",
        )

    def test_processes_target_tags(self):
        """Test firewall rule target tag matching with instances."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_firewall.web_fw": [],
            "google_compute_instance.web1": [],
            "google_compute_instance.db1": [],
        }
        tfdata["meta_data"] = {"google_compute_firewall.web_fw": {}}
        tfdata["original_metadata"] = {
            "google_compute_firewall.web_fw": {
                "network": "main",
                "target_tags": ["web-tier"],
            },
            "google_compute_instance.web1": {
                "network": "main",
                "tags": ["web-tier"],
            },
            "google_compute_instance.db1": {
                "network": "main",
                "tags": ["db-tier"],
            },
        }

        result = gcp_handle_firewall(tfdata)

        # Only web1 should be wrapped by firewall
        self.assertIn(
            "google_compute_instance.web1",
            result["graphdict"]["google_compute_firewall.web_fw"],
        )
        self.assertNotIn(
            "google_compute_instance.db1",
            result["graphdict"]["google_compute_firewall.web_fw"],
        )

    def test_firewall_without_target_tags_applies_to_all(self):
        """Test firewall without target tags applies to all instances in network."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.main": [],
            "google_compute_firewall.allow_all": [],
            "google_compute_instance.vm1": [],
            "google_compute_instance.vm2": [],
        }
        tfdata["meta_data"] = {"google_compute_firewall.allow_all": {}}
        tfdata["original_metadata"] = {
            "google_compute_firewall.allow_all": {
                "network": "main",
                "target_tags": [],  # No target tags - applies to all
            },
            "google_compute_instance.vm1": {"network": "main", "tags": ["web"]},
            "google_compute_instance.vm2": {"network": "main", "tags": ["db"]},
        }

        result = gcp_handle_firewall(tfdata)

        # Both instances should be wrapped
        self.assertIn(
            "google_compute_instance.vm1",
            result["graphdict"]["google_compute_firewall.allow_all"],
        )
        self.assertIn(
            "google_compute_instance.vm2",
            result["graphdict"]["google_compute_firewall.allow_all"],
        )


class TestGCPHandleLB(unittest.TestCase):
    """Test gcp_handle_lb() for load balancer type detection."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_detects_http_lb(self):
        """Test detection of HTTP(S) load balancer from backend service."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.http_backend": ["instance1"],
            "instance1": [],
        }
        tfdata["meta_data"] = {
            "google_compute_backend_service.http_backend": {"count": 1}
        }
        tfdata["original_metadata"] = {
            "google_compute_backend_service.http_backend": {
                "load_balancing_scheme": "EXTERNAL",
                "protocol": "HTTP",
            }
        }

        result = gcp_handle_lb(tfdata)

        # HTTP LB node should be created
        self.assertIn("google_compute_http_lb.lb", result["graphdict"])
        # Connections should be transferred
        self.assertIn("instance1", result["graphdict"]["google_compute_http_lb.lb"])
        # Metadata should be set
        self.assertEqual(
            result["meta_data"]["google_compute_http_lb.lb"]["type"],
            "google_compute_http_lb",
        )

    def test_detects_https_lb(self):
        """Test detection of HTTPS load balancer."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.https_backend": [],
        }
        tfdata["meta_data"] = {"google_compute_backend_service.https_backend": {}}
        tfdata["original_metadata"] = {
            "google_compute_backend_service.https_backend": {
                "load_balancing_scheme": "EXTERNAL",
                "protocol": "HTTPS",
            }
        }

        result = gcp_handle_lb(tfdata)

        # HTTPS should also map to HTTP LB
        self.assertIn("google_compute_http_lb.lb", result["graphdict"])

    def test_detects_tcp_lb(self):
        """Test detection of TCP/SSL load balancer."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.tcp_backend": [],
        }
        tfdata["meta_data"] = {"google_compute_backend_service.tcp_backend": {}}
        tfdata["original_metadata"] = {
            "google_compute_backend_service.tcp_backend": {
                "load_balancing_scheme": "EXTERNAL",
                "protocol": "TCP",
            }
        }

        result = gcp_handle_lb(tfdata)

        self.assertIn("google_compute_tcp_lb.lb", result["graphdict"])

    def test_detects_ssl_lb(self):
        """Test detection of SSL load balancer."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.ssl_backend": [],
        }
        tfdata["meta_data"] = {"google_compute_backend_service.ssl_backend": {}}
        tfdata["original_metadata"] = {
            "google_compute_backend_service.ssl_backend": {
                "load_balancing_scheme": "EXTERNAL",
                "protocol": "SSL",
            }
        }

        result = gcp_handle_lb(tfdata)

        # SSL should map to TCP LB
        self.assertIn("google_compute_tcp_lb.lb", result["graphdict"])

    def test_detects_internal_lb(self):
        """Test detection of internal load balancer."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.internal_backend": [],
        }
        tfdata["meta_data"] = {"google_compute_backend_service.internal_backend": {}}
        tfdata["original_metadata"] = {
            "google_compute_backend_service.internal_backend": {
                "load_balancing_scheme": "INTERNAL",
                "protocol": "TCP",
            }
        }

        result = gcp_handle_lb(tfdata)

        self.assertIn("google_compute_internal_lb.lb", result["graphdict"])

    def test_updates_metadata_with_lb_type(self):
        """Test that LB metadata is correctly set based on type."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.backend": [],
        }
        tfdata["meta_data"] = {
            "google_compute_backend_service.backend": {"custom_key": "custom_value"}
        }
        tfdata["original_metadata"] = {
            "google_compute_backend_service.backend": {
                "load_balancing_scheme": "EXTERNAL",
                "protocol": "HTTP",
            }
        }

        result = gcp_handle_lb(tfdata)

        lb_metadata = result["meta_data"]["google_compute_http_lb.lb"]
        # Standard metadata
        self.assertEqual(lb_metadata["type"], "google_compute_http_lb")
        self.assertEqual(lb_metadata["provider"], "gcp")
        # Custom metadata should be copied
        self.assertEqual(lb_metadata["custom_key"], "custom_value")

    def test_forwarding_rule_links_to_backend(self):
        """Test forwarding rules are linked to backend services."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_backend_service.backend": [],
            "google_compute_forwarding_rule.frontend": [],
        }
        tfdata["meta_data"] = {"google_compute_backend_service.backend": {}}
        tfdata["original_metadata"] = {
            "google_compute_backend_service.backend": {
                "load_balancing_scheme": "EXTERNAL",
                "protocol": "HTTP",
            },
            "google_compute_forwarding_rule.frontend": {
                "backend_service": "google_compute_backend_service.backend"
            },
        }

        result = gcp_handle_lb(tfdata)

        # Forwarding rule should be linked to backend
        self.assertIn(
            "google_compute_forwarding_rule.frontend",
            result["graphdict"]["google_compute_backend_service.backend"],
        )


class TestGCPHandleCloudDNS(unittest.TestCase):
    """Test gcp_handle_cloud_dns() for Cloud DNS zone and record processing."""

    def _base_tfdata(self) -> Dict[str, Any]:
        return {
            "graphdict": {},
            "meta_data": {},
            "original_metadata": {},
        }

    def test_public_dns_zone_detection(self):
        """Test detection of public DNS zones."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {"google_dns_managed_zone.public_zone": []}
        tfdata["meta_data"] = {"google_dns_managed_zone.public_zone": {}}
        tfdata["original_metadata"] = {
            "google_dns_managed_zone.public_zone": {"visibility": "public"}
        }

        result = gcp_handle_cloud_dns(tfdata)

        self.assertEqual(
            result["meta_data"]["google_dns_managed_zone.public_zone"]["zone_type"],
            "public",
        )
        self.assertEqual(
            result["meta_data"]["google_dns_managed_zone.public_zone"]["visibility"],
            "public",
        )

    def test_private_dns_zone_detection(self):
        """Test detection of private DNS zones."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {"google_dns_managed_zone.private_zone": []}
        tfdata["meta_data"] = {"google_dns_managed_zone.private_zone": {}}
        tfdata["original_metadata"] = {
            "google_dns_managed_zone.private_zone": {"visibility": "private"}
        }

        result = gcp_handle_cloud_dns(tfdata)

        self.assertEqual(
            result["meta_data"]["google_dns_managed_zone.private_zone"]["zone_type"],
            "private",
        )

    def test_dns_records_grouped_under_zone(self):
        """Test DNS records are grouped under their managed zones."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_dns_managed_zone.zone1": [],
            "google_dns_record_set.record_a": [],
            "google_dns_record_set.record_cname": [],
        }
        tfdata["meta_data"] = {
            "google_dns_record_set.record_a": {},
            "google_dns_record_set.record_cname": {},
        }
        tfdata["original_metadata"] = {
            "google_dns_record_set.record_a": {
                "managed_zone": "zone1",
                "type": "A",
            },
            "google_dns_record_set.record_cname": {
                "managed_zone": "zone1",
                "type": "CNAME",
            },
        }

        result = gcp_handle_cloud_dns(tfdata)

        # Both records should be children of the zone
        self.assertIn(
            "google_dns_record_set.record_a",
            result["graphdict"]["google_dns_managed_zone.zone1"],
        )
        self.assertIn(
            "google_dns_record_set.record_cname",
            result["graphdict"]["google_dns_managed_zone.zone1"],
        )
        # Record types should be in metadata
        self.assertEqual(
            result["meta_data"]["google_dns_record_set.record_a"]["record_type"], "A"
        )
        self.assertEqual(
            result["meta_data"]["google_dns_record_set.record_cname"]["record_type"],
            "CNAME",
        )

    def test_dnssec_configuration(self):
        """Test DNSSEC configuration detection."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {"google_dns_managed_zone.secure_zone": []}
        tfdata["meta_data"] = {"google_dns_managed_zone.secure_zone": {}}
        tfdata["original_metadata"] = {
            "google_dns_managed_zone.secure_zone": {
                "visibility": "public",
                "dnssec_config": {"state": "on"},
            }
        }

        result = gcp_handle_cloud_dns(tfdata)

        self.assertTrue(
            result["meta_data"]["google_dns_managed_zone.secure_zone"]["dnssec_enabled"]
        )

    def test_private_zone_vpc_linking(self):
        """Test private zones are linked to VPC networks."""
        tfdata = self._base_tfdata()
        tfdata["graphdict"] = {
            "google_compute_network.vpc1": [],
            "google_dns_managed_zone.private_zone": [],
        }
        tfdata["meta_data"] = {"google_dns_managed_zone.private_zone": {}}
        tfdata["original_metadata"] = {
            "google_dns_managed_zone.private_zone": {
                "visibility": "private",
                "private_visibility_config": {"networks": [{"network_url": "vpc1"}]},
            }
        }

        result = gcp_handle_cloud_dns(tfdata)

        # Zone should be linked to VPC
        self.assertIn(
            "google_dns_managed_zone.private_zone",
            result["graphdict"]["google_compute_network.vpc1"],
        )


if __name__ == "__main__":
    unittest.main()
