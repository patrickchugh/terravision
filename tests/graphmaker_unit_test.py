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
)


class TestReverseRelations(unittest.TestCase):
    def test_reverse_relations_basic(self):
        tfdata = {"graphdict": {"node1": ["node2"], "node2": []}}
        result = reverse_relations(tfdata)
        self.assertIsInstance(result["graphdict"], dict)


class TestCheckRelationship(unittest.TestCase):
    def test_check_relationship_no_match(self):
        tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "hidden": [],
        }
        result = check_relationship("node1", ["value"], tfdata)
        self.assertEqual(result, [])

    def test_check_relationship_with_match(self):
        tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "hidden": [],
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
        }
        result = cleanup_originals(["resource1"], tfdata)
        self.assertNotIn("resource1", result["graphdict"])

    def test_cleanup_originals_empty_list(self):
        tfdata = {"graphdict": {"resource1": []}, "meta_data": {"resource1": {}}}
        result = cleanup_originals([], tfdata)
        self.assertIn("resource1", result["graphdict"])


if __name__ == "__main__":
    unittest.main(exit=False)
