"""Unit tests for gitlibs URL parsing functions.

Tests that various Terraform module source URL formats are correctly parsed
into (clone_url, subfolder, git_tag) tuples.
"""

import pytest

from modules.gitlibs import (
    _handle_git_prefix_url,
    _handle_http_archive_url,
    _is_http_archive,
    get_clone_url,
)


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

    def test_http_archive_routes_correctly(self):
        url = "https://example.com/modules/vpc.tar.gz"
        git_url, subfolder, tag = get_clone_url(url)
        assert git_url == "https://example.com/modules/vpc.tar.gz"
        assert subfolder == ""
        assert tag == ""

    def test_s3_archive_routes_correctly(self):
        url = "s3::https://bucket.s3.amazonaws.com/modules/vpc.tar.gz"
        git_url, subfolder, tag = get_clone_url(url)
        assert git_url == "https://bucket.s3.amazonaws.com/modules/vpc.tar.gz"
        assert subfolder == ""
        assert tag == ""


class TestIsHttpArchive:
    """Tests for _is_http_archive detection."""

    def test_tar_gz(self):
        assert _is_http_archive("https://example.com/module.tar.gz") is True

    def test_tgz(self):
        assert _is_http_archive("https://example.com/module.tgz") is True

    def test_zip(self):
        assert _is_http_archive("https://example.com/module.zip") is True

    def test_tar_bz2(self):
        assert _is_http_archive("https://example.com/module.tar.bz2") is True

    def test_tar_xz(self):
        assert _is_http_archive("https://example.com/module.tar.xz") is True

    def test_plain_tar(self):
        assert _is_http_archive("https://example.com/module.tar") is True

    def test_s3_prefix_tar_gz(self):
        assert (
            _is_http_archive("s3::https://bucket.s3.amazonaws.com/mod.tar.gz") is True
        )

    def test_gcs_prefix_zip(self):
        assert _is_http_archive("gcs::https://storage.googleapis.com/mod.zip") is True

    def test_with_query_params(self):
        assert _is_http_archive("https://example.com/module.tar.gz?version=1") is True

    def test_with_subfolder(self):
        assert _is_http_archive("https://example.com/module.tar.gz//subdir") is True

    def test_not_archive_git_url(self):
        assert _is_http_archive("git::https://github.com/owner/repo.git") is False

    def test_not_archive_registry(self):
        assert _is_http_archive("terraform-aws-modules/vpc/aws") is False

    def test_not_archive_github_shorthand(self):
        assert _is_http_archive("github.com/owner/repo") is False


class TestHandleHttpArchiveUrl:
    """Tests for _handle_http_archive_url parsing."""

    def test_plain_https_tar_gz(self):
        url = "https://example.com/modules/vpc.tar.gz"
        download_url, subfolder, tag = _handle_http_archive_url(url)
        assert download_url == "https://example.com/modules/vpc.tar.gz"
        assert subfolder == ""
        assert tag == ""

    def test_s3_prefix_stripped(self):
        url = "s3::https://bucket.s3.amazonaws.com/modules/vpc.tar.gz"
        download_url, subfolder, tag = _handle_http_archive_url(url)
        assert download_url == "https://bucket.s3.amazonaws.com/modules/vpc.tar.gz"
        assert subfolder == ""
        assert tag == ""

    def test_gcs_prefix_stripped(self):
        url = "gcs::https://storage.googleapis.com/bucket/module.zip"
        download_url, subfolder, tag = _handle_http_archive_url(url)
        assert download_url == "https://storage.googleapis.com/bucket/module.zip"
        assert subfolder == ""
        assert tag == ""

    def test_with_subfolder(self):
        url = "https://example.com/modules/iam.tar.gz//modules/iam-user"
        download_url, subfolder, tag = _handle_http_archive_url(url)
        assert download_url == "https://example.com/modules/iam.tar.gz"
        assert subfolder == "modules/iam-user"
        assert tag == ""

    def test_s3_with_subfolder(self):
        url = "s3::https://bucket.s3.amazonaws.com/iam.tar.gz//modules/iam-user"
        download_url, subfolder, tag = _handle_http_archive_url(url)
        assert download_url == "https://bucket.s3.amazonaws.com/iam.tar.gz"
        assert subfolder == "modules/iam-user"
        assert tag == ""

    def test_tag_always_empty(self):
        url = "https://example.com/module.tar.gz"
        _, _, tag = _handle_http_archive_url(url)
        assert tag == ""
