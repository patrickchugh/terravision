"""Service layer backing the TerraVision MCP server.

This module adapts TerraVision's CLI pipeline for use inside a long-lived
server process. It deliberately contains no MCP protocol code and does not
import the ``mcp`` package, so it remains importable and testable on a
default install without the optional ``[mcp]`` extra.

Three concerns are handled here that the CLI never has to worry about,
because the CLI runs one command per process and then exits:

1. **stdout isolation.** The pipeline writes progress messages to stdout via
   ``click.echo``. Under the MCP stdio transport stdout carries the JSON-RPC
   stream, so a single stray byte corrupts the session. Every pipeline call
   is run with stdout redirected to stderr.
2. **Exit containment.** Several pipeline paths call ``sys.exit()`` on user
   error (a plan with no resources, an unsupported output format, a Graphviz
   failure). In a server that would terminate the process, so ``SystemExit``
   is caught and converted into :class:`McpServiceError`.
3. **Global state.** ``drawing`` and ``helpers`` hold module-level rendering
   options, and ``resource_classes`` holds a diagram contextvar. The CLI sets
   them once per process; a server must restore them after every call or
   options leak between requests.

Because output paths are resolved relative to the process working directory,
and because the guards above mutate module-level state, all pipeline work is
serialised under a single lock. Concurrency is not useful here anyway --- the
dominant cost is ``terraform plan``, which is itself a subprocess.
"""

import contextlib
import os
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterator, List, Optional, Sequence, Tuple

# Serialises all pipeline execution. See module docstring.
_PIPELINE_LOCK = threading.Lock()

# Directory that generated files are written to. Configured once at server
# startup by the ``terravision mcp`` command; defaults to the process CWD.
_OUTPUT_DIR: Optional[Path] = None

# Formats accepted by ``generate_diagram``. Read from Canvas so this stays in
# sync with the renderer instead of duplicating the list. ``drawio`` is
# handled outside Graphviz and so is not part of that tuple.
_EXTRA_FORMATS = ("drawio",)


class McpServiceError(Exception):
    """A pipeline failure that should be reported to the calling agent.

    Raised in place of ``SystemExit`` and ``TerravisionError`` so that a bad
    request fails one tool call rather than the whole server.
    """


