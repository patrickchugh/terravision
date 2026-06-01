import unittest, sys, os
from unittest import mock

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

from modules.helpers import *
import modules.helpers as helpers


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


class TestTfBinaryResolver(unittest.TestCase):
    """Resolution of the Terraform-compatible binary (terraform / tofu).

    Given a Terravision invocation with an --engine value,
    when the binary is resolved,
    then the correct executable name is stored and returned.
    """

    def setUp(self):
        # Each scenario starts with no previously resolved binary.
        helpers._TF_BINARY = None

    def tearDown(self):
        helpers._TF_BINARY = None

    def test_should_return_tofu_when_engine_is_tofu(self):
        # given an explicit tofu engine / when resolved / then tofu is used
        result = set_tf_binary("tofu")
        self.assertEqual(result, "tofu")
        self.assertEqual(get_tf_binary(), "tofu")

    def test_should_return_terraform_when_engine_is_terraform(self):
        # given an explicit terraform engine / when resolved / then terraform is used
        result = set_tf_binary("terraform")
        self.assertEqual(result, "terraform")
        self.assertEqual(get_tf_binary(), "terraform")

    def test_should_be_case_insensitive_for_explicit_engine(self):
        # given an uppercase engine name / when resolved / then it is normalised
        self.assertEqual(set_tf_binary("TOFU"), "tofu")

    def test_should_prefer_terraform_when_auto_and_both_present(self):
        # given both binaries on PATH / when auto / then terraform wins
        with mock.patch.object(helpers.shutil, "which", return_value="/usr/bin/x"):
            self.assertEqual(set_tf_binary("auto"), "terraform")

    def test_should_fall_back_to_tofu_when_auto_and_terraform_absent(self):
        # given only tofu on PATH / when auto / then tofu is used
        def which(exe):
            return "/usr/bin/tofu" if exe == "tofu" else None

        with mock.patch.object(helpers.shutil, "which", side_effect=which):
            self.assertEqual(set_tf_binary("auto"), "tofu")

    def test_should_default_to_terraform_when_auto_and_neither_present(self):
        # given neither binary on PATH / when auto / then terraform is reported
        with mock.patch.object(helpers.shutil, "which", return_value=None):
            self.assertEqual(set_tf_binary("auto"), "terraform")

    def test_should_autodetect_when_get_called_before_set(self):
        # given an unset binary / when get is called / then it autodetects via auto
        with mock.patch.object(
            helpers.shutil, "which", return_value="/usr/bin/terraform"
        ):
            self.assertEqual(get_tf_binary(), "terraform")


if __name__ == "__main__":
    unittest.main()
