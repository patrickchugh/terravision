"""Unit tests for modules/html_renderer.py."""

import json
import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.html_renderer import (
    _clean_metadata_dict,
    _clean_string_value,
    _deep_normalize,
    _embed_icons_as_base64,
    _get_instance_info,
    _normalize_value,
    _serialize_metadata,
    _try_decode_base64,
)


class TestCleanMetadataDict(unittest.TestCase):
    def test_strips_node_key(self):
        attrs = {"name": "test", "node": "<some object>"}
        result = _clean_metadata_dict(attrs)
        self.assertNotIn("node", result)
        self.assertEqual(result["name"], "test")

    def test_strips_internal_markers(self):
        attrs = {"name": "test", "_internal": "x", "_synthetic": True}
        result = _clean_metadata_dict(attrs)
        self.assertNotIn("_internal", result)
        # _synthetic and _data_source are preserved
        self.assertIn("_synthetic", result)

    def test_known_after_apply_replacement(self):
        attrs = {"arn": True, "id": True, "name": "real-name"}
        result = _clean_metadata_dict(attrs)
        self.assertEqual(result["arn"], "Computed (known after apply)")
        self.assertEqual(result["id"], "Computed (known after apply)")
        self.assertEqual(result["name"], "real-name")

    def test_real_boolean_attrs_preserved(self):
        # These attribute names should keep their boolean True value
        attrs = {
            "force_destroy": True,
            "enable_dns_support": True,
            "associate_public_ip_address": True,
        }
        result = _clean_metadata_dict(attrs)
        self.assertEqual(result["force_destroy"], True)
        self.assertEqual(result["enable_dns_support"], True)
        self.assertEqual(result["associate_public_ip_address"], True)


class TestCleanStringValue(unittest.TestCase):
    def test_strips_surrounding_quotes(self):
        self.assertEqual(_clean_string_value('"hello"'), "hello")
        self.assertEqual(_clean_string_value('"ami-12345" '), "ami-12345")

    def test_strips_terraform_expression_wrapper(self):
        self.assertEqual(
            _clean_string_value("${aws_ecs_cluster.this.id}"),
            "aws_ecs_cluster.this.id",
        )

    def test_replaces_unknown_marker_in_expression(self):
        # UNKNOWN markers appear inside larger expressions
        self.assertEqual(
            _clean_string_value('elastic-ip-nat-gw-"UNKNOWN"'),
            "elastic-ip-nat-gw-<unknown>",
        )

    def test_preserves_normal_strings(self):
        self.assertEqual(_clean_string_value("us-east-1"), "us-east-1")
        self.assertEqual(_clean_string_value("t2.micro"), "t2.micro")

    def test_strips_whitespace(self):
        self.assertEqual(_clean_string_value("  hello  "), "hello")


class TestNormalizeValue(unittest.TestCase):
    def test_parses_python_list_repr(self):
        value = "[{'type': 'forward', 'arn': 'test'}]"
        result = _normalize_value("action", value)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "forward")

    def test_parses_python_dict_repr(self):
        value = "{'key': 'value', 'count': 3}"
        result = _normalize_value("config", value)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["count"], 3)

    def test_passes_through_real_lists(self):
        value = ["a", "b", "c"]
        result = _normalize_value("items", value)
        self.assertEqual(result, ["a", "b", "c"])

    def test_passes_through_numbers(self):
        self.assertEqual(_normalize_value("count", 5), 5)
        self.assertEqual(_normalize_value("ratio", 1.5), 1.5)


class TestTryDecodeBase64(unittest.TestCase):
    def test_decodes_plain_base64(self):
        # "Hello, World!" base64-encoded
        encoded = "SGVsbG8sIFdvcmxkIQ=="
        result = _try_decode_base64(encoded)
        self.assertEqual(result, "Hello, World!")

    def test_decodes_gzip_base64(self):
        import base64
        import gzip

        original = "#!/bin/bash\necho hello\n"
        compressed = gzip.compress(original.encode())
        encoded = base64.b64encode(compressed).decode()
        result = _try_decode_base64(encoded)
        self.assertEqual(result, original)

    def test_returns_none_for_binary(self):
        # Random binary data base64-encoded
        encoded = "AAECAwQFBgcICQoLDA0ODw=="  # 0-15 bytes
        result = _try_decode_base64(encoded)
        self.assertIsNone(result)

    def test_handles_missing_padding(self):
        # Valid base64 without padding
        result = _try_decode_base64("SGVsbG8")  # "Hello"
        self.assertEqual(result, "Hello")


