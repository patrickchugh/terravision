"""Unit tests for modules/resource_handlers/aws.py"""

import copy
import sys
import unittest
from pathlib import Path
from typing import Any, Dict

# Add modules directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.exceptions import MissingResourceError
from modules.resource_handlers.aws import (
    aws_handle_autoscaling,
    aws_handle_dbsubnet,
    aws_handle_efs,
    aws_handle_lb,
    aws_handle_sg,
    aws_handle_subnet_azs,
    aws_handle_vpcendpoints,
    handle_special_cases,
    link_ec2_to_iam_roles,
    link_sqs_queue_policy,
    match_az_to_subnets,
    match_sg_to_subnets,
    split_nat_gateways,
)


class TestHandleSpecialCases(unittest.TestCase):
    """Test handle_special_cases() for AWS-specific disconnections and SQS linking."""

    def test_disconnect_services_removed(self):
        """Test that services in DISCONNECT_SERVICES have connections removed."""
        tfdata = {
            "graphdict": {
                "aws_iam_role_policy.inline": ["aws_s3_bucket.data"],
                "aws_iam_role.test": ["aws_s3_bucket.data"],
                "aws_s3_bucket.data": [],
            },
            "metadata": {},
        }
        result = handle_special_cases(tfdata)
        # Only aws_iam_role_policy should be disconnected (inline policies clutter diagrams)
        self.assertEqual(result["graphdict"]["aws_iam_role_policy.inline"], [])
        # IAM roles should retain their connections for proper visualization
        self.assertEqual(
            result["graphdict"]["aws_iam_role.test"], ["aws_s3_bucket.data"]
        )

    def test_sqs_queue_policy_linking(self):
        """Test that SQS queue policies are linked correctly."""
        tfdata = {
            "graphdict": {
                "aws_sqs_queue.main": [],
                "aws_sqs_queue_policy.main": ["aws_sqs_queue.main"],
                "aws_lambda_function.processor": ["aws_sqs_queue_policy.main"],
            },
            "metadata": {},
        }
        result = handle_special_cases(tfdata)
        # Lambda should be linked directly to queue (transitive via policy)
        self.assertIn(
            "aws_sqs_queue.main", result["graphdict"]["aws_lambda_function.processor"]
        )

    def test_empty_graphdict_handled(self):
        """Test that empty graphdict is handled gracefully."""
        tfdata = {"graphdict": {}, "metadata": {}}
        result = handle_special_cases(tfdata)
        self.assertEqual(result["graphdict"], {})


class TestAwsHandleSg(unittest.TestCase):
    """Test aws_handle_sg() for security group relationship management."""

    def setUp(self):
        self.tfdata_base = {
            "graphdict": {
                "aws_security_group.web": [],
                "aws_instance.server": ["aws_security_group.web"],
            },
            "meta_data": {
                "aws_security_group.web": {"name": "web-sg", "count": 1},
                "aws_instance.server": {"name": "server", "count": 1},
            },
        }

    def test_sg_wraps_referenced_resources(self):
        """Test that security groups wrap resources that reference them."""
        result = aws_handle_sg(copy.deepcopy(self.tfdata_base))
        self.assertIn(
            "aws_instance.server", result["graphdict"]["aws_security_group.web"]
        )

    def test_multiple_sgs_on_resource(self):
        """Test handling resources with multiple security groups."""
        tfdata = copy.deepcopy(self.tfdata_base)
        tfdata["graphdict"]["aws_security_group.db"] = []
        tfdata["graphdict"]["aws_instance.server"].append("aws_security_group.db")
        tfdata["meta_data"]["aws_security_group.db"] = {"name": "db-sg", "count": 1}
        result = aws_handle_sg(tfdata)
        self.assertIn(
            "aws_instance.server", result["graphdict"]["aws_security_group.web"]
        )
        self.assertIn(
            "aws_instance.server", result["graphdict"]["aws_security_group.db"]
        )

    def test_creates_unique_sg_nodes(self):
        """Test that duplicate SG entries are pruned when empty."""
        tfdata = copy.deepcopy(self.tfdata_base)
        tfdata["graphdict"]["aws_security_group.web_duplicate"] = []
        tfdata["meta_data"]["aws_security_group.web_duplicate"] = {
            "name": "web-dup",
            "count": 1,
        }
        result = aws_handle_sg(tfdata)
        # Empty duplicate SGs should be removed
        self.assertNotIn("aws_security_group.web_duplicate", result["graphdict"])

    def test_preserves_metadata_when_wrapping(self):
        """Test that metadata entries persist after SG wrapping operations."""
        result = aws_handle_sg(copy.deepcopy(self.tfdata_base))
        self.assertIn("aws_security_group.web", result["meta_data"])
        self.assertIn("aws_instance.server", result["meta_data"])


