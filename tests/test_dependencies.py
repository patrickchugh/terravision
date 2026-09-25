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


class TestGraphJsonSourceSkipsTerraform:
    """A graph JSON source never runs Terraform, so it must not require it."""

    def test_is_graph_json_source(self):
        from modules.helpers import is_graph_json_source

        assert is_graph_json_source("architecture.tvg.json")
        assert is_graph_json_source("graph.json")
        assert is_graph_json_source("ARCHITECTURE.TVG.JSON")
        assert not is_graph_json_source("./infra")
        assert not is_graph_json_source("graph.tvg")

    @patch("modules.helpers.shutil.which")
    @patch("modules.helpers.os.path.isfile")
    def test_terraform_missing_is_fine_without_terraform(self, mock_isfile, mock_which):
        mock_which.side_effect = lambda exe: (
            None if exe in ("terraform", "tofu") else "/usr/bin/fake"
        )
        mock_isfile.return_value = False

        check_dependencies(needs_terraform=False)  # must not exit

        with pytest.raises(SystemExit):
            check_dependencies()

    def test_preflight_skips_terraform_version_check(self):
        import terravision.terravision as tv

        with (
            patch.object(tv.helpers, "set_tf_binary"),
            patch.object(tv.helpers, "check_dependencies") as deps,
            patch.object(tv.helpers, "check_terraform_version") as version,
        ):
            tv.preflight_check(None, needs_terraform=False)

        deps.assert_called_once_with(needs_terraform=False)
        version.assert_not_called()


class TestWindowsGraphvizPath:
    """A winget Graphviz install is not on PATH; TerraVision finds it anyway."""

    @pytest.fixture
    def windows(self, monkeypatch, tmp_path):
        """Pretend to be Windows with Graphviz installed but not on PATH."""
        import modules.helpers as helpers

        bin_dir = tmp_path / "Graphviz" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "dot.exe").write_text("")
        monkeypatch.setattr(helpers.platform, "system", lambda: "Windows")
        monkeypatch.setattr(helpers.shutil, "which", lambda exe: None)
        monkeypatch.setenv("ProgramFiles", str(tmp_path))
        monkeypatch.delenv("ProgramFiles(x86)", raising=False)
        monkeypatch.setenv("PATH", "C:\\Windows")
        return bin_dir

    def test_install_dir_is_appended_to_path(self, windows):
        import os

        from modules.helpers import add_windows_graphviz_to_path

        assert add_windows_graphviz_to_path() == str(windows)
        assert os.environ["PATH"] == os.pathsep.join(["C:\\Windows", str(windows)])

    def test_dot_already_on_path_wins(self, windows, monkeypatch):
        import os

        import modules.helpers as helpers

        monkeypatch.setattr(helpers.shutil, "which", lambda exe: "C:\\other\\dot.exe")
        assert helpers.add_windows_graphviz_to_path() is None
        assert os.environ["PATH"] == "C:\\Windows"

    def test_not_installed_changes_nothing(self, windows):
        import os

        from modules.helpers import add_windows_graphviz_to_path

        (windows / "dot.exe").unlink()
        assert add_windows_graphviz_to_path() is None
        assert os.environ["PATH"] == "C:\\Windows"

    def test_other_platforms_are_untouched(self, windows, monkeypatch):
        import os

        import modules.helpers as helpers

        monkeypatch.setattr(helpers.platform, "system", lambda: "Linux")
        assert helpers.add_windows_graphviz_to_path() is None
        assert os.environ["PATH"] == "C:\\Windows"

    def test_preflight_uses_it(self, windows, monkeypatch):
        """check_dependencies passes once the install dir is on PATH."""
        import os

        import modules.helpers as helpers

        monkeypatch.setattr(
            helpers.shutil,
            "which",
            lambda exe: (
                "found" if exe != "dot" or str(windows) in os.environ["PATH"] else None
            ),
        )
        helpers.check_dependencies(needs_terraform=False)
        assert str(windows) in os.environ["PATH"]

    def test_mcp_binary_check_uses_it(self, windows, monkeypatch):
        import os

        import modules.helpers as helpers
        import modules.mcp_service as mcp_service

        monkeypatch.setattr(
            helpers.shutil,
            "which",
            lambda exe: (
                "found"
                if exe not in ("dot", "gvpr") or str(windows) in os.environ["PATH"]
                else None
            ),
        )
        mcp_service._check_binaries(needs_terraform=False)
