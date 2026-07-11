"""Tests for the crash-reporting boundary around graph enrichment.

Unexpected exceptions during enrichment are wrapped in TerravisionError
carrying the tfdata at the failure point, so default runs print a friendly
one-line error while --debug runs also get a full traceback and a
replayable tfdata.json dump.
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

import modules.helpers as helpers
from terravision.terravision import compile_tfdata, _safe_compile_tfdata

FIXTURE = os.path.join(parent_dir, "tests", "json", "bastion-tfdata.json")


class TestEnrichmentErrorBoundary(unittest.TestCase):
    @patch("terravision.terravision._enrich_graph_data")
    def test_unexpected_error_wrapped_with_tfdata(self, mock_enrich):
        mock_enrich.side_effect = ValueError("boom")
        with self.assertRaises(helpers.TerravisionError) as ctx:
            compile_tfdata(FIXTURE, [], "default", debug=False)
        self.assertIsInstance(ctx.exception.__cause__, ValueError)
        self.assertIsNotNone(ctx.exception.tfdata)
        self.assertIn("likely a TerraVision bug", str(ctx.exception))

    @patch("terravision.terravision._enrich_graph_data")
    def test_terravision_error_passes_through_unwrapped(self, mock_enrich):
        original = helpers.TerravisionError("known failure")
        mock_enrich.side_effect = original
        with self.assertRaises(helpers.TerravisionError) as ctx:
            compile_tfdata(FIXTURE, [], "default", debug=False)
        self.assertIs(ctx.exception, original)


class TestSafeCompileTraceback(unittest.TestCase):
    def _run(self, debug):
        with patch("terravision.terravision.compile_tfdata") as mock_compile:
            try:
                raise ValueError("boom")
            except ValueError as cause:
                err = helpers.TerravisionError("wrapped failure")
                err.__cause__ = cause
            mock_compile.side_effect = err
            with self.assertRaises(SystemExit) as ctx:
                _safe_compile_tfdata(debug, "somewhere", (), "default")
            self.assertEqual(ctx.exception.code, 1)

    def test_debug_prints_traceback(self):
        import io
        from contextlib import redirect_stderr

        buf = io.StringIO()
        with redirect_stderr(buf):
            self._run(debug=True)
        self.assertIn("Traceback", buf.getvalue())
        self.assertIn("wrapped failure", buf.getvalue())

    def test_default_hides_traceback(self):
        import io
        from contextlib import redirect_stderr

        buf = io.StringIO()
        with redirect_stderr(buf):
            self._run(debug=False)
        self.assertNotIn("Traceback", buf.getvalue())
        self.assertIn("wrapped failure", buf.getvalue())


if __name__ == "__main__":
    unittest.main(exit=False)
