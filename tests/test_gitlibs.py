"""Unit tests for gitlibs URL parsing functions.

Tests that various Terraform module source URL formats are correctly parsed
into (clone_url, subfolder, git_tag) tuples.
"""

import io
import tarfile
import zipfile

import pytest

import modules.gitlibs as gitlibs
from modules.gitlibs import (
    _download_and_extract_archive,
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


class TestDownloadAndExtractArchive:
    """A module archive comes from an untrusted URL: extraction must stay
    inside the destination and refuse archive bombs."""

    @staticmethod
    def _serve(monkeypatch, data: bytes) -> None:
        class FakeResponse:
            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size):
                yield data

        monkeypatch.setattr(gitlibs.requests, "get", lambda *a, **k: FakeResponse())

    @staticmethod
    def _tar(members) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for info, content in members:
                tf.addfile(info, io.BytesIO(content) if content is not None else None)
        return buf.getvalue()

    @staticmethod
    def _file(name: str, content: bytes = b"x"):
        info = tarfile.TarInfo(name)
        info.size = len(content)
        return info, content

    @staticmethod
    def _zip(names) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name in names:
                zf.writestr(name, "x")
        return buf.getvalue()

    def test_tar_extracts(self, monkeypatch, tmp_path):
        self._serve(monkeypatch, self._tar([self._file("mod/main.tf", b"# ok")]))
        dest = tmp_path / "dest"

        _download_and_extract_archive("https://example.com/mod.tar.gz", str(dest))

        assert (dest / "mod" / "main.tf").read_bytes() == b"# ok"

    def test_zip_extracts(self, monkeypatch, tmp_path):
        self._serve(monkeypatch, self._zip(["mod/main.tf"]))
        dest = tmp_path / "dest"

        _download_and_extract_archive("https://example.com/mod.zip", str(dest))

        assert (dest / "mod" / "main.tf").exists()

    @pytest.mark.parametrize(
        "name", ["../evil.tf", "mod/../../evil.tf", "/tmp/evil.tf"]
    )
    def test_tar_path_outside_destination_is_refused(self, monkeypatch, tmp_path, name):
        self._serve(monkeypatch, self._tar([self._file(name)]))
        dest = tmp_path / "dest"

        with pytest.raises(SystemExit):
            _download_and_extract_archive("https://example.com/mod.tar.gz", str(dest))

        assert not (tmp_path / "evil.tf").exists()

    def test_tar_link_outside_destination_is_refused(self, monkeypatch, tmp_path):
        link = tarfile.TarInfo("mod/passwd")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../../../etc/passwd"
        self._serve(monkeypatch, self._tar([(link, None)]))

        with pytest.raises(SystemExit):
            _download_and_extract_archive(
                "https://example.com/mod.tar.gz", str(tmp_path / "dest")
            )

    def test_zip_path_outside_destination_is_refused(self, monkeypatch, tmp_path):
        self._serve(monkeypatch, self._zip(["../evil.tf"]))

        with pytest.raises(SystemExit):
            _download_and_extract_archive(
                "https://example.com/mod.zip", str(tmp_path / "dest")
            )

        assert not (tmp_path / "evil.tf").exists()

    def test_too_many_entries_is_refused(self, monkeypatch, tmp_path):
        monkeypatch.setattr(gitlibs, "_ARCHIVE_MAX_ENTRIES", 2)
        self._serve(monkeypatch, self._zip(["a.tf", "b.tf", "c.tf"]))

        with pytest.raises(SystemExit):
            _download_and_extract_archive(
                "https://example.com/mod.zip", str(tmp_path / "dest")
            )

    def test_too_large_is_refused(self, monkeypatch, tmp_path):
        monkeypatch.setattr(gitlibs, "_ARCHIVE_MAX_BYTES", 10)
        self._serve(monkeypatch, self._tar([self._file("mod/main.tf", b"x" * 11)]))
        dest = tmp_path / "dest"

        with pytest.raises(SystemExit):
            _download_and_extract_archive("https://example.com/mod.tar.gz", str(dest))

        assert not (dest / "mod" / "main.tf").exists()

    def test_tar_without_data_filter_is_refused(self, monkeypatch, tmp_path):
        monkeypatch.delattr(tarfile, "data_filter")
        self._serve(monkeypatch, self._tar([self._file("mod/main.tf")]))
        dest = tmp_path / "dest"

        with pytest.raises(SystemExit):
            _download_and_extract_archive("https://example.com/mod.tar.gz", str(dest))

        assert not (dest / "mod" / "main.tf").exists()

    def test_corrupt_archive_is_refused(self, monkeypatch, tmp_path):
        self._serve(monkeypatch, b"not an archive")

        with pytest.raises(SystemExit):
            _download_and_extract_archive(
                "https://example.com/mod.zip", str(tmp_path / "dest")
            )