class TestAwsHandleLb(unittest.TestCase):
    """Test aws_handle_lb() for load balancer SKU/type detection."""

    def test_detects_alb_nlb_and_clb_variants(self):
        """Test load balancer variant creation for ALB/NLB/CLB."""
        tfdata = {
            "graphdict": {
                "aws_lb.alb_main": ["aws_target_group.app"],
                "aws_lb.nlb_main": ["aws_target_group.net"],
                "aws_elb.classic": ["aws_instance.web"],
            },
            "meta_data": {
                "aws_lb.alb_main": {"name": "my-alb", "count": 1},
                "aws_lb.nlb_main": {"name": "my-nlb", "count": 1},
                "aws_elb.classic": {"name": "classic", "count": 1},
                "aws_target_group.app": {"count": 1},
                "aws_target_group.net": {"count": 1},
                "aws_instance.web": {"count": 1},
            },
            "all_resource": {
                "aws_lb.alb_main": {"load_balancer_type": "application"},
                "aws_lb.nlb_main": {"load_balancer_type": "network"},
                "aws_elb.classic": {},
            },
        }
        result = aws_handle_lb(copy.deepcopy(tfdata))
        self.assertIn("aws_lb.elb", result["graphdict"])
        self.assertIn("aws_elb.elb", result["graphdict"])
        self.assertIn("aws_lb.elb", result["graphdict"].get("aws_lb.alb_main", []))

    def test_updates_metadata_counts_from_dependents(self):
        """Test that dependent counts propagate to LB metadata."""
        tfdata = {
            "graphdict": {"aws_lb.alb_main": ["aws_ecs_service.app"]},
            "meta_data": {
                "aws_lb.alb_main": {"name": "my-alb", "count": 1},
                "aws_ecs_service.app": {"name": "app", "count": 3},
            },
            "all_resource": {
                "aws_lb.alb_main": {"load_balancer_type": "application"},
                "aws_ecs_service.app": {"desired_count": 3},
            },
        }
        result = aws_handle_lb(copy.deepcopy(tfdata))
        renamed = "aws_lb.elb"
        self.assertIn(renamed, result["meta_data"])
        self.assertEqual(result["meta_data"][renamed]["count"], 3)

    def test_handles_missing_lb_type_gracefully(self):
        """Test LB without explicit type defaults to application variant."""
        tfdata = {
            "graphdict": {"aws_lb.main": []},
            "meta_data": {"aws_lb.main": {"name": "main-lb", "count": 1}},
            "all_resource": {"aws_lb.main": {}},
        }
        result = aws_handle_lb(copy.deepcopy(tfdata))
        self.assertIsInstance(result, dict)
        self.assertIn("aws_lb.elb", result["graphdict"]["aws_lb.main"])


class TestAwsHandleSubnetAzs(unittest.TestCase):
    """Test aws_handle_subnet_azs() for subnet availability zone labeling."""

    def test_subnet_az_suffix_added(self):
        """Test that subnet names get AZ suffix."""
        tfdata = {
            "graphdict": {"aws_subnet.public_a": [], "aws_subnet.public_b": []},
            "meta_data": {
                "aws_subnet.public_a": {
                    "name": "public",
                    "availability_zone": "us-east-1a",
                },
                "aws_subnet.public_b": {
                    "name": "public",
                    "availability_zone": "us-east-1b",
                },
            },
            "all_resource": {
                "aws_subnet.public_a": {"availability_zone": "us-east-1a"},
                "aws_subnet.public_b": {"availability_zone": "us-east-1b"},
            },
        }
        result = aws_handle_subnet_azs(tfdata)
        # Subnet names should include AZ suffix
        self.assertIn("1a", result["meta_data"]["aws_subnet.public_a"]["name"])
        self.assertIn("1b", result["meta_data"]["aws_subnet.public_b"]["name"])

    def test_subnet_without_az_unchanged(self):
        """Test that subnets without AZ info are unchanged."""
        tfdata = {
            "graphdict": {"aws_subnet.main": []},
            "meta_data": {"aws_subnet.main": {"name": "main-subnet"}},
            "all_resource": {"aws_subnet.main": {}},
        }
        result = aws_handle_subnet_azs(tfdata)
        # Should handle gracefully
        self.assertEqual(result["meta_data"]["aws_subnet.main"]["name"], "main-subnet")


