"""Tests for the near-linear variable resolver guards in modules.interpreter.

Covers the memoization, re-entrancy guard, and bounded-cost cap added to
find_replace_values (and its per-pass reset in handle_metadata_vars), plus a
regression guard asserting a pathological, deeply-referential attribute resolves
in bounded time rather than blowing up O(refs**depth).
"""

import os
import sys
import time
import unittest
from unittest.mock import patch

parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

import modules.interpreter as interp
from modules.interpreter import find_replace_values, handle_metadata_vars


class ResolverGuardTests(unittest.TestCase):
    def setUp(self):
        # Isolate module-level caches between tests.
        interp._FRV_CACHE.clear()
        interp._FRV_STACK.clear()
        interp._FRV_STATE.clear()
        interp._FRV_STATE["calls"] = 0

    def test_normal_local_resolution_unchanged(self):
        """A simple local reference still resolves to its value."""
        tfdata = {"all_locals": {"main": {"foo": "bar"}}}
        self.assertEqual(find_replace_values("${local.foo}", "main", tfdata).strip(), "bar")

    def test_cache_hit_does_not_consume_budget(self):
        """A cached (value, module) returns immediately without spending budget."""
        interp._FRV_CACHE[("${local.foo}", "main")] = "cached"
        interp._FRV_STATE["calls"] = 0
        result = find_replace_values("${local.foo}", "main", {"all_locals": {}})
        self.assertEqual(result, "cached")
        self.assertEqual(interp._FRV_STATE["calls"], 0)  # budget untouched

    def test_reentrant_call_returns_str_unchanged(self):
        """A re-entrant identical (value, module) short-circuits and returns a str."""
        interp._FRV_STACK.add(("${module.m.a}", "main"))
        result = find_replace_values("${module.m.a}", "main", {})
        self.assertEqual(result, "${module.m.a}")
        self.assertIsInstance(result, str)

    def test_stack_marker_removed_on_exception(self):
        """An exception mid-resolution must not leave a stale _FRV_STACK entry."""
        key = ("${local.x}", "main")
        with patch.object(
            interp.helpers, "strip_var_curlies", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                find_replace_values("${local.x}", "main", {"all_locals": {}})
        self.assertNotIn(key, interp._FRV_STACK)

    def test_cost_cap_calls_bounds_and_warns(self):
        """Exceeding the per-attribute call budget returns the input as a str and warns."""
        with patch.object(interp, "_FRV_MAX_CALLS", 0):
            with patch.object(interp.click, "echo") as echo:
                result = find_replace_values("${local.foo}", "main", {"all_locals": {}})
        self.assertEqual(result, "${local.foo}")
        self.assertIsInstance(result, str)
        self.assertTrue(echo.called)  # a warning was emitted

    def test_cost_cap_length_bounds(self):
        """An over-length value bails out unchanged without processing."""
        big = "${local." + "a" * 50 + "}"
        with patch.object(interp, "_FRV_MAX_LEN", 5):
            result = find_replace_values(big, "main", {"all_locals": {}})
        self.assertEqual(result, big)

    def test_deeply_referential_attribute_is_bounded(self):
        """Regression guard: an attribute referencing many mutually-referencing
        module outputs must resolve in bounded time (previously O(refs**depth))."""
        n = 10
        refs = " ".join("${module.m1.o%d}" % i for i in range(n))
        outputs = []
        for i in range(n):
            others = " ".join(
                "${module.m1.o%d}" % j for j in range(n) if j != i
            )
            outputs.append({f"o{i}": {"value": "${var.unset} " + others}})
        tfdata = {
            "meta_data": {"aws_thing.x": {"module": "main", "config": refs}},
            "all_output": {";m1;/outputs.tf": outputs},
            "all_locals": {"main": {}},
            "variable_map": {"main": {}},
            "module_source_dict": {},
        }
        start = time.time()
        handle_metadata_vars(tfdata)
        self.assertLess(time.time() - start, 10.0)  # seconds; patched runs in <1s


if __name__ == "__main__":
    unittest.main()
