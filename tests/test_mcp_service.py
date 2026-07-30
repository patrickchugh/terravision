"""Unit tests for the MCP service layer.

These deliberately avoid importing the ``mcp`` package so the suite runs on a
default install without the optional ``[mcp]`` extra. Everything covered here
concerns running the pipeline inside a long-lived server process rather than a
one-shot CLI: stdout isolation, exit containment, and global state restoration.
"""

import contextlib
import io
import os
import sys
from pathlib import Path

import click
import pytest

import modules.drawing as drawing
import modules.helpers as helpers
from modules.helpers import TerravisionError
from modules.mcp_service import (
    McpServiceError,
    _guarded,
    _provider_suffixed,
    _restored_globals,
    _validate_outfile,
    get_output_dir,
    run_diagram,
    set_output_dir,
    supported_formats,
)


@pytest.fixture(autouse=True)
def _restore_output_dir():
    """Keep the module-level output directory from leaking between tests."""
    import modules.mcp_service as mcp_service

    original = mcp_service._OUTPUT_DIR
    yield
    mcp_service._OUTPUT_DIR = original


# ── Output filename validation (path safety) ──────────────────────────


@pytest.mark.parametrize(
    "name",
    ["architecture", "my-diagram", "diagram_v2", "a.b"],
)
def test_validate_outfile_accepts_plain_names(name):
    assert _validate_outfile(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "   ", "..", "../evil", "../../etc/passwd", "sub/name", "sub\\name"],
)
def test_validate_outfile_rejects_paths_and_traversal(name):
    """An agent-supplied name must not be able to escape the output dir."""
    with pytest.raises(McpServiceError):
        _validate_outfile(name)


def test_validate_outfile_strips_surrounding_whitespace():
    assert _validate_outfile("  architecture  ") == "architecture"


def test_validate_outfile_rejects_both_separators_on_every_platform():
    """Rejection must not depend on the host OS.

    Deferring to os.path.sep/altsep would let "sub\\name" through on POSIX,
    where altsep is None -- so the same agent request would be refused on
    Windows and accepted on Linux.
    """
    for name in ("sub/name", "sub\\name"):
        with pytest.raises(McpServiceError):
            _validate_outfile(name)


# ── Output directory ──────────────────────────────────────────────────


def test_set_output_dir_creates_and_resolves(tmp_path):
    target = tmp_path / "out" / "nested"
    resolved = set_output_dir(str(target))
    assert resolved == target.resolve()
    assert resolved.is_dir()
    assert get_output_dir() == target.resolve()


def test_set_output_dir_defaults_to_cwd():
    assert set_output_dir(None) == Path.cwd().resolve()


def test_set_output_dir_rejects_a_file(tmp_path):
    afile = tmp_path / "file.txt"
    afile.write_text("x")
    with pytest.raises(McpServiceError):
        set_output_dir(str(afile))


# ── Supported formats ─────────────────────────────────────────────────


def test_supported_formats_includes_graphviz_and_drawio():
    formats = supported_formats()
    assert "drawio" in formats
    for expected in ("png", "svg", "pdf", "dot"):
        assert expected in formats


def test_supported_formats_tracks_canvas():
    """The list is read from Canvas rather than duplicated in the service."""
    from resource_classes import Canvas

    for fmt in getattr(Canvas, "_Canvas__outformats", ()):
        assert fmt in supported_formats()


# ── Exit containment ──────────────────────────────────────────────────


def test_guarded_converts_system_exit():
    """sys.exit() in the pipeline must not terminate the server."""
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            sys.exit(2)
    assert "exit code 2" in str(excinfo.value)


def test_system_exit_error_replays_the_cause():
    """The reason must reach the caller, not just the server log.

    Modelled on a real run: a source using live AWS data sources fails at
    plan time with a credentials error. Without the tail, the agent receives
    only "aborted" and has to re-run Terraform by hand to learn why.
    """
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            click.echo("Error: No valid credential sources found")
            click.echo('  with provider["registry.terraform.io/hashicorp/aws"],')
            sys.exit(1)

    message = str(excinfo.value)
    assert "No valid credential sources found" in message
    assert "hashicorp/aws" in message


