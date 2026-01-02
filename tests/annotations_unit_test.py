import unittest, sys, os
from unittest.mock import patch, MagicMock

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.annotations import add_annotations, modify_nodes, modify_metadata


class TestAddAnnotations(unittest.TestCase):
    def test_add_annotations_basic(self):
        tfdata = {
            "graphdict": {"aws_lambda_function.test": []},
            "meta_data": {"aws_lambda_function.test": {}},
            "provider_detection": {"primary_provider": "aws"},
        }
        result = add_annotations(tfdata)
        self.assertIn("graphdict", result)
        self.assertIn("meta_data", result)

    def test_add_annotations_with_user_annotations(self):
        tfdata = {
            "graphdict": {"node1": []},
            "meta_data": {"node1": {}},
            "annotations": {"add": {"node2": {}}},
            "provider_detection": {"primary_provider": "aws"},
        }
        result = add_annotations(tfdata)
        self.assertIn("node2", result["graphdict"])

    def test_add_annotations_auto_link(self):
        tfdata = {
            "graphdict": {"aws_lambda_function.test": []},
            "meta_data": {"aws_lambda_function.test": {}},
            "provider_detection": {"primary_provider": "aws"},
        }
        result = add_annotations(tfdata)
        self.assertIsInstance(result["graphdict"], dict)


class TestModifyNodes(unittest.TestCase):
    @patch("modules.annotations.click.echo")
    def test_modify_nodes_add(self, mock_echo):
        graphdict = {"node1": []}
        annotate = {"add": {"node2": {}}}
        result = modify_nodes(graphdict, annotate)
        self.assertIn("node2", result)
        self.assertEqual(result["node2"], [])

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_connect(self, mock_echo):
        graphdict = {"node1": [], "node2": []}
        annotate = {"connect": {"node1": ["node2"]}}
        result = modify_nodes(graphdict, annotate)
        self.assertIn("node2", result["node1"])

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_connect_with_label(self, mock_echo):
        graphdict = {"node1": [], "node2": []}
        annotate = {"connect": {"node1": [{"node2": "label"}]}}
        result = modify_nodes(graphdict, annotate)
        self.assertIn("node2", result["node1"])

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_connect_wildcard(self, mock_echo):
        graphdict = {"aws_lambda.func1": [], "aws_lambda.func2": [], "node2": []}
        annotate = {"connect": {"aws_lambda*": ["node2"]}}
        result = modify_nodes(graphdict, annotate)
        self.assertIn("node2", result["aws_lambda.func1"])
        self.assertIn("node2", result["aws_lambda.func2"])

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_disconnect(self, mock_echo):
        graphdict = {"node1": ["node2"], "node2": []}
        annotate = {"disconnect": {"node1": ["node2"]}}
        with self.assertRaises(AttributeError):
            modify_nodes(graphdict, annotate)

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_disconnect_wildcard(self, mock_echo):
        graphdict = {"aws_lambda.func1": ["node2"], "aws_lambda.func2": ["node2"]}
        annotate = {"disconnect": {"aws_lambda*": ["node2"]}}
        result = modify_nodes(graphdict, annotate)
        self.assertNotIn("node2", result["aws_lambda.func1"])
        self.assertNotIn("node2", result["aws_lambda.func2"])

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_remove(self, mock_echo):
        graphdict = {"node1": [], "node2": []}
        annotate = {"remove": ["node1"]}
        result = modify_nodes(graphdict, annotate)
        self.assertNotIn("node1", result)

    @patch("modules.annotations.click.echo")
    def test_modify_nodes_empty_annotate(self, mock_echo):
        graphdict = {"node1": []}
        annotate = {}
        result = modify_nodes(graphdict, annotate)
        self.assertEqual(result, graphdict)


class TestModifyMetadata(unittest.TestCase):
    def test_modify_metadata_connect(self):
        annotations = {"connect": {"node1": [{"node2": "label"}]}}
        graphdict = {"node1": ["node2"]}
        metadata = {"node1": {}}
        result = modify_metadata(annotations, graphdict, metadata)
        self.assertIn("edge_labels", result["node1"])

    def test_modify_metadata_connect_wildcard(self):
        annotations = {"connect": {"aws_lambda*": [{"node2": "label"}]}}
        graphdict = {"aws_lambda.func1": ["node2"]}
        metadata = {"aws_lambda.func1": {}}
        result = modify_metadata(annotations, graphdict, metadata)
        self.assertIsInstance(result, dict)

    def test_modify_metadata_add(self):
        annotations = {"add": {"node2": {"attr1": "value1"}}}
        graphdict = {"node1": []}
        metadata = {"node1": {}}
        result = modify_metadata(annotations, graphdict, metadata)
        self.assertIn("node2", result)
        self.assertEqual(result["node2"]["attr1"], "value1")

    def test_modify_metadata_update(self):
        annotations = {"update": {"node1": {"attr1": "new_value"}}}
        graphdict = {"node1": []}
        metadata = {"node1": {"attr1": "old_value"}}
        result = modify_metadata(annotations, graphdict, metadata)
        self.assertEqual(result["node1"]["attr1"], "new_value")

    def test_modify_metadata_update_wildcard(self):
        annotations = {"update": {"aws_lambda*": {"attr1": "new_value"}}}
        graphdict = {"aws_lambda.func1": [], "aws_lambda.func2": []}
        metadata = {"aws_lambda.func1": {}, "aws_lambda.func2": {}}
        result = modify_metadata(annotations, graphdict, metadata)
        self.assertEqual(result["aws_lambda.func1"]["attr1"], "new_value")
        self.assertEqual(result["aws_lambda.func2"]["attr1"], "new_value")

    def test_modify_metadata_empty_annotations(self):
        annotations = {}
        graphdict = {"node1": []}
        metadata = {"node1": {}}
        result = modify_metadata(annotations, graphdict, metadata)
        self.assertEqual(result, metadata)


if __name__ == "__main__":
    unittest.main()