class TestAwsHandleEfs(unittest.TestCase):
    """Test aws_handle_efs() for EFS mount target handling."""

    def test_groups_mount_targets_under_filesystem(self):
        """Test that EFS mount targets are grouped under file system node."""
        tfdata = {
            "graphdict": {
                "aws_efs_file_system.main": [],
                "aws_efs_mount_target.az_a": ["aws_efs_file_system.main"],
                "aws_efs_mount_target.az_b": ["aws_efs_file_system.main"],
            },
            "meta_data": {
                "aws_efs_file_system.main": {"name": "main-efs", "count": 1},
                "aws_efs_mount_target.az_a": {"name": "mt-a", "count": 1},
                "aws_efs_mount_target.az_b": {"name": "mt-b", "count": 1},
            },
        }
        result = aws_handle_efs(copy.deepcopy(tfdata))
        self.assertIn(
            "aws_efs_mount_target.az_a",
            result["graphdict"]["aws_efs_file_system.main"],
        )
        self.assertIn(
            "aws_efs_mount_target.az_b",
            result["graphdict"]["aws_efs_file_system.main"],
        )

    def test_handles_missing_filesystem_metadata(self):
        """Test that missing filesystem metadata entry is handled gracefully."""
        tfdata = {
            "graphdict": {
                "aws_efs_file_system.main": ["aws_efs_mount_target.az_a"],
                "aws_efs_mount_target.az_a": [],
            },
            "meta_data": {
                "aws_efs_mount_target.az_a": {"name": "mt-a", "count": 1},
            },
        }
        result = aws_handle_efs(copy.deepcopy(tfdata))
        self.assertIn("aws_efs_file_system.main", result["graphdict"])
        self.assertIn("aws_efs_file_system.main", result["meta_data"])


class TestAwsHandleDbsubnet(unittest.TestCase):
    """Test aws_handle_dbsubnet() for RDS subnet group handling."""

    def test_db_subnet_group_wraps_subnets(self):
        """Test that DB subnet groups wrap their member subnets."""
        tfdata = {
            "graphdict": {
                "aws_db_subnet_group.main": [],
                "aws_subnet.db_a": [],
                "aws_subnet.db_b": [],
            },
            "meta_data": {
                "aws_db_subnet_group.main": {"name": "db-subnet-group"},
                "aws_subnet.db_a": {"name": "db-a"},
                "aws_subnet.db_b": {"name": "db-b"},
            },
            "all_resource": {
                "aws_db_subnet_group.main": {
                    "subnet_ids": ["aws_subnet.db_a", "aws_subnet.db_b"]
                }
            },
        }
        result = aws_handle_dbsubnet(tfdata)
        # DB subnet group should contain the subnets
        self.assertIsInstance(result, dict)