def test_system_exit_tail_strips_ansi_colour():
    """Pipeline errors are colourised; escape codes must not leak through."""
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            sys.stdout.write("\x1b[31m\x1b[1mERROR: something broke\x1b[0m\n")
            sys.exit(1)
    message = str(excinfo.value)
    assert "ERROR: something broke" in message
    assert "\x1b[" not in message


def test_system_exit_tail_is_bounded():
    """A chatty pipeline must not paste thousands of lines into one error."""
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            for i in range(5000):
                click.echo(f"line {i}")
            sys.exit(1)

    message = str(excinfo.value)
    assert len(message.splitlines()) < 30
    assert "line 4999" in message  # keeps the most recent, not the oldest
    assert "line 0" not in message


def test_system_exit_without_output_still_reports():
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            sys.exit(3)
    message = str(excinfo.value)
    assert "exit code 3" in message
    assert "No further detail" in message


def test_tee_still_writes_through_to_the_log():
    """Capturing the tail must not stop output reaching the server log."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        with pytest.raises(McpServiceError):
            with _guarded(change_dir=False):
                click.echo("diagnostic detail")
                sys.exit(1)
    assert "diagnostic detail" in err.getvalue()


def test_guarded_converts_terravision_error():
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            raise TerravisionError("plan produced no resources")
    assert str(excinfo.value) == "plan produced no resources"


def test_guarded_converts_unexpected_exception():
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            raise KeyError("graphdict")
    assert "KeyError" in str(excinfo.value)


def test_guarded_passes_through_service_error():
    """An already-typed error keeps its message rather than being re-wrapped."""
    with pytest.raises(McpServiceError) as excinfo:
        with _guarded(change_dir=False):
            raise McpServiceError("already formatted")
    assert str(excinfo.value) == "already formatted"


def test_guarded_releases_lock_after_failure():
    """A failed call must not deadlock every subsequent one."""
    for _ in range(3):
        with pytest.raises(McpServiceError):
            with _guarded(change_dir=False):
                raise TerravisionError("boom")
    with _guarded(change_dir=False):
        pass


# ── stdout isolation ──────────────────────────────────────────────────


def test_guarded_keeps_stdout_clean():
    """Pipeline chatter must never reach stdout; it carries JSON-RPC."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with _guarded(change_dir=False):
            click.echo("progress message")
            print("raw print")
    assert out.getvalue() == ""
    assert "progress message" in err.getvalue()
    assert "raw print" in err.getvalue()


def test_guarded_keeps_stdout_clean_on_failure():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with pytest.raises(McpServiceError):
            with _guarded(change_dir=False):
                click.echo("about to fail")
                raise TerravisionError("boom")
    assert out.getvalue() == ""


# ── Global state restoration ──────────────────────────────────────────


def test_restored_globals_restores_rendering_options():
    drawing.DIAGRAM_FONTSIZE = None
    drawing.DIAGRAM_ICONSIZE = None
    helpers.USE_TF_NAMES = False
    helpers.USE_RESOURCE_NAMES = False

    with _restored_globals():
        drawing.DIAGRAM_FONTSIZE = 72
        drawing.DIAGRAM_ICONSIZE = 256
        helpers.USE_TF_NAMES = True
        helpers.USE_RESOURCE_NAMES = True

    assert drawing.DIAGRAM_FONTSIZE is None
    assert drawing.DIAGRAM_ICONSIZE is None
    assert helpers.USE_TF_NAMES is False
    assert helpers.USE_RESOURCE_NAMES is False


def test_restored_globals_restores_on_exception():
    drawing.DIAGRAM_FONTSIZE = None
    with pytest.raises(McpServiceError):
        with _guarded(change_dir=False):
            drawing.DIAGRAM_FONTSIZE = 99
            raise McpServiceError("boom")
    assert drawing.DIAGRAM_FONTSIZE is None


def test_consecutive_calls_do_not_contaminate_each_other():
    """The leak this guards against is options bleeding across requests."""
    drawing.DIAGRAM_FONTSIZE = None
    helpers.USE_TF_NAMES = False

    with _guarded(change_dir=False):
        drawing.DIAGRAM_FONTSIZE = 48
        helpers.USE_TF_NAMES = True

    observed = {}
    with _guarded(change_dir=False):
        observed["fontsize"] = drawing.DIAGRAM_FONTSIZE
        observed["use_tf_names"] = helpers.USE_TF_NAMES

    assert observed == {"fontsize": None, "use_tf_names": False}