class TestGetInstanceInfo(unittest.TestCase):
    def test_returns_none_for_non_numbered(self):
        tfdata = {"meta_data": {"aws_instance.web": {}}}
        self.assertIsNone(_get_instance_info("aws_instance.web", tfdata))

    def test_extracts_instance_number_and_total(self):
        tfdata = {
            "meta_data": {
                "aws_instance.web~1": {},
                "aws_instance.web~2": {},
                "aws_instance.web~3": {},
            }
        }
        info = _get_instance_info("aws_instance.web~2", tfdata)
        self.assertEqual(info["instance_number"], 2)
        self.assertEqual(info["total_instances"], 3)

    def test_handles_index_in_base_name(self):
        # aws_efs_mount_target.this[0]~1 etc.
        tfdata = {
            "meta_data": {
                "aws_efs.this[0]~1": {},
                "aws_efs.this[1]~2": {},
                "aws_efs.this[2]~3": {},
            }
        }
        info = _get_instance_info("aws_efs.this[1]~2", tfdata)
        self.assertEqual(info["instance_number"], 2)
        self.assertEqual(info["total_instances"], 3)


class TestEmbedIconsAsBase64(unittest.TestCase):
    def test_replaces_existing_icon_path(self):
        # Use a real icon file from resource_images
        from pathlib import Path

        icon_path = Path(parent_dir) / "resource_images" / "generic" / "generic.png"
        if not icon_path.exists():
            self.skipTest("Generic icon not available")

        dot = f'node1 [image="{icon_path}"]'
        result_dot, failed = _embed_icons_as_base64(dot, {str(icon_path)})
        self.assertEqual(failed, {})
        self.assertIn("data:image/png;base64,", result_dot)
        self.assertNotIn(str(icon_path), result_dot)

    def test_handles_missing_file(self):
        dot = 'node1 [image="/nonexistent/icon.png"]'
        result_dot, failed = _embed_icons_as_base64(dot, {"/nonexistent/icon.png"})
        self.assertIn("/nonexistent/icon.png", failed)


class TestSerializeMetadata(unittest.TestCase):
    def test_includes_all_required_fields(self):
        tfdata = {
            "meta_data": {"aws_s3_bucket.test": {"bucket": "my-bucket"}},
            "original_metadata": {"aws_s3_bucket.test": {"bucket": "my-bucket"}},
            "graphdict": {"aws_s3_bucket.test": []},
        }
        result = _serialize_metadata(tfdata)
        self.assertIn("metadata", result)
        self.assertIn("original_metadata", result)
        self.assertIn("graphdict", result)
        self.assertIn("resource_siblings", result)
        self.assertIn("original_name_map", result)

    def test_uses_pre_draw_metadata_when_available(self):
        tfdata = {
            "pre_draw_metadata": {"aws_instance.web": {"instance_type": "t2.micro"}},
            "meta_data": {"aws_instance.web": {"node": "<placeholder>"}},
            "original_metadata": {},
            "graphdict": {},
        }
        result = _serialize_metadata(tfdata)
        self.assertEqual(
            result["metadata"]["aws_instance.web"]["instance_type"], "t2.micro"
        )

    def test_serializable_to_json(self):
        tfdata = {
            "meta_data": {"aws_s3_bucket.test": {"bucket": "x", "tags": {}}},
            "original_metadata": {"aws_s3_bucket.test": {"bucket": "x"}},
            "graphdict": {"aws_s3_bucket.test": []},
        }
        result = _serialize_metadata(tfdata)
        # Should not raise
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
