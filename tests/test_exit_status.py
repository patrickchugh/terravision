"""Failures exit with status 1, so a CI job running TerraVision fails too.

Issue #285: a bare exit() means status 0, so a run that printed ERROR and
drew nothing still passed in CI.
"""

import ast
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules import helpers, validators

MODULES = Path(__file__).resolve().parent.parent / "modules"


def _exit_calls_without_status(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "exit":
            continue
        status = node.args[0] if node.args else None
        if status is None or (isinstance(status, ast.Constant) and status.value == 0):
            yield node.lineno


@pytest.mark.parametrize("path", sorted(MODULES.glob("*.py")), ids=lambda p: p.name)
def test_no_module_exits_with_status_0(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert list(_exit_calls_without_status(tree)) == []


def _fake_version(monkeypatch, stdout):
    monkeypatch.setattr(helpers, "get_tf_binary", lambda: "terraform")
    monkeypatch.setattr(
        helpers.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout=stdout, returncode=0),
    )


def test_unsupported_engine_version_exits_1(monkeypatch):
    _fake_version(monkeypatch, "Terraform v0.12.31\n")
    with pytest.raises(SystemExit) as err:
        helpers.check_terraform_version()
    assert err.value.code == 1


def test_unreadable_engine_version_exits_1(monkeypatch):
    monkeypatch.setattr(helpers, "get_tf_binary", lambda: "terraform")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(helpers.subprocess, "run", fail)
    with pytest.raises(SystemExit) as err:
        helpers.check_terraform_version()
    assert err.value.code == 1


def test_supported_engine_version_passes(monkeypatch):
    _fake_version(monkeypatch, "OpenTofu v1.13.0\n")
    helpers.check_terraform_version()


def test_tf_file_as_source_exits_1():
    with pytest.raises(SystemExit) as err:
        validators.validate_source("main.tf")
    assert err.value.code == 1