def test_restored_globals_clears_diagram_contextvar():
    from resource_classes import getdiagram, setdiagram

    setdiagram("sentinel")
    with _restored_globals():
        pass
    assert getdiagram() is None
    setdiagram(None)


# ── Working directory handling ────────────────────────────────────────


def test_guarded_runs_inside_output_dir_and_restores_cwd(tmp_path):
    target = set_output_dir(str(tmp_path / "generated"))
    before = Path.cwd()
    with _guarded() as outdir:
        assert outdir == target
        assert Path.cwd() == target
    assert Path.cwd() == before


def test_guarded_restores_cwd_on_failure(tmp_path):
    set_output_dir(str(tmp_path / "generated"))
    before = Path.cwd()
    with pytest.raises(McpServiceError):
        with _guarded():
            raise TerravisionError("boom")
    assert Path.cwd() == before


def test_guarded_without_change_dir_leaves_cwd_alone(tmp_path):
    set_output_dir(str(tmp_path / "generated"))
    before = Path.cwd()
    with _guarded(change_dir=False) as outdir:
        assert outdir is None
        assert Path.cwd() == before
    assert Path.cwd() == before


# ── Provider suffix parity with the CLI ───────────────────────────────


def test_provider_suffix_skipped_without_detection():
    """`draw` only suffixes when provider_detection is present.

    A replayed tfdata.json carries no detection block, and the CLI leaves the
    filename untouched in that case. Matching this is what keeps MCP output
    paths identical to the equivalent command.
    """
    assert _provider_suffixed("architecture", {}) == "architecture"
    assert _provider_suffixed("architecture", {"provider_detection": {}}) == (
        "architecture"
    )


def test_provider_suffix_applied_with_detection():
    tfdata = {"provider_detection": {"primary_provider": "gcp"}}
    assert _provider_suffixed("architecture", tfdata) == "architecture-gcp"


def test_provider_suffix_defaults_to_aws():
    tfdata = {"provider_detection": {"detected": True}}
    assert _provider_suffixed("architecture", tfdata) == "architecture-aws"


def test_provider_suffix_not_applied_twice():
    tfdata = {"provider_detection": {"primary_provider": "azure"}}
    assert _provider_suffixed("architecture-azure", tfdata) == "architecture-azure"


# ── Working directory survives the pipeline ───────────────────────────
#
# Regression: tf_initplan() ends with os.chdir(START_DIR), where START_DIR is
# captured at tfwrapper import time. That is the server's launch directory,
# not the output directory _in_output_dir() entered, so a real Terraform
# source used to leave the cwd stranded -- the diagram was written next to the
# server and then reported as missing. A .json replay never reaches tfwrapper,
# so the original tests, which all used replay fixtures, could not catch it.


def _stub_pipeline(monkeypatch, strand_to):
    """Make _compile's pipeline chdir away, as tfwrapper does."""
    import terravision.terravision as tv

    monkeypatch.setattr(tv, "preflight_check", lambda *a, **k: None)

    def fake_compile(*args, **kwargs):
        os.chdir(strand_to)
        return {"graphdict": {"aws_instance.web": []}, "meta_data": {}}

    monkeypatch.setattr(tv, "compile_tfdata", fake_compile)


def test_compile_restores_cwd_when_pipeline_strands_it(tmp_path, monkeypatch):
    import modules.mcp_service as mcp_service

    strand = tmp_path / "elsewhere"
    strand.mkdir()
    outdir = set_output_dir(str(tmp_path / "generated"))
    _stub_pipeline(monkeypatch, strand)
    monkeypatch.setattr(mcp_service, "_check_binaries", lambda: None)

    with _guarded():
        mcp_service._compile(
            "some/terraform/dir", None, "default", "", "", "", False, False
        )
        # Without the fix this is `strand`, and the renderer would write
        # the diagram there instead of into the output directory.
        assert Path.cwd() == outdir


