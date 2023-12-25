import unittest, sys, os

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

from modules.helpers import *
from modules.graphmaker import add_relations


class TestAddRelations(unittest.TestCase):
    def setUp(self):
        self.tfdata = {
            "node_list": ["node1", "node2"],
            "graphdict": {"node1": [], "node2": []},
            "meta_data": {"node1": {"param1": "node2"}},
            "original_metadata": {
                "node1": {"param1": "value1"},
                "node2": {"param2": "value2"},
            },
            "hidden": [],
        }

    def test_add_relation_baseline(self):
        self.tfdata = add_relations(self.tfdata)
        self.assertEqual(len(self.tfdata["graphdict"]["node1"]), 1)
        self.assertIn("node2", self.tfdata["graphdict"]["node1"])

    def test_add_relation_nomatches(self):
        self.tfdata["meta_data"]["node1"]["param1"] = "node3"
        self.tfdata = add_relations(self.tfdata)
        self.assertEqual(len(self.tfdata["graphdict"]["node1"]), 0)

if __name__ == "__main__":
    unittest.main()
