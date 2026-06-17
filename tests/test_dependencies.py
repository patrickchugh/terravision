"""Tests for dependency preflight checks in helpers module."""

import pytest
from unittest.mock import patch

from modules.helpers import check_dependencies, _get_os_family


class TestCheckDependencies:
    """Tests for check_dependencies() function."""

    @patch("modules.helpers.shutil.which")
    @patch("modules.helpers.os.path.isfile")
    def test_all_dependencies_present(self, mock_isfile, mock_which):
        """When all dependencies are present, function should echo and return."""
        mock_which.return_value = "/usr/bin/fake"
        mock_isfile.return_value = False

        check_dependencies()

    @patch("modules.helpers.shutil.which")
    @patch("modules.helpers.os.path.isfile")
    def test_missing_single_dependency(self, mock_isfile, mock_which):
        """Missing a single dependency should report it and exit."""

        def fake_which(exe):
            return None if exe == "dot" else "/usr/bin/fake"

        mock_which.side_effect = fake_which
        mock_isfile.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            check_dependencies()

        assert exc_info.value.code == 1

    @patch("modules.helpers.shutil.which")
    @patch("modules.helpers.os.path.isfile")
    def test_missing_multiple_dependencies(self, mock_isfile, mock_which):
        """Missing multiple dependencies should report all of them."""

        def fake_which(exe):
            return None if exe in ("dot", "terraform") else "/usr/bin/fake"

        mock_which.side_effect = fake_which
        mock_isfile.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            check_dependencies()

        assert exc_info.value.code == 1

    @patch("modules.helpers.shutil.which")
    @patch("modules.helpers.os.path.isfile")
    def test_missing_git_dependency(self, mock_isfile, mock_which):
        """Missing git should report Git specifically."""

        def fake_which(exe):
            return None if exe == "git" else "/usr/bin/fake"

        mock_which.side_effect = fake_which
        mock_isfile.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            check_dependencies()

        assert exc_info.value.code == 1


class TestGetOsFamily:
    """Tests for _get_os_family() helper."""

    @patch("modules.helpers.platform.system")
    def test_detects_macos(self, mock_system):
        mock_system.return_value = "Darwin"
        assert _get_os_family() == "macos"

    @patch("modules.helpers.platform.system")
    @patch("modules.helpers.is_wsl")
    def test_detects_wsl(self, mock_is_wsl, mock_system):
        mock_system.return_value = "Linux"
        mock_is_wsl.return_value = True
        assert _get_os_family() == "wsl"

    @patch("modules.helpers.platform.system")
    @patch("modules.helpers.is_wsl")
    @patch("builtins.open")
    def test_detects_debian(self, mock_open, mock_is_wsl, mock_system):
        mock_system.return_value = "Linux"
        mock_is_wsl.return_value = False
        mock_open.return_value.__enter__.return_value.read.return_value = (
            'ID="ubuntu"\nID_LIKE="debian"\n'
        )
        assert _get_os_family() == "debian"

    @patch("modules.helpers.platform.system")
    @patch("modules.helpers.is_wsl")
    @patch("builtins.open")
    def test_detects_generic_linux(self, mock_open, mock_is_wsl, mock_system):
        mock_system.return_value = "Linux"
        mock_is_wsl.return_value = False
        mock_open.return_value.__enter__.return_value.read.return_value = (
            'ID="fedora"\n'
        )
        assert _get_os_family() == "linux"

    @patch("modules.helpers.platform.system")
    def test_detects_windows(self, mock_system):
        mock_system.return_value = "Windows"
        assert _get_os_family() == "windows"

    @patch("modules.helpers.platform.system")
    def test_detects_unknown(self, mock_system):
        mock_system.return_value = "FreeBSD"
        assert _get_os_family() == "unknown"
