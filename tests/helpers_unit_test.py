import unittest, sys, os

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

from modules.helpers import *


class TestCheckForDomain(unittest.TestCase):
    def test_valid_domain(self):
        string = "www.example.com"
        result = check_for_domain(string)
        self.assertTrue(result)

    def test_no_domain(self):
        string = "example"
        result = check_for_domain(string)
        self.assertFalse(result)

    def test_tld_only(self):
        string = ".com"
        result = check_for_domain(string)
        self.assertFalse(result)

    def test_subdomain(self):
        string = "www.example"
        result = check_for_domain(string)
        self.assertFalse(result)


class TestGetvar(unittest.TestCase):
    def test_getvar_from_env(self):
        os.environ["TF_VAR_environ"] = "value_from_env"
        result = getvar("environ", {})
        self.assertEqual(result, "value_from_env")

    def test_getvar_from_dict(self):
        variables = {"test": "value_from_dict"}
        result = getvar("test", variables)
        self.assertEqual(result, "value_from_dict")

    def test_getvar_ignore_case(self):
        variables = {"Test": "value_ignore_case"}
        result = getvar("test", variables)
        self.assertEqual(result, "value_ignore_case")

    def test_getvar_not_found(self):
        result = getvar("not_found", {})
        self.assertEqual(result, "NOTFOUND")


if __name__ == "__main__":
    unittest.main()
