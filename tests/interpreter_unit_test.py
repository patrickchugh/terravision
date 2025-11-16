import unittest, sys, os
from unittest.mock import patch, MagicMock

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.interpreter import (
    extract_locals,
    find_replace_values,
    replace_data_values,
    replace_local_values,
    handle_implied_resources,
    handle_numbered_nodes,
    find_actual_resource,
)


class TestExtractLocals(unittest.TestCase):
    def test_extract_locals_empty(self):
        tfdata = {}
        result = extract_locals(tfdata)
        self.assertEqual(result["all_locals"], {})

    def test_extract_locals_main_module(self):
        tfdata = {"all_locals": {"file.tf": [{"var1": "value1"}]}}
        result = extract_locals(tfdata)
        self.assertIn("main", result["all_locals"])
        self.assertEqual(result["all_locals"]["main"]["var1"], "value1")

    def test_extract_locals_with_module(self):
        tfdata = {"all_locals": {"file.tf;mymodule;": [{"var1": "value1"}]}}
        result = extract_locals(tfdata)
        self.assertIn("mymodule", result["all_locals"])


class TestFindReplaceValues(unittest.TestCase):
    def test_find_replace_values_no_vars(self):
        tfdata = {"variable_map": {"main": {}}, "all_locals": {}}
        result = find_replace_values("simple_string", "main", tfdata)
        self.assertEqual(result, "simple_string")

    def test_find_replace_values_with_var(self):
        tfdata = {
            "variable_map": {"main": {"test": "value"}},
            "all_locals": {},
        }
        result = find_replace_values("var.test", "main", tfdata)
        self.assertIsInstance(result, str)


class TestReplaceDataValues(unittest.TestCase):
    def test_replace_data_values_empty(self):
        tfdata = {}
        result = replace_data_values([], "test_value", tfdata)
        self.assertEqual(result, "test_value")

    def test_replace_data_values_with_match(self):
        tfdata = {}
        result = replace_data_values(
            ["data.aws_availability_zones_names"], "${data.aws_availability_zones_names}", tfdata
        )
        self.assertIsInstance(result, (str, list))


class TestReplaceLocalValues(unittest.TestCase):
    @patch("modules.interpreter.click.echo")
    def test_replace_local_values_found(self, mock_echo):
        tfdata = {"all_locals": {"main": {"test": "value"}}}
        result = replace_local_values(["local.test"], "local.test", "main", tfdata)
        self.assertIn("value", result)

    @patch("modules.interpreter.click.echo")
    def test_replace_local_values_not_found(self, mock_echo):
        tfdata = {"all_locals": {"main": {}}}
        result = replace_local_values(["local.missing"], "local.missing", "main", tfdata)
        self.assertIsInstance(result, str)


class TestHandleImpliedResources(unittest.TestCase):
    def test_handle_implied_resources_iam_policy(self):
        item = {"aws_iam_policy": {"test": {"policy": ["logs:CreateLogGroup"]}}}
        tfdata = {"node_list": [], "graphdict": {}}
        meta_data = {}
        result_meta, result_tfdata = handle_implied_resources(
            item, "aws_iam_policy", "test", tfdata, meta_data
        )
        self.assertIn("aws_cloudwatch_log_group.logs", result_tfdata["node_list"])

    def test_handle_implied_resources_other_type(self):
        item = {"aws_s3_bucket": {"test": {}}}
        tfdata = {"node_list": [], "graphdict": {}}
        meta_data = {}
        result_meta, result_tfdata = handle_implied_resources(
            item, "aws_s3_bucket", "test", tfdata, meta_data
        )
        self.assertEqual(len(result_tfdata["node_list"]), 0)


class TestHandleNumberedNodes(unittest.TestCase):
    def test_handle_numbered_nodes_basic(self):
        tfdata = {"node_list": ["resource[0]", "resource[1]"]}
        meta_data = {"resource[0]": {"attr": "value"}}
        result = handle_numbered_nodes("resource[0]", tfdata, meta_data)
        self.assertIn("resource[0]", result)
        self.assertIn("resource[1]", result)

    def test_handle_numbered_nodes_single(self):
        tfdata = {"node_list": ["resource[0]"]}
        meta_data = {"resource[0]": {"attr": "value"}}
        result = handle_numbered_nodes("resource[0]", tfdata, meta_data)
        self.assertEqual(result["resource[0]"]["count"], 1)


class TestFindActualResource(unittest.TestCase):
    def test_find_actual_resource_exact_match(self):
        node_list = ["aws_s3_bucket.test"]
        result = find_actual_resource(
            node_list, "aws_s3_bucket.test", "aws_s3_bucket", "main", {"original_metadata": {}}
        )
        self.assertEqual(result, "aws_s3_bucket.test")

    def test_find_actual_resource_with_bracket(self):
        node_list = ["aws_s3_bucket.test[0]", "aws_s3_bucket.test[1]"]
        result = find_actual_resource(
            node_list, "aws_s3_bucket.test", "aws_s3_bucket", "main", {"original_metadata": {}}
        )
        self.assertEqual(result, "aws_s3_bucket.test[0]")

    def test_find_actual_resource_not_found(self):
        node_list = ["aws_s3_bucket.other"]
        result = find_actual_resource(
            node_list, "aws_s3_bucket.test", "aws_s3_bucket", "main", {"original_metadata": {}}
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(exit=False)
