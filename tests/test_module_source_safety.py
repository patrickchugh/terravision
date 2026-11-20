"""A module source can name code to download, never options, files or tokens.

Module sources come from Terraform code the user may not have written: a
?ref= must reach git as a ref, a //subfolder must stay inside the module,
and a private registry's token must go only to that registry.
"""

from unittest.mock import MagicMock

import git
import pytest

import modules.gitlibs as gitlibs


@pytest.mark.parametrize(
    "subfolder,expected",
    [
        ("", ""),
        ("modules/vpc", "modules/vpc"),
        ("modules/vpc/", "modules/vpc"),
        ("/modules/vpc", "modules/vpc"),
        ("modules/../vpc", "vpc"),
        (".", ""),
    ],
)
def test_subfolders_inside_the_module_are_kept(subfolder, expected):
    assert gitlibs._safe_subfolder(subfolder, "src") == expected


@pytest.mark.parametrize("subfolder", ["..", "../../etc", "a/../../b", "//../x"])
def test_subfolders_outside_the_module_stop_the_run(subfolder):
    with pytest.raises(SystemExit) as err:
        gitlibs._safe_subfolder(subfolder, "src")
    assert err.value.code == 1


@pytest.mark.parametrize("ref", ["", "v1.2.0", "main", "feature/x", "a1b2c3d"])
def test_ordinary_refs_pass(ref):
    gitlibs._check_git_ref(ref, "src")


@pytest.mark.parametrize(
    "ref", ["main --upload-pack=touch /tmp/x", "--upload-pack=x", "-c", "a\tb"]
)
def test_refs_git_could_read_as_options_stop_the_run(ref):
    with pytest.raises(SystemExit) as err:
        gitlibs._check_git_ref(ref, "src")
    assert err.value.code == 1


def test_clone_passes_the_ref_as_one_branch_argument(tmp_path, monkeypatch):
    clone = MagicMock()
    monkeypatch.setattr(git.Repo, "clone_from", clone)
    gitlibs._clone_full_repo(
        "https://github.com/org/repo.git", "", "v1.2.0", str(tmp_path / "dest")
    )
    kwargs = clone.call_args.kwargs
    assert kwargs["branch"] == "v1.2.0"
    assert "multi_options" not in kwargs


def test_clone_with_an_injected_ref_never_calls_git(tmp_path, monkeypatch):
    clone = MagicMock()
    monkeypatch.setattr(git.Repo, "clone_from", clone)
    with pytest.raises(SystemExit):
        gitlibs._clone_full_repo(
            "https://github.com/org/repo.git",
            "",
            "main --upload-pack=echo_marker",
            str(tmp_path / "dest"),
        )
    clone.assert_not_called()


def _registry_calls(monkeypatch, tmp_path, modules_v1):
    """Resolve a private-registry module; return (url, headers) of each call."""
    monkeypatch.setattr(gitlibs, "MODULE_DIR", str(tmp_path))
    monkeypatch.setenv("TF_TOKEN_reg_example_com", "SECRET")
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, dict(headers or {})))
        response = MagicMock()
        if url.endswith("/.well-known/terraform.json"):
            response.json.return_value = {"modules.v1": modules_v1}
        else:
            response.json.return_value = {
                "source": "https://github.com/org/terraform-aws-vpc"
            }
        return response

    monkeypatch.setattr(gitlibs.requests, "get", fake_get)
    gitlibs._handle_registry_url("reg.example.com/org/vpc/aws")
    return calls


def test_registry_token_goes_to_its_own_host(monkeypatch, tmp_path):
    calls = _registry_calls(monkeypatch, tmp_path, "/api/registry/v1/modules/")
    url, headers = calls[-1]
    assert url.startswith("https://reg.example.com/api/registry/v1/modules/")
    assert headers == {"Authorization": "Bearer SECRET"}


@pytest.mark.parametrize(
    "modules_v1",
    [
        "https://elsewhere.example/v1/modules/",
        "http://reg.example.com/v1/modules/",
        "https://reg.example.com.elsewhere.example/v1/modules/",
    ],
)
def test_registry_token_never_goes_elsewhere(monkeypatch, tmp_path, modules_v1):
    calls = _registry_calls(monkeypatch, tmp_path, modules_v1)
    assert all("Authorization" not in headers for _, headers in calls)
