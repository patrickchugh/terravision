"""Tests for Terragrunt detection via validators.is_terragrunt_source()."""

import os
import tempfile

import pytest

import modules.validators as validators


class TestIsTerragruntSource:
    """Test validators.is_terragrunt_source() with various directory types."""

    def test_terraform_only_dir(self, tmp_path):
        """Directory with only .tf files is NOT Terragrunt."""
        (tmp_path / "main.tf").write_text('resource "null_resource" "a" {}')
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is False
        assert result["is_multi_module"] is False
        assert result["child_modules"] == []

    def test_single_module_terragrunt(self, tmp_path):
        """Directory with terragrunt.hcl in root is single-module."""
        (tmp_path / "terragrunt.hcl").write_text('terraform { source = "." }')
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is True
        assert result["is_multi_module"] is False

    def test_multi_module_terragrunt(self, tmp_path):
        """Directory with terragrunt.hcl in child dirs is multi-module."""
        vpc = tmp_path / "vpc"
        vpc.mkdir()
        (vpc / "terragrunt.hcl").write_text('terraform { source = "." }')
        app = tmp_path / "app"
        app.mkdir()
        (app / "terragrunt.hcl").write_text('terraform { source = "." }')
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is True
        assert result["is_multi_module"] is True
        assert len(result["child_modules"]) == 2

    def test_empty_dir(self, tmp_path):
        """Empty directory is NOT Terragrunt."""
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is False

    def test_both_tf_and_terragrunt(self, tmp_path):
        """Directory with both .tf and terragrunt.hcl is Terragrunt."""
        (tmp_path / "main.tf").write_text('resource "null_resource" "a" {}')
        (tmp_path / "terragrunt.hcl").write_text('terraform { source = "." }')
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is True

    def test_nonexistent_dir(self):
        """Non-existent directory returns not Terragrunt."""
        result = validators.is_terragrunt_source("/nonexistent/path")
        assert result["is_terragrunt"] is False

    def test_skips_terragrunt_cache(self, tmp_path):
        """Should skip .terragrunt-cache directories."""
        cache = tmp_path / ".terragrunt-cache" / "abc123"
        cache.mkdir(parents=True)
        (cache / "terragrunt.hcl").write_text('terraform { source = "." }')
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is False
        assert result["child_modules"] == []

    def test_deeply_nested_child_modules(self, tmp_path):
        """Detects deeply nested child modules."""
        deep = tmp_path / "region" / "env" / "vpc"
        deep.mkdir(parents=True)
        (deep / "terragrunt.hcl").write_text('terraform { source = "." }')
        result = validators.is_terragrunt_source(str(tmp_path))
        assert result["is_terragrunt"] is True
        assert result["is_multi_module"] is True
        assert len(result["child_modules"]) == 1
