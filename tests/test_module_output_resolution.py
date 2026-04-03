"""Test module output resolution for local modules.

Reproduces the issue where cross-module references like module.keyvault.name
fail to resolve when modules use local paths (./modules/keyvault) because
the all_output keys don't contain the ;module_name; pattern expected by
replace_module_vars.
"""

import unittest
from unittest.mock import patch

import sys, os

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from modules.interpreter import replace_module_vars, find_replace_values


class TestModuleOutputResolutionLocalPaths(unittest.TestCase):
    """Test that module output references resolve when all_output keys use
    local filesystem paths (no ;module_name; in path)."""

    def _make_tfdata_with_local_module_outputs(self):
        """Create tfdata simulating local modules like ./modules/keyvault.

        The key issue: when modules are local (source = "./modules/keyvault"),
        all_output keys are absolute paths like:
            /home/user/infra/modules/keyvault/outputs.tf

        But replace_module_vars previously expected keys containing ;keyvault; like:
            /home/user/.terravision/module_cache/repo;keyvault;/outputs.tf
        """
        return {
            "all_output": {
                # Local module paths - no ;module_name; in path
                "/home/user/infra/modules/keyvault/outputs.tf": [
                    {
                        "name": {
                            "description": "The name of the keyvault",
                            "value": "kv-myapp-prod",
                        }
                    },
                    {
                        "id": {
                            "description": "The ID of the keyvault",
                            "value": "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv-myapp-prod",
                        }
                    },
                ],
                "/home/user/infra/modules/resource_group/outputs.tf": [
                    {
                        "name": {
                            "description": "The name of the resource group",
                            "value": "rg-myapp-prod",
                        }
                    },
                    {
                        "location": {
                            "description": "The location of the resource group",
                            "value": "eastus",
                        }
                    },
                ],
                "/home/user/infra/modules/recoveryservicesvault/outputs.tf": [
                    {
                        "name": {
                            "description": "The name of the recovery services vault",
                            "value": "rsv-myapp-prod",
                        }
                    },
                ],
            },
            "variable_map": {
                "main": {},
                "keyvault_private_endpoint": {},
                "sql_server": {},
                "log_analytics_workspace": {},
                "recoveryservicesvault_private_endpoint": {},
            },
            "all_locals": {},
            "all_module": {
                "/home/user/infra/main.tf": [
                    {
                        "keyvault": {
                            "source": "./modules/keyvault",
                            "name": "kv-myapp-prod",
                        }
                    },
                    {
                        "resource_group": {
                            "source": "./modules/resource_group",
                            "name": "rg-myapp-prod",
                        }
                    },
                    {
                        "recoveryservicesvault": {
                            "source": "./modules/recoveryservicesvault",
                            "name": "rsv-myapp-prod",
                        }
                    },
                    {
                        "keyvault_private_endpoint": {
                            "source": "./modules/private_endpoint",
                            "name": "module.keyvault.name",
                            "resource_id": "module.keyvault.id",
                        }
                    },
                    {
                        "recoveryservicesvault_private_endpoint": {
                            "source": "./modules/private_endpoint",
                            "name": "module.recoveryservicesvault.name",
                            "resource_id": "module.recoveryservicesvault.id",
                        }
                    },
                    {
                        "sql_server": {
                            "source": "./modules/sql_server",
                            "resource_group_name": "module.resource_group.name",
                        }
                    },
                    {
                        "log_analytics_workspace": {
                            "source": "./modules/log_analytics",
                            "resource_group_name": "module.resource_group.name",
                        }
                    },
                ]
            },
            "module_source_dict": {
                "keyvault": "/home/user/infra/modules/keyvault",
                "resource_group": "/home/user/infra/modules/resource_group",
                "recoveryservicesvault": "/home/user/infra/modules/recoveryservicesvault",
                "keyvault_private_endpoint": "/home/user/infra/modules/private_endpoint",
                "recoveryservicesvault_private_endpoint": "/home/user/infra/modules/private_endpoint",
                "sql_server": "/home/user/infra/modules/sql_server",
                "log_analytics_workspace": "/home/user/infra/modules/log_analytics",
            },
        }

    @patch("modules.interpreter.click.echo")
    def test_local_module_keyvault_name_resolves(self, mock_echo):
        """module.keyvault.name should resolve via module_source_dict lookup."""
        tfdata = self._make_tfdata_with_local_module_outputs()

        result = replace_module_vars(
            ["module.keyvault.name"],
            "module.keyvault.name",
            "keyvault_private_endpoint",
            tfdata,
            recursion_depth=0,
        )

        warning_calls = [
            str(call)
            for call in mock_echo.call_args_list
            if "Cannot resolve" in str(call)
        ]
        self.assertEqual(
            len(warning_calls),
            0,
            f"Unexpected 'Cannot resolve' warnings: {warning_calls}",
        )
        self.assertNotIn("UNKNOWN", result)
        self.assertIn("kv-myapp-prod", result)

    @patch("modules.interpreter.click.echo")
    def test_local_module_resource_group_name_resolves(self, mock_echo):
        """module.resource_group.name should resolve via module_source_dict lookup."""
        tfdata = self._make_tfdata_with_local_module_outputs()

        result = replace_module_vars(
            ["module.resource_group.name"],
            "module.resource_group.name",
            "sql_server",
            tfdata,
            recursion_depth=0,
        )

        warning_calls = [
            str(call)
            for call in mock_echo.call_args_list
            if "Cannot resolve" in str(call)
        ]
        self.assertEqual(
            len(warning_calls),
            0,
            f"Unexpected 'Cannot resolve' warnings: {warning_calls}",
        )
        self.assertNotIn("UNKNOWN", result)
        self.assertIn("rg-myapp-prod", result)

    @patch("modules.interpreter.click.echo")
    def test_local_module_recoveryservicesvault_name_resolves(self, mock_echo):
        """module.recoveryservicesvault.name should resolve via module_source_dict."""
        tfdata = self._make_tfdata_with_local_module_outputs()

        result = replace_module_vars(
            ["module.recoveryservicesvault.name"],
            "module.recoveryservicesvault.name",
            "recoveryservicesvault_private_endpoint",
            tfdata,
            recursion_depth=0,
        )

        warning_calls = [
            str(call)
            for call in mock_echo.call_args_list
            if "Cannot resolve" in str(call)
        ]
        self.assertEqual(
            len(warning_calls),
            0,
            f"Unexpected 'Cannot resolve' warnings: {warning_calls}",
        )
        self.assertNotIn("UNKNOWN", result)
        self.assertIn("rsv-myapp-prod", result)

    @patch("modules.interpreter.click.echo")
    def test_remote_module_output_still_resolves(self, mock_echo):
        """Remote module outputs (with ;module; in path) must still resolve."""
        tfdata = self._make_tfdata_with_local_module_outputs()

        # Add a remote-style entry WITH the ;module; pattern
        tfdata["all_output"][
            "/home/user/.terravision/module_cache/some_repo;keyvault;/outputs.tf"
        ] = [
            {
                "name": {
                    "description": "The name of the keyvault",
                    "value": "kv-remote-prod",
                }
            },
        ]
        # Remove local path so only the remote one matches
        del tfdata["all_output"]["/home/user/infra/modules/keyvault/outputs.tf"]
        del tfdata["module_source_dict"]["keyvault"]

        result = replace_module_vars(
            ["module.keyvault.name"],
            "module.keyvault.name",
            "keyvault_private_endpoint",
            tfdata,
            recursion_depth=0,
        )

        self.assertNotIn("UNKNOWN", result)
        self.assertIn("kv-remote-prod", result)

    @patch("modules.interpreter.click.echo")
    def test_no_false_match_on_similar_module_names(self, mock_echo):
        """Ensure keyvault_extra doesn't accidentally match keyvault's outputs."""
        tfdata = self._make_tfdata_with_local_module_outputs()
        # Add a module whose name is a prefix of another
        tfdata["module_source_dict"][
            "keyvault_extra"
        ] = "/home/user/infra/modules/keyvault_extra"
        tfdata["variable_map"]["keyvault_extra"] = {}

        # keyvault_extra should NOT resolve from keyvault's outputs
        result = replace_module_vars(
            ["module.keyvault_extra.name"],
            "module.keyvault_extra.name",
            "some_consumer",
            tfdata,
            recursion_depth=0,
        )

        # No output file exists for keyvault_extra, so it should be UNKNOWN
        self.assertIn("UNKNOWN", result)

    @patch("modules.interpreter.click.echo")
    def test_no_module_source_dict_falls_back_gracefully(self, mock_echo):
        """When module_source_dict is missing, only ;mod; matching should work."""
        tfdata = self._make_tfdata_with_local_module_outputs()
        del tfdata["module_source_dict"]

        # Without module_source_dict, local paths won't match
        result = replace_module_vars(
            ["module.keyvault.name"],
            "module.keyvault.name",
            "keyvault_private_endpoint",
            tfdata,
            recursion_depth=0,
        )

        self.assertIn("UNKNOWN", result)


if __name__ == "__main__":
    unittest.main(exit=False)