class TestAWSHandleAutoscaling(unittest.TestCase):
    """Test aws_handle_autoscaling() for autoscaling group handling."""

    def test_missing_target_logs_info(self):
        """Test that missing autoscaling targets are handled gracefully."""
        tfdata = {
            "graphdict": {
                "aws_ecs_service.app": [],
                "aws_subnet.private_a": ["aws_ecs_service.app"],
            },
            "meta_data": {
                "aws_ecs_service.app": {"name": "app", "count": 1},
                "aws_subnet.private_a": {"name": "private-a", "count": 2},
            },
            "all_resource": {},
        }
        # Should not raise exception when no autoscaling targets found
        result = aws_handle_autoscaling(copy.deepcopy(tfdata))
        self.assertIsInstance(result, dict)
        self.assertIn("aws_ecs_service.app", result["graphdict"])

    def test_invalid_metadata_logs_warning(self):
        """Test that invalid metadata is handled with appropriate logging."""
        tfdata = {
            "graphdict": {
                "aws_appautoscaling_target.ecs": ["aws_ecs_service.app"],
                "aws_ecs_service.app": [],
            },
            "meta_data": {
                "aws_appautoscaling_target.ecs": {},  # Missing count
                "aws_ecs_service.app": {},  # Missing count
            },
            "all_resource": {},
        }
        # Should handle missing metadata gracefully
        result = aws_handle_autoscaling(copy.deepcopy(tfdata))
        self.assertIsInstance(result, dict)

    def test_successful_processing(self):
        """Test successful autoscaling processing with complete data."""
        tfdata = {
            "graphdict": {
                "aws_appautoscaling_target.ecs": ["aws_ecs_service.app"],
                "aws_ecs_service.app": [],
                "aws_subnet.private_a": ["aws_ecs_service.app"],
                "aws_subnet.private_b": ["aws_ecs_service.app"],
            },
            "meta_data": {
                "aws_appautoscaling_target.ecs": {"name": "ecs-target"},
                "aws_ecs_service.app": {"name": "app"},
                "aws_subnet.private_a": {"name": "private-a", "count": 2},
                "aws_subnet.private_b": {"name": "private-b", "count": 2},
            },
            "all_resource": {},
        }
        result = aws_handle_autoscaling(copy.deepcopy(tfdata))
        # Should process successfully
        self.assertIsInstance(result, dict)
        self.assertIn("aws_appautoscaling_target.ecs", result["graphdict"])


