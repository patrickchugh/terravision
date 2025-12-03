"""Unit tests for terravision.py CLI functions."""

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from terravision import _validate_source


class TestValidateSource(unittest.TestCase):
    """Test _validate_source() for source input validation."""

    def test_validate_source_all_entries(self):
        """Test that all source entries are validated, not just the first."""
        # Test with .tf file as second entry
        with patch("sys.exit") as mock_exit:
            with patch("click.echo") as mock_echo:
                _validate_source(["./valid_dir", "invalid.tf"])

                # Should call sys.exit() for .tf file
                mock_exit.assert_called_once()

                # Should print error message
                mock_echo.assert_called_once()
                error_msg = str(mock_echo.call_args)
                self.assertIn("invalid.tf", error_msg)
                self.assertIn("ERROR", error_msg)

    def test_validate_source_rejects_tf_file(self):
        """Test that individual .tf files are rejected."""
        with patch("sys.exit") as mock_exit:
            with patch("click.echo"):
                _validate_source(["main.tf"])
                mock_exit.assert_called_once()

    def test_validate_source_accepts_directories(self):
        """Test that directory paths are accepted."""
        with patch("sys.exit") as mock_exit:
            # Should not call sys.exit for valid directory paths
            _validate_source(["./terraform", "/path/to/configs"])
            mock_exit.assert_not_called()

    def test_validate_source_accepts_git_urls(self):
        """Test that git URLs are accepted."""
        with patch("sys.exit") as mock_exit:
            _validate_source(["https://github.com/user/repo//terraform"])
            mock_exit.assert_not_called()

    def test_validate_source_multiple_tf_files(self):
        """Test that function exits on first .tf file encountered."""
        with patch("sys.exit") as mock_exit:
            with patch("click.echo"):
                # Should exit on first .tf file encountered
                _validate_source(["main.tf", "variables.tf", "outputs.tf"])
                # sys.exit() called once per .tf file in the loop
                # The function doesn't early-return after first exit
                self.assertEqual(mock_exit.call_count, 3)


if __name__ == "__main__":
    unittest.main()