def test_cwd_restored_even_when_pipeline_raises(tmp_path, monkeypatch):
    import modules.mcp_service as mcp_service
    import terravision.terravision as tv

    strand = tmp_path / "elsewhere"
    strand.mkdir()
    outdir = set_output_dir(str(tmp_path / "generated"))
    monkeypatch.setattr(mcp_service, "_check_binaries", lambda: None)
    monkeypatch.setattr(tv, "preflight_check", lambda *a, **k: None)

    def failing_compile(*args, **kwargs):
        os.chdir(strand)
        raise TerravisionError("plan failed")

    monkeypatch.setattr(tv, "compile_tfdata", failing_compile)

    with _guarded():
        with pytest.raises(TerravisionError):
            mcp_service._compile(
                "some/terraform/dir", None, "default", "", "", "", False, False
            )
        assert Path.cwd() == outdir


def test_outer_cwd_still_restored_after_a_stranding_call(tmp_path, monkeypatch):
    """The process must not be left inside the output dir either."""
    import modules.mcp_service as mcp_service

    strand = tmp_path / "elsewhere"
    strand.mkdir()
    set_output_dir(str(tmp_path / "generated"))
    _stub_pipeline(monkeypatch, strand)
    monkeypatch.setattr(mcp_service, "_check_binaries", lambda: None)

    before = Path.cwd()
    with _guarded():
        mcp_service._compile(
            "some/terraform/dir", None, "default", "", "", "", False, False
        )
    assert Path.cwd() == before


# ── External dependency checks ────────────────────────────────────────
#
# helpers.check_dependencies() calls exit(1) when a binary is missing, which
# _guarded can only report as a generic abort that blames the Terraform plan.
# An MCP server is especially prone to this: it is spawned by a client and
# inherits that client's environment, so a client started before PATH last
# changed hands down a stale copy.


def test_missing_binaries_reported_with_names(monkeypatch):
    import modules.mcp_service as mcp_service

    monkeypatch.setattr(mcp_service, "_missing_binaries", lambda: ["dot", "terraform"])
    with pytest.raises(McpServiceError) as excinfo:
        mcp_service._check_binaries()

    message = str(excinfo.value)
    assert "dot" in message and "terraform" in message
    assert "stale" in message.lower()


def test_binary_check_passes_when_all_present(monkeypatch):
    import modules.mcp_service as mcp_service

    monkeypatch.setattr(mcp_service, "_missing_binaries", lambda: [])
    mcp_service._check_binaries()  # must not raise


def test_missing_binaries_deduplicates(monkeypatch):
    import modules.mcp_service as mcp_service

    monkeypatch.setattr(
        mcp_service, "_missing_binaries", lambda: ["dot", "dot", "gvpr"]
    )
    with pytest.raises(McpServiceError) as excinfo:
        mcp_service._check_binaries()
    assert str(excinfo.value).count("dot") == 1


def test_missing_binaries_uses_the_shared_dependency_table(monkeypatch):
    """The list must track helpers.DEPENDENCIES, not a private copy."""
    import modules.mcp_service as mcp_service

    monkeypatch.setattr("shutil.which", lambda exe: None)
    missing = mcp_service._missing_binaries()
    assert {"dot", "gvpr", "git"} <= set(missing)


def test_binary_failure_is_not_reported_as_a_plan_failure(monkeypatch):
    """Regression: the generic abort text misattributed a PATH problem."""
    import modules.mcp_service as mcp_service

    monkeypatch.setattr(mcp_service, "_missing_binaries", lambda: ["dot"])
    with pytest.raises(McpServiceError) as excinfo:
        mcp_service._check_binaries()
    assert "could not produce a plan" not in str(excinfo.value)


# ── Argument validation happens before any pipeline work ──────────────


def test_run_diagram_rejects_unknown_format_without_running_pipeline():
    """Bad arguments must fail fast, not after a multi-minute plan."""
    with pytest.raises(McpServiceError) as excinfo:
        run_diagram("/nonexistent/source", format="notaformat")
    assert "Unsupported format" in str(excinfo.value)


def test_run_diagram_rejects_outfile_path_without_running_pipeline():
    with pytest.raises(McpServiceError):
        run_diagram("/nonexistent/source", format="png", outfile="../escape")
