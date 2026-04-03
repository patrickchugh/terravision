import unittest, sys, os
from unittest.mock import patch, MagicMock

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.graphmaker import (
    reverse_relations,
    check_relationship,
    add_relations,
    consolidate_nodes,
    dict_generator,
    cleanup_originals,
    add_number_suffix,
    extend_sg_groups,
)


class TestReverseRelations(unittest.TestCase):
    def test_reverse_relations_basic(self):
        tfdata = {
            "graphdict": {"node1": ["node2"], "node2": []},
            "provider_detection": {"primary_provider": "aws"},
        }
        result = reverse_relations(tfdata)
        self.assertIsInstance(result["graphdict"], dict)


class TestCheckRelationship(unittest.TestCase):
    def test_check_relationship_no_match(self):
        tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "hidden": [],
            "provider_detection": {"primary_provider": "aws"},
        }
        result = check_relationship("node1", ["value"], tfdata)
        self.assertEqual(result, [])

    def test_check_relationship_with_match(self):
        tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "hidden": [],
            "provider_detection": {"primary_provider": "aws"},
        }
        result = check_relationship("node1", ["node2"], tfdata)
        self.assertIsInstance(result, list)


class TestAddRelations(unittest.TestCase):
    @patch("modules.graphmaker.click.echo")
    def test_add_relation_baseline(self, mock_echo):
        tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "meta_data": {"node1": {"param1": "node2"}},
            "original_metadata": {
                "node1": {"param1": "value1"},
                "node2": {"param2": "value2"},
            },
            "hidden": [],
            "provider_detection": {"primary_provider": "aws"},
        }
        result = add_relations(tfdata)
        self.assertIn("graphdict", result)
        self.assertIn("original_graphdict_with_relations", result)

    @patch("modules.graphmaker.click.echo")
    def test_add_relation_nomatches(self, mock_echo):
        tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "meta_data": {"node1": {"param1": "node3"}},
            "original_metadata": {
                "node1": {"param1": "value1"},
                "node2": {"param2": "value2"},
            },
            "hidden": [],
            "provider_detection": {"primary_provider": "aws"},
        }
        result = add_relations(tfdata)
        self.assertEqual(len(result["graphdict"]["node1"]), 0)


class TestConsolidateNodes(unittest.TestCase):
    def test_consolidate_nodes_removes_null_resource(self):
        tfdata = {
            "graphdict": {"null_resource.test": [], "node1": []},
            "meta_data": {"null_resource.test": {}, "node1": {}},
        }
        result = consolidate_nodes(tfdata)
        self.assertNotIn("null_resource.test", result["graphdict"])

    def test_consolidate_nodes_basic(self):
        tfdata = {"graphdict": {"node1": []}, "meta_data": {"node1": {}}}
        result = consolidate_nodes(tfdata)
        self.assertIn("node1", result["graphdict"])


class TestDictGenerator(unittest.TestCase):
    def test_dict_generator_simple(self):
        data = {"key1": "value1"}
        result = list(dict_generator(data))
        self.assertGreater(len(result), 0)

    def test_dict_generator_nested(self):
        data = {"key1": {"key2": "value2"}}
        result = list(dict_generator(data))
        self.assertGreater(len(result), 0)

    def test_dict_generator_with_list(self):
        data = {"key1": ["value1", "value2"]}
        result = list(dict_generator(data))
        self.assertGreater(len(result), 0)

    def test_dict_generator_empty(self):
        data = {}
        result = list(dict_generator(data))
        self.assertEqual(len(result), 0)


class TestCleanupOriginals(unittest.TestCase):
    def test_cleanup_originals_basic(self):
        tfdata = {
            "graphdict": {"resource1": [], "resource2": []},
            "meta_data": {"resource1": {}, "resource2": {}},
            "provider_detection": {"primary_provider": "aws"},
        }
        result = cleanup_originals(["resource1"], tfdata)
        self.assertNotIn("resource1", result["graphdict"])

    def test_cleanup_originals_empty_list(self):
        tfdata = {
            "graphdict": {"resource1": []},
            "meta_data": {"resource1": {}},
            "provider_detection": {"primary_provider": "aws"},
        }
        result = cleanup_originals([], tfdata)
        self.assertIn("resource1", result["graphdict"])


class TestAddNumberSuffix(unittest.TestCase):
    """Tests for add_number_suffix - issue #184 ValueError fix."""

    def test_no_crash_when_resource_removed_twice(self):
        """A resource matching multiple numbered variants should not crash.

        When a connection matches two or more numbered variants (e.g. res~1 and
        res~2), the original unnumbered connection should only be removed once
        from new_list, not once per match.
        """
        tfdata = {
            "graphdict": {
                "aws_security_group.sg": [
                    "aws_instance.web",
                ],
                "aws_instance.web~1": [],
                "aws_instance.web~2": [],
                "aws_instance.web": [],
            },
            "meta_data": {
                "aws_security_group.sg": {"count": 2},
                "aws_instance.web": {"count": 2},
                "aws_instance.web~1": {"count": 2},
                "aws_instance.web~2": {"count": 2},
            },
            "provider_detection": {"primary_provider": "aws"},
        }
        # Should not raise ValueError: list.remove(x): x not in list
        result = add_number_suffix(1, "aws_security_group.sg", tfdata)
        self.assertIsInstance(result, list)


