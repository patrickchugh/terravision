"""Unit tests for gitlibs URL parsing functions.

Tests that various Terraform module source URL formats are correctly parsed
into (clone_url, subfolder, git_tag) tuples.
"""

import pytest

from modules.gitlibs import _handle_git_prefix_url, get_clone_url


class TestHandleGitPrefixUrl:
    """Tests for _handle_git_prefix_url parsing."""

    # git::https:// URLs

    def test_git_https_bare(self):
        url = "git::https://github.com/owner/repo.git"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "https://github.com/owner/repo.git"
        assert subfolder == ""
        assert tag == ""

    def test_git_https_with_subfolder(self):
        url = "git::https://github.com/owner/repo.git//modules/submod"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "https://github.com/owner/repo.git"
        assert subfolder == "modules/submod"
        assert tag == ""

    def test_git_https_with_ref(self):
        url = "git::https://github.com/owner/repo.git?ref=v1.0.0"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "https://github.com/owner/repo.git"
        assert subfolder == ""
        assert tag == "v1.0.0"

    def test_git_https_with_subfolder_and_ref(self):
        url = "git::https://github.com/owner/repo.git//modules/submod?ref=v2.0.0"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "https://github.com/owner/repo.git"
        assert subfolder == "modules/submod"
        assert tag == "v2.0.0"

    # git::ssh:// URLs (Azure DevOps style)

    def test_git_ssh_azure_devops_bare(self):
        url = "git::ssh://git@ssh.dev.azure.com/v3/org/project/repo"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "ssh://git@ssh.dev.azure.com/v3/org/project/repo"
        assert subfolder == ""
        assert tag == ""

    def test_git_ssh_azure_devops_with_subfolder(self):
        url = (
            "git::ssh://git@ssh.dev.azure.com/v3/org/project/terraform-modules//lambda"
        )
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "ssh://git@ssh.dev.azure.com/v3/org/project/terraform-modules"
        assert subfolder == "lambda"
        assert tag == ""

    def test_git_ssh_azure_devops_with_ref(self):
        url = "git::ssh://git@ssh.dev.azure.com/v3/org/project/repo?ref=v1.0.1"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "ssh://git@ssh.dev.azure.com/v3/org/project/repo"
        assert subfolder == ""
        assert tag == "v1.0.1"

    def test_git_ssh_azure_devops_with_subfolder_and_ref(self):
        url = "git::ssh://git@ssh.dev.azure.com/v3/org/project/terraform-modules//lambda?ref=v1.0.1"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "ssh://git@ssh.dev.azure.com/v3/org/project/terraform-modules"
        assert subfolder == "lambda"
        assert tag == "v1.0.1"

    # git::ssh:// with standard GitHub/GitLab

    def test_git_ssh_github(self):
        url = "git::ssh://git@github.com/owner/repo.git"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "ssh://git@github.com/owner/repo.git"
        assert subfolder == ""
        assert tag == ""

    def test_git_ssh_github_with_subfolder_and_ref(self):
        url = "git::ssh://git@github.com/owner/repo.git//modules/sub?ref=v3.0.0"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "ssh://git@github.com/owner/repo.git"
        assert subfolder == "modules/sub"
        assert tag == "v3.0.0"

    # SCP-style git@ URLs (no ssh:// protocol)

    def test_git_scp_style_github(self):
        url = "git::git@github.com:owner/repo.git"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "git@github.com:owner/repo.git"
        assert subfolder == ""
        assert tag == ""

    def test_git_scp_style_with_subfolder_and_ref(self):
        url = "git::git@github.com:owner/repo.git//modules/sub?ref=v1.0.0"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "git@github.com:owner/repo.git"
        assert subfolder == "modules/sub"
        assert tag == "v1.0.0"

    # GitLab git::https with subfolder and ref

    def test_git_https_gitlab_with_subfolder_and_ref(self):
        url = "git::https://gitlab.com/group/subgroup/repo.git//modules/sub?ref=v1.0.0"
        git_url, subfolder, tag = _handle_git_prefix_url(url)
        assert git_url == "https://gitlab.com/group/subgroup/repo.git"
        assert subfolder == "modules/sub"
        assert tag == "v1.0.0"


class TestGetCloneUrl:
    """Tests for get_clone_url routing."""

    def test_git_ssh_azure_devops_routes_correctly(self):
        url = "git::ssh://git@ssh.dev.azure.com/v3/org/project/terraform-modules//lambda?ref=v1.0.1"
        git_url, subfolder, tag = get_clone_url(url)
        assert git_url == "ssh://git@ssh.dev.azure.com/v3/org/project/terraform-modules"
        assert subfolder == "lambda"
        assert tag == "v1.0.1"

    def test_git_https_routes_correctly(self):
        url = "git::https://github.com/owner/repo.git//modules/sub?ref=v2.0.0"
        git_url, subfolder, tag = get_clone_url(url)
        assert git_url == "https://github.com/owner/repo.git"
        assert subfolder == "modules/sub"
        assert tag == "v2.0.0"
