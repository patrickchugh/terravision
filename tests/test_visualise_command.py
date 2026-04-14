"""CLI tests for the `terravision visualise` command."""

import os
import sys
import unittest
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(parent_dir)

from terravision.terravision import cli


class TestVisualiseCommand(unittest.TestCase):
    """Tests for the visualise CLI command."""

    def test_command_is_registered(self):
        """The visualise command should be registered with the CLI group."""
        self.assertIn("visualise", cli.commands)

    def test_help_runs(self):
        """The --help flag should produce output without errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["visualise", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("visualise", result.output.lower())

    def test_help_lists_expected_flags(self):
        """The help output should mention all expected flags."""
        runner = CliRunner()
        result = runner.invoke(cli, ["visualise", "--help"])
        for flag in [
            "--source",
            "--workspace",
            "--varfile",
            "--outfile",
            "--show",
            "--simplified",
            "--annotate",
            "--planfile",
            "--graphfile",
            "--debug",
            "--upgrade",
        ]:
            self.assertIn(flag, result.output, f"Missing flag in help: {flag}")

    def test_format_flag_warning(self):
        """Passing --format should print a warning but continue."""
        runner = CliRunner()
        # Use a non-existent source so the command exits early after the warning
        result = runner.invoke(
            cli,
            [
                "visualise",
                "--source",
                "/nonexistent/path",
                "--format",
                "png",
            ],
        )
        # Should print the warning regardless of where the command fails
        self.assertIn("--format", result.output)
        self.assertIn("not applicable", result.output)

    def test_ai_annotate_flag_warning(self):
        """Passing --ai-annotate should print a warning but continue."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "visualise",
                "--source",
                "/nonexistent/path",
                "--ai-annotate",
                "bedrock",
            ],
        )
        self.assertIn("--ai-annotate", result.output)
        self.assertIn("not applicable", result.output)

    def test_html_extension_appended(self):
        """The visualise command should append .html to outfile if missing."""
        runner = CliRunner()
        # Use the bastion tfdata fixture which works without terraform
        fixture = Path(parent_dir) / "tests" / "json" / "bastion-tfdata.json"
        if not fixture.exists():
            self.skipTest("Bastion tfdata fixture not available")

        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                [
                    "visualise",
                    "--source",
                    str(fixture),
                    "--outfile",
                    "my-test-diagram",
                ],
            )
            # The command may produce warnings/errors but should attempt to write
            # the file. Check the working directory for the .html file.
            files = os.listdir(".")
            html_files = [f for f in files if f.endswith(".html")]
            self.assertTrue(
                any("my-test-diagram" in f for f in html_files),
                f"Expected .html file not found. Output: {result.output[-500:]}",
            )


if __name__ == "__main__":
    unittest.main()
