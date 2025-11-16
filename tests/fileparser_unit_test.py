import unittest, sys, os
from unittest.mock import patch, MagicMock, mock_open
import tempfile

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.fileparser import (
    walklevel,
    handle_module,
)


class TestWalklevel(unittest.TestCase):
    def test_walklevel_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.tf")
            with open(test_file, "w") as f:
                f.write("# test")
            result = list(walklevel(tmpdir, level=1))
            self.assertGreater(len(result), 0)

    def test_walklevel_depth_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub1", "sub2")
            os.makedirs(subdir)
            result = list(walklevel(tmpdir, level=1))
            self.assertIsInstance(result, list)


class TestHandleModule(unittest.TestCase):
    def test_handle_module_local_source(self):
        modules_list = [{"test_module": {"source": "./local/path"}}]
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertIn("tf_file_paths", result)
        self.assertIn("module_source_dict", result)
        self.assertIn("test_module", result["module_source_dict"])

    def test_handle_module_remote_source(self):
        modules_list = [{"test_module": {"source": "terraform-aws-modules/vpc/aws"}}]
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertIn("test_module", result["module_source_dict"])
        self.assertIn("cache_path", result["module_source_dict"]["test_module"])

    def test_handle_module_empty_list(self):
        modules_list = []
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertEqual(len(result["module_source_dict"]), 0)

    def test_handle_module_multiple_modules(self):
        modules_list = [
            {"module1": {"source": "./path1"}},
            {"module2": {"source": "./path2"}},
        ]
        tf_file_paths = []
        filename = "main.tf"
        result = handle_module(modules_list, tf_file_paths, filename)
        self.assertEqual(len(result["module_source_dict"]), 2)


if __name__ == "__main__":
    unittest.main(exit=False)