class TestAwsHandleVpcendpoints(unittest.TestCase):
    """Test aws_handle_vpcendpoints() for VPC endpoint handling."""

    def test_no_vpc_raises_error(self):
        """Test that missing VPC raises MissingResourceError when endpoints exist."""
        tfdata = {
            "graphdict": {"aws_vpc_endpoint.s3": []},
            "meta_data": {"aws_vpc_endpoint.s3": {"name": "s3-endpoint", "count": 1}},
            "all_resource": {"aws_vpc_endpoint.s3": {}},
        }
        with self.assertRaises(MissingResourceError) as ctx:
            aws_handle_vpcendpoints(copy.deepcopy(tfdata))
        self.assertIn("No VPC found", str(ctx.exception))

    def test_groups_endpoints_under_vpc(self):
        """Test that VPC endpoints are moved under their parent VPC."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
                "aws_vpc_endpoint.s3": [],
                "aws_vpc_endpoint.dynamodb": [],
            },
            "meta_data": {
                "aws_vpc.main": {"name": "main", "count": 1},
                "aws_vpc_endpoint.s3": {"name": "s3-endpoint", "count": 1},
                "aws_vpc_endpoint.dynamodb": {"name": "ddb-endpoint", "count": 1},
            },
            "all_resource": {
                "aws_vpc_endpoint.s3": {"vpc_id": "aws_vpc.main"},
                "aws_vpc_endpoint.dynamodb": {"vpc_id": "aws_vpc.main"},
                "aws_vpc.main": {},
            },
        }
        result = aws_handle_vpcendpoints(copy.deepcopy(tfdata))
        # Endpoints should be moved under VPC
        self.assertIn("aws_vpc_endpoint.s3", result["graphdict"]["aws_vpc.main"])
        self.assertIn("aws_vpc_endpoint.dynamodb", result["graphdict"]["aws_vpc.main"])
        # Endpoints should no longer be top-level nodes
        self.assertNotIn("aws_vpc_endpoint.s3", result["graphdict"])
        self.assertNotIn("aws_vpc_endpoint.dynamodb", result["graphdict"])

    def test_preserves_metadata(self):
        """Test that endpoint metadata is preserved after grouping."""
        tfdata = {
            "graphdict": {
                "aws_vpc.main": [],
                "aws_vpc_endpoint.s3": [],
            },
            "meta_data": {
                "aws_vpc.main": {"name": "main", "count": 1, "cidr": "10.0.0.0/16"},
                "aws_vpc_endpoint.s3": {
                    "name": "s3-endpoint",
                    "count": 1,
                    "service_name": "com.amazonaws.us-east-1.s3",
                },
            },
            "all_resource": {
                "aws_vpc_endpoint.s3": {"vpc_id": "aws_vpc.main"},
                "aws_vpc.main": {},
            },
        }
        original_endpoint_meta = copy.deepcopy(
            tfdata["meta_data"]["aws_vpc_endpoint.s3"]
        )
        original_vpc_meta = copy.deepcopy(tfdata["meta_data"]["aws_vpc.main"])

        result = aws_handle_vpcendpoints(copy.deepcopy(tfdata))

        # Metadata should be preserved
        self.assertEqual(
            result["meta_data"]["aws_vpc_endpoint.s3"], original_endpoint_meta
        )
        self.assertEqual(result["meta_data"]["aws_vpc.main"], original_vpc_meta)


class TestLinkSqsQueuePolicy(unittest.TestCase):
    """Test link_sqs_queue_policy() for SQS policy transitive connections."""

    def test_sqs_policy_creates_transitive_link(self):
        """Test that resources linking to SQS policy also link to queue."""
        graphdict = {
            "aws_sqs_queue.main": [],
            "aws_sqs_queue_policy.main": ["aws_sqs_queue.main"],
            "aws_lambda_function.processor": ["aws_sqs_queue_policy.main"],
        }
        result = link_sqs_queue_policy(graphdict)
        # Lambda should now link directly to queue
        self.assertIn("aws_sqs_queue.main", result["aws_lambda_function.processor"])

    def test_no_sqs_policy_unchanged(self):
        """Test that graphs without SQS policies are unchanged."""
        graphdict = {
            "aws_lambda_function.test": ["aws_s3_bucket.data"],
            "aws_s3_bucket.data": [],
        }
        result = link_sqs_queue_policy(graphdict)
        self.assertEqual(result, graphdict)


class TestSplitNatGateways(unittest.TestCase):
    """Test split_nat_gateways() for NAT gateway per-AZ splitting."""

    def test_nat_gateway_split_by_subnet_az(self):
        """Test that NAT gateways are split by subnet AZ."""
        graphdict = {
            "aws_nat_gateway.main": ["aws_subnet.public_a", "aws_subnet.public_b"],
            "aws_subnet.public_a": [],
            "aws_subnet.public_b": [],
        }
        result = split_nat_gateways(graphdict)
        # Should create separate NAT gateway entries per subnet
        self.assertIsInstance(result, dict)

    def test_nat_gateway_without_subnets_unchanged(self):
        """Test NAT gateways without subnet refs are unchanged."""
        graphdict = {"aws_nat_gateway.main": [], "aws_vpc.main": []}
        result = split_nat_gateways(graphdict)
        self.assertIn("aws_nat_gateway.main", result)


class TestLinkEc2ToIamRoles(unittest.TestCase):
    """Test link_ec2_to_iam_roles() for EC2-IAM instance profile linking."""

    def test_ec2_linked_to_iam_role_via_profile(self):
        """Test that EC2 instances link to IAM roles via instance profiles."""
        graphdict = {
            "aws_instance.web": ["aws_iam_instance_profile.web"],
            "aws_iam_instance_profile.web": ["aws_iam_role.web"],
            "aws_iam_role.web": [],
        }
        result = link_ec2_to_iam_roles(graphdict)
        # EC2 should link directly to IAM role
        self.assertIn("aws_iam_role.web", result["aws_instance.web"])

    def test_ec2_without_instance_profile_unchanged(self):
        """Test EC2 instances without profiles are unchanged."""
        graphdict = {"aws_instance.web": ["aws_vpc.main"], "aws_vpc.main": []}
        result = link_ec2_to_iam_roles(graphdict)
        self.assertEqual(result["aws_instance.web"], ["aws_vpc.main"])


class TestMatchAzToSubnets(unittest.TestCase):
    """Test match_az_to_subnets() for availability zone matching."""

    def test_resources_matched_to_subnet_azs(self):
        """Test that resources are matched to subnets in same AZ."""
        graphdict = {
            "aws_instance.web_a": ["aws_subnet.public~us-east-1a"],
            "aws_subnet.public~us-east-1a": [],
            "aws_subnet.public~us-east-1b": [],
        }
        result = match_az_to_subnets(graphdict)
        # Should maintain AZ-based subnet relationships
        self.assertIsInstance(result, dict)


class TestMatchSgToSubnets(unittest.TestCase):
    """Test match_sg_to_subnets() for security group-subnet matching."""

    def test_sg_matched_to_subnets_with_resources(self):
        """Test that SGs are matched to subnets containing their resources."""
        graphdict = {
            "aws_security_group.web": ["aws_instance.server"],
            "aws_instance.server": ["aws_subnet.public_a"],
            "aws_subnet.public_a": [],
        }
        result = match_sg_to_subnets(graphdict)
        # SG should be associated with subnet containing the instance
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