def set_output_dir(path: Optional[str]) -> Path:
    """Set the directory generated files are written to.

    Args:
        path: Target directory, or None to use the current working directory.

    Returns:
        The resolved output directory.

    Raises:
        McpServiceError: If the path exists but is not a directory.
    """
    global _OUTPUT_DIR
    resolved = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise McpServiceError(f"Output path is not a directory: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    _OUTPUT_DIR = resolved
    return resolved


def get_output_dir() -> Path:
    """Return the configured output directory, defaulting to the CWD."""
    return _OUTPUT_DIR if _OUTPUT_DIR is not None else Path.cwd().resolve()


def supported_formats() -> Tuple[str, ...]:
    """Return the output formats ``generate_diagram`` accepts.

    Sourced from ``Canvas`` so the list cannot drift from what the renderer
    actually supports, plus the specially-handled ``drawio``.
    """
    from resource_classes import Canvas

    graphviz_formats = getattr(Canvas, "_Canvas__outformats", ())
    return tuple(sorted(set(graphviz_formats) | set(_EXTRA_FORMATS)))


def _validate_outfile(outfile: str) -> str:
    """Validate that ``outfile`` is a bare filename, not a path.

    Generated files always land in the configured output directory. Rejecting
    separators and parent references keeps an agent-supplied name from writing
    outside it. Mirrors the CLI, where ``--outfile`` is also a bare name.

    Args:
        outfile: Requested output filename, without extension.

    Returns:
        The validated filename.

    Raises:
        McpServiceError: If the name is empty or contains path components.
    """
    name = (outfile or "").strip()
    if not name:
        raise McpServiceError("outfile must not be empty")
    # Both separators are rejected on every platform rather than deferring to
    # os.path.sep/altsep, which would let "sub\name" through on POSIX (altsep
    # is None there). Neither character is ever legitimate in a bare filename,
    # and an agent should get the same answer regardless of the host OS.
    if "/" in name or "\\" in name:
        raise McpServiceError(
            f"outfile must be a filename, not a path: {outfile!r}. "
            "Output location is set by the server's --output-dir."
        )
    if name in (".", "..") or name.startswith(".."):
        raise McpServiceError(f"Invalid outfile name: {outfile!r}")
    return name


@contextlib.contextmanager
def _restored_globals() -> Iterator[None]:
    """Save and restore pipeline module-level state around a call.

    Covers ``drawing.DIAGRAM_FONTSIZE`` / ``DIAGRAM_ICONSIZE``,
    ``helpers.USE_TF_NAMES`` / ``USE_RESOURCE_NAMES`` /
    ``_RESOURCE_ORIGINAL_META``, and the ``resource_classes`` diagram
    contextvar. Without this, options set by one request leak into the next.
    """
    import modules.drawing as drawing
    import modules.helpers as helpers
    from resource_classes import setdiagram

    saved = (
        drawing.DIAGRAM_FONTSIZE,
        drawing.DIAGRAM_ICONSIZE,
        helpers.USE_TF_NAMES,
        helpers.USE_RESOURCE_NAMES,
        helpers._RESOURCE_ORIGINAL_META,
    )
    try:
        yield
    finally:
        (
            drawing.DIAGRAM_FONTSIZE,
            drawing.DIAGRAM_ICONSIZE,
            helpers.USE_TF_NAMES,
            helpers.USE_RESOURCE_NAMES,
            helpers._RESOURCE_ORIGINAL_META,
        ) = saved
        setdiagram(None)


@contextlib.contextmanager
def _in_output_dir() -> Iterator[Path]:
    """Run with the process CWD set to the configured output directory.

    The renderers resolve their output paths against ``Path.cwd()``, so this
    is how generated files are placed. Safe only because ``_guarded`` holds
    the pipeline lock for the duration.
    """
    target = get_output_dir()
    target.mkdir(parents=True, exist_ok=True)
    previous = Path.cwd()
    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(previous)


class _Tee:
    """Write to a real stream while keeping the last lines for diagnostics.

    Pipeline failures report themselves by printing and then calling
    ``exit()``. Under MCP that explanation goes to the server log and is
    invisible to the agent, which is left with a generic abort and no way to
    act on it short of re-running Terraform by hand. Retaining a bounded tail
    lets the actual cause travel back in the tool error.
    """

    def __init__(self, stream: Any, keep: int = 400) -> None:
        self._stream = stream
        self._lines: Deque[str] = deque(maxlen=keep)
        self._partial = ""

    def write(self, text: str) -> int:
        self._stream.write(text)
        self._partial += text
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            self._lines.append(line)
        return len(text)

    def flush(self) -> None:
        self._stream.flush()

    def tail(self, count: int = 12) -> str:
        """Return the last meaningful lines, ANSI colour codes removed."""
        import re

        lines = list(self._lines)
        if self._partial.strip():
            lines.append(self._partial)
        cleaned = [re.sub(r"\x1b\[[0-9;]*m", "", ln).rstrip() for ln in lines]
        return "\n".join([ln for ln in cleaned if ln.strip()][-count:])


@contextlib.contextmanager
def _guarded(change_dir: bool = True) -> Iterator[Optional[Path]]:
    """Run a pipeline call with all server-safety guards applied.

    Serialises execution, redirects stdout to stderr, optionally moves into
    the output directory, restores global state, and converts pipeline exits
    and errors into :class:`McpServiceError`.

    Args:
        change_dir: Whether to run inside the output directory. False for
            read-only calls that produce no files.

    Yields:
        The output directory when ``change_dir`` is set, otherwise None.

    Raises:
        McpServiceError: For any pipeline failure, including ``SystemExit``.
    """
    from modules.helpers import TerravisionError

    with _PIPELINE_LOCK:
        with contextlib.ExitStack() as stack:
            tee = _Tee(sys.stderr)
            stack.enter_context(contextlib.redirect_stdout(tee))
            stack.enter_context(_restored_globals())
            outdir = stack.enter_context(_in_output_dir()) if change_dir else None
            try:
                yield outdir
            except McpServiceError:
                raise
            except TerravisionError as e:
                raise McpServiceError(str(e)) from e
            except SystemExit as e:
                # The pipeline explains itself by printing and then calling
                # exit(). Replaying the tail is what turns "aborted" into
                # something the caller can act on -- a missing AWS credential
                # or an unparseable module, rather than a bare exit code.
                detail = tee.tail()
                raise McpServiceError(
                    "TerraVision could not process this source "
                    f"(exit code {e.code}).\n"
                    + (
                        f"Last output before it stopped:\n{detail}"
                        if detail
                        else "No further detail was produced."
                    )
                ) from e
            except Exception as e:
                raise McpServiceError(f"{type(e).__name__}: {e}") from e


def _missing_binaries() -> List[str]:
    """Return the required external executables that are not on PATH.

    Reuses the CLI's own dependency table so the two cannot disagree.
    """
    import shutil

    from modules.helpers import DEPENDENCIES, get_tf_binary

    missing = []
    for info in DEPENDENCIES.values():
        for exe in info["executables"] or [get_tf_binary()]:
            if not shutil.which(exe):
                missing.append(exe)
    return missing


def _check_binaries() -> None:
    """Fail with an actionable message when an external dependency is absent.

    ``helpers.check_dependencies()`` calls ``exit(1)`` in this situation, which
    :func:`_guarded` can only report as a generic abort --- and it would blame
    the Terraform plan for what is really a PATH problem. Checking first lets
    the agent be told what is actually wrong.

    A missing binary is disproportionately likely here: MCP servers are spawned
    as child processes and inherit the client's environment, so a client
    launched before PATH was last changed passes a stale copy down.

    Raises:
        McpServiceError: If any required executable is missing.
    """
    missing = _missing_binaries()
    if not missing:
        return
    raise McpServiceError(
        "TerraVision cannot run: "
        + ", ".join(sorted(set(missing)))
        + " not found on PATH. TerraVision needs Graphviz, Git and "
        "Terraform (or OpenTofu).\n"
        "If these are installed, the MCP server has inherited a stale "
        "environment from the client that launched it --- restart that "
        "client so it picks up the current PATH.\n"
        "Installation: https://patrickchugh.github.io/terravision/installation/"
    )


def _compile(
    source: str,
    varfile: Optional[Sequence[str]],
    workspace: str,
    annotate: str,
    planfile: str,
    graphfile: str,
    upgrade: bool,
    simplified: bool,
) -> Dict[str, Any]:
    """Run preflight plus the full parse/enrich pipeline.

    Reuses the CLI's own entry points so behaviour cannot drift. Must be
    called inside :func:`_guarded`.
    """
    import modules.graphmaker as graphmaker
    from terravision.terravision import compile_tfdata, preflight_check

    _check_binaries()
    intended_cwd = Path.cwd()
    try:
        # AI annotation is not exposed over MCP, so no backend is requested.
        preflight_check(None)
        tfdata = compile_tfdata(
            source,
            list(varfile or []),
            workspace,
            False,  # debug: never write replay files from a server
            annotate,
            planfile,
            graphfile,
            upgrade,
        )
    finally:
        # For a real Terraform source, tfwrapper.tf_initplan() ends with
        # os.chdir(START_DIR) -- and START_DIR is captured at import time
        # (tfwrapper.py:25), so it points at wherever the server process was
        # launched, not the output directory _in_output_dir() entered. That
        # is correct for the CLI, where output belongs beside the command
        # that produced it, but it silently strands the working directory
        # here and would drop generated files next to the server instead of
        # in --output-dir. A .json replay source never reaches tfwrapper,
        # which is why only real sources are affected.
        if Path.cwd() != intended_cwd:
            os.chdir(intended_cwd)

    if simplified:
        graphmaker.simplify_graphdict(tfdata)
    return tfdata


def _provider_of(tfdata: Dict[str, Any]) -> str:
    """Return the primary cloud provider detected for this source."""
    from modules.provider_detector import get_primary_provider_or_default

    return get_primary_provider_or_default(tfdata)


def _provider_suffixed(outfile: str, tfdata: Dict[str, Any]) -> str:
    """Append the provider suffix exactly as ``draw`` and ``visualise`` do.

    Deliberately mirrors the CLI branch rather than using
    :func:`_provider_of`: the commands suffix *only* when ``provider_detection``
    is present, and read ``primary_provider`` straight out of it. The two
    differ on a replayed ``tfdata.json`` that carries no detection block, where
    the CLI leaves the filename alone but ``get_primary_provider_or_default``
    would still answer ``aws``. Keeping the logic identical is what makes MCP
    output paths match the equivalent command.
    """
    detection = tfdata.get("provider_detection")
    if not detection:
        return outfile
    provider = detection.get("primary_provider", "aws")
    return outfile if outfile.endswith(f"-{provider}") else f"{outfile}-{provider}"


def run_architecture_graph(
    source: str,
    varfile: Optional[Sequence[str]] = None,
    workspace: str = "default",
    annotate: str = "",
    planfile: str = "",
    graphfile: str = "",
    upgrade: bool = False,
    simplified: bool = False,
    services_only: bool = False,
) -> Dict[str, Any]:
    """Build the architecture graph for a Terraform source.

    Equivalent to ``terravision graphdata``.

    Returns:
        With ``services_only``, ``{"services", "count", "provider"}``.
        Otherwise ``{"graphdict", "node_count", "edge_count", "provider"}``.
    """
    from modules.helpers import unique_services

    with _guarded(change_dir=False):
        tfdata = _compile(
            source,
            varfile,
            workspace,
            annotate,
            planfile,
            graphfile,
            upgrade,
            simplified,
        )
        graphdict = tfdata.get("graphdict", {})
        provider = _provider_of(tfdata)

        if services_only:
            services = unique_services(list(graphdict.keys()))
            return {
                "services": services,
                "count": len(services),
                "provider": provider,
            }

        return {
            "graphdict": graphdict,
            "node_count": len(graphdict),
            "edge_count": sum(len(v) for v in graphdict.values()),
            "provider": provider,
        }


def run_diagram(
    source: str,
    varfile: Optional[Sequence[str]] = None,
    workspace: str = "default",
    annotate: str = "",
    planfile: str = "",
    graphfile: str = "",
    upgrade: bool = False,
    simplified: bool = False,
    format: str = "png",
    outfile: str = "architecture",
    use_tf_names: bool = False,
    use_resource_names: bool = False,
    fontsize: Optional[int] = None,
    iconsize: Optional[int] = None,
) -> Dict[str, Any]:
    """Render an architecture diagram to a file.

    Equivalent to ``terravision draw``. Returns the path to the generated
    file rather than its contents; read the file to inspect text formats such
    as ``drawio``, ``svg`` or ``dot``.

    Returns:
        ``{"path", "format", "provider"}``.
    """
    import modules.drawing as drawing
    import modules.helpers as helpers

    fmt = (format or "png").strip().lower()
    allowed = supported_formats()
    if fmt not in allowed:
        raise McpServiceError(
            f"Unsupported format {format!r}. Supported: {', '.join(allowed)}"
        )
    name = _validate_outfile(outfile)

    with _guarded() as outdir:
        tfdata = _compile(
            source,
            varfile,
            workspace,
            annotate,
            planfile,
            graphfile,
            upgrade,
            simplified,
        )
        provider = _provider_of(tfdata)

        helpers.USE_TF_NAMES = use_tf_names
        helpers.USE_RESOURCE_NAMES = use_resource_names
        helpers._RESOURCE_ORIGINAL_META = tfdata.get("original_metadata")
        drawing.DIAGRAM_FONTSIZE = fontsize
        drawing.DIAGRAM_ICONSIZE = iconsize

        final_name = _provider_suffixed(name, tfdata)
        drawing.render_diagram(tfdata, False, final_name, fmt, source)

        # render_diagram writes the file but does not return its path, so it
        # is reconstructed from the documented naming scheme and then checked
        # rather than trusted.
        if fmt == "drawio":
            produced = outdir / f"{final_name}.drawio"
        else:
            produced = outdir / f"{final_name}.dot.{fmt}"
        if not produced.exists():
            raise McpServiceError(
                f"Diagram generation reported success but {produced.name} was "
                "not found. See the server log on stderr."
            )

        return {"path": str(produced), "format": fmt, "provider": provider}


def run_interactive_html(
    source: str,
    varfile: Optional[Sequence[str]] = None,
    workspace: str = "default",
    annotate: str = "",
    planfile: str = "",
    graphfile: str = "",
    upgrade: bool = False,
    simplified: bool = False,
    outfile: str = "architecture",
    use_tf_names: bool = False,
    use_resource_names: bool = False,
    fontsize: Optional[int] = None,
    iconsize: Optional[int] = None,
) -> Dict[str, Any]:
    """Render a self-contained interactive HTML diagram.

    Equivalent to ``terravision visualise``. The output embeds the diagram,
    resource metadata and its own JavaScript, so it opens offline.

    Returns:
        ``{"path", "provider"}``.
    """
    import modules.drawing as drawing
    import modules.helpers as helpers
    import modules.html_renderer as html_renderer

    name = _validate_outfile(outfile)

    with _guarded() as outdir:
        tfdata = _compile(
            source,
            varfile,
            workspace,
            annotate,
            planfile,
            graphfile,
            upgrade,
            simplified,
        )
        provider = _provider_of(tfdata)

        helpers.USE_TF_NAMES = use_tf_names
        helpers.USE_RESOURCE_NAMES = use_resource_names
        helpers._RESOURCE_ORIGINAL_META = tfdata.get("original_metadata")
        drawing.DIAGRAM_FONTSIZE = fontsize
        drawing.DIAGRAM_ICONSIZE = iconsize

        final_name = _provider_suffixed(name, tfdata)
        html_renderer.render_html(tfdata, False, final_name, source)

        produced = outdir / f"{final_name}.html"
        if not produced.exists():
            raise McpServiceError(
                f"HTML generation reported success but {produced.name} was "
                "not found. See the server log on stderr."
            )

        return {"path": str(produced), "provider": provider}