class TestExtendSgGroups(unittest.TestCase):
    """Tests for extend_sg_groups - issue #184 shared SG across subnets."""

    def _make_tfdata(self, graphdict, meta_data=None):
        if meta_data is None:
            meta_data = {k: {"module": "main"} for k in graphdict}
        return {
            "graphdict": graphdict,
            "meta_data": meta_data,
            "provider_detection": {"primary_provider": "aws"},
        }

    def test_subnet_refs_updated_when_sg_expanded(self):
        """When an SG is expanded into numbered variants, subnets referencing
        the original SG must be updated to reference the numbered variants.
        """
        tfdata = self._make_tfdata(
            {
                "aws_subnet.private_a": ["aws_security_group.ecs_sg"],
                "aws_subnet.private_b": ["aws_security_group.ecs_sg"],
                "aws_security_group.ecs_sg": ["aws_fargate.ecs~1"],
                "aws_fargate.ecs~1": [],
            }
        )
        result = extend_sg_groups(tfdata)
        gd = result["graphdict"]

        # Original SG should be deleted
        self.assertNotIn("aws_security_group.ecs_sg", gd)

        # Numbered variant should exist
        self.assertIn("aws_security_group.ecs_sg~1", gd)

        # First subnet gets the SG variant (only ~1 exists)
        self.assertNotIn("aws_security_group.ecs_sg", gd["aws_subnet.private_a"])
        self.assertIn("aws_security_group.ecs_sg~1", gd["aws_subnet.private_a"])

        # Second subnet should NOT get an SG — there is no ~2 instance,
        # so no resource is actually deployed there
        self.assertNotIn("aws_security_group.ecs_sg", gd["aws_subnet.private_b"])
        sg_refs_b = [c for c in gd["aws_subnet.private_b"] if "ecs_sg~" in c]
        self.assertEqual(len(sg_refs_b), 0, "Subnet B should have no SG variant")

    def test_multiple_instances_across_subnets(self):
        """When an SG has variants matching each subnet, each subnet gets one."""
        tfdata = self._make_tfdata(
            {
                "aws_subnet.a": ["aws_security_group.web_sg"],
                "aws_subnet.b": ["aws_security_group.web_sg"],
                "aws_security_group.web_sg": [
                    "aws_instance.web~1",
                    "aws_instance.web~2",
                ],
                "aws_instance.web~1": [],
                "aws_instance.web~2": [],
            }
        )
        result = extend_sg_groups(tfdata)
        gd = result["graphdict"]

        sg_in_a = [c for c in gd["aws_subnet.a"] if "web_sg~" in c]
        sg_in_b = [c for c in gd["aws_subnet.b"] if "web_sg~" in c]

        # Both subnets should have SG refs
        self.assertTrue(len(sg_in_a) > 0)
        self.assertTrue(len(sg_in_b) > 0)

        # They should NOT share the same SG variant
        self.assertNotEqual(
            sg_in_a,
            sg_in_b,
            "Subnets share the same SG variant - graphviz can't render this",
        )

    def test_shared_sg_no_numbered_children_gets_expanded(self):
        """An SG with no numbered children but shared across subnets must
        still be expanded into per-subnet copies.
        """
        tfdata = self._make_tfdata(
            {
                "aws_subnet.a": ["aws_security_group.efs"],
                "aws_subnet.b": ["aws_security_group.efs"],
                "aws_security_group.efs": [
                    "aws_efs_mount_target.mt",
                    "aws_security_group_rule.efs_rule",
                ],
                "aws_efs_mount_target.mt": [],
                "aws_security_group_rule.efs_rule": [],
            }
        )
        result = extend_sg_groups(tfdata)
        gd = result["graphdict"]

        # Original SG should be deleted
        self.assertNotIn("aws_security_group.efs", gd)

        # Per-subnet variants should exist
        self.assertIn("aws_security_group.efs~1", gd)
        self.assertIn("aws_security_group.efs~2", gd)

        # Each subnet gets its own variant
        self.assertIn("aws_security_group.efs~1", gd["aws_subnet.a"])
        self.assertIn("aws_security_group.efs~2", gd["aws_subnet.b"])
        self.assertNotIn("aws_security_group.efs~2", gd["aws_subnet.a"])
        self.assertNotIn("aws_security_group.efs~1", gd["aws_subnet.b"])

    def test_single_subnet_sg_not_expanded(self):
        """An SG referenced by only one subnet should not be expanded."""
        tfdata = self._make_tfdata(
            {
                "aws_subnet.a": ["aws_security_group.admin_sg"],
                "aws_security_group.admin_sg": ["aws_instance.bastion"],
                "aws_instance.bastion": [],
            }
        )
        result = extend_sg_groups(tfdata)
        gd = result["graphdict"]

        # SG should remain unchanged (not expanded)
        self.assertIn("aws_security_group.admin_sg", gd)
        self.assertIn("aws_security_group.admin_sg", gd["aws_subnet.a"])


if __name__ == "__main__":
    unittest.main(exit=False)
