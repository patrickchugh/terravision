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
import re
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterator, List, Optional, Sequence, Set, Tuple

# Node address rule for graphs passed to render_graph. Keep identical to the
# pattern in docs/schemas/terravision-graph-1.0.schema.json and the skill's
# scripts/validate_graph.py; tests/test_mcp_service.py compares all three.
_NODE_ADDRESS = re.compile(
    r"^(module\.[A-Za-z0-9_-]+(\[[^\]]+\])?\.)*[a-z][a-z0-9_]*\.[A-Za-z0-9_-]+(\[[^\]]+\])*(~[0-9]+)?$"
)

# Serialises all pipeline execution. See module docstring.
_PIPELINE_LOCK = threading.Lock()

# Directory that generated files are written to. Configured once at server
# startup by the ``terravision mcp`` command; defaults to the process CWD.
_OUTPUT_DIR: Optional[Path] = None

# Formats every diagram call writes, whatever format was asked for: a PNG to
# look at, an SVG to embed and a draw.io file to edit.
_DIAGRAM_SET = ("png", "svg", "drawio")

# Files rendered by this server process. The diagram view's helper tools only
# read or open paths in this set, so neither an agent nor a view can reach any
# other file on the machine.
_RENDERED: Set[Path] = set()

# Heading drawing.render_diagram uses when no title is set.
_DEFAULT_TITLE = "Cloud Architecture Diagram"

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


def _missing_binaries(needs_terraform: bool = True) -> List[str]:
    """Return the required external executables that are not on PATH.

    Reuses the CLI's own dependency table so the two cannot disagree. A graph
    JSON source never runs Terraform, so it is not required in that case.
    """
    import shutil

    from modules.helpers import DEPENDENCIES, get_tf_binary

    missing = []
    for key, info in DEPENDENCIES.items():
        if key == "terraform" and not needs_terraform:
            continue
        for exe in info["executables"] or [get_tf_binary()]:
            if not shutil.which(exe):
                missing.append(exe)
    return missing


def _check_binaries(needs_terraform: bool = True) -> None:
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
    from modules.helpers import (
        DEPENDENCIES,
        _get_os_family,
        add_graphviz_to_path,
        get_tf_binary,
        neato_engine_error,
    )

    add_graphviz_to_path()
    missing = _missing_binaries(needs_terraform)
    if not missing:
        engine_error = neato_engine_error()
        if engine_error:
            raise McpServiceError(
                f"TerraVision cannot run: Graphviz cannot run its neato layout "
                f"engine ({engine_error}). On Ubuntu 26.04+ and Debian testing it "
                "is a separate package: sudo apt install libgvplugin-neato-layout8"
            )
        return
    # The same per-OS install commands the CLI prints, so a chat app can show
    # the user exactly what to run.
    os_family = _get_os_family()
    commands = [
        line
        for info in DEPENDENCIES.values()
        if set(info["executables"] or [get_tf_binary()]) & set(missing)
        for line in info["install"].get(os_family, info["install"]["default"])
    ]
    needed = (
        "Graphviz and Git"
        if not needs_terraform
        else ("Graphviz, Git and Terraform (or OpenTofu)")
    )
    raise McpServiceError(
        "TerraVision cannot run: "
        + ", ".join(sorted(set(missing)))
        + f" not found on PATH. TerraVision needs {needed}.\n"
        "If these are installed, the MCP server has inherited a stale "
        "environment from the client that launched it --- restart that "
        "client so it picks up the current PATH.\n"
        + ("To install:\n  " + "\n  ".join(commands) + "\n" if commands else "")
        + "Installation: https://patrickchugh.github.io/terravision/installation/"
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

    from modules.helpers import is_graph_json_source

    needs_terraform = not is_graph_json_source(source)
    _check_binaries(needs_terraform)
    intended_cwd = Path.cwd()
    try:
        # AI annotation is not exposed over MCP, so no backend is requested.
        preflight_check(None, needs_terraform=needs_terraform)
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


def _output_file(outdir: Path, name: str, fmt: str) -> Path:
    """Return the path render_diagram writes for ``fmt``.

    render_diagram does not return its path, so it is reconstructed from the
    CLI's naming scheme and checked by the caller rather than trusted.
    """
    return outdir / (f"{name}.drawio" if fmt == "drawio" else f"{name}.dot.{fmt}")


def _render_set(
    tfdata: Dict[str, Any], name: str, requested: str, source: str, outdir: Path
) -> Dict[str, Path]:
    """Render the requested format plus the standard set from one compile.

    render_diagram stores drawing state such as Node objects in tfdata, so
    each format is drawn from a fresh copy of the compiled data. That keeps
    the pipeline, and any ``terraform plan``, to a single run.
    """
    import copy

    import modules.drawing as drawing

    files: Dict[str, Path] = {}
    for fmt in dict.fromkeys((requested, *_DIAGRAM_SET)):
        drawing.render_diagram(copy.deepcopy(tfdata), False, name, fmt, source)
        produced = _output_file(outdir, name, fmt)
        if not produced.exists():
            raise McpServiceError(
                f"Diagram generation reported success but {produced.name} was "
                "not found. See the server log on stderr."
            )
        _RENDERED.add(produced.resolve())
        files[fmt] = produced
    return files


def _write_graph(tfdata: Dict[str, Any], outdir: Path, name: str, source: str) -> Path:
    """Save the compiled graph as ``<name>.tvg.json`` beside the diagram.

    Gives every diagram, including one drawn from Terraform, a graph file the
    user can edit and render again. A graph file that is itself the source is
    left untouched.
    """
    import json

    target = outdir / f"{name}.tvg.json"
    src = Path(source)
    if not (src.is_file() and src.resolve() == target.resolve()):
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(tfdata.get("graphdict", {}), fh, indent=2, sort_keys=True)
    _RENDERED.add(target.resolve())
    return target


def _check_flows(flows: Any) -> None:
    """Raise McpServiceError for malformed flows, before anything is written."""
    import modules.annotations as annotations
    from modules.helpers import TerravisionError

    try:
        annotations.check_flows(flows)
    except TerravisionError as e:
        raise McpServiceError(str(e)) from e


# Put in a result without flows: the model reads tool results far more
# reliably than its instructions at the moment it writes the reply.
def _offer_flows(has_labels: bool) -> str:
    extras = "" if has_labels else ", and short labels on the connections"
    again = "flows" if has_labels else "flows and edge_labels"
    return (
        "Present the diagram, explaining how requests or data move through it. "
        "Then end your reply with one line offering to add that flow to the "
        f"diagram as numbered steps with a legend{extras}. On a yes, render the "
        f"same graph again with {again}. Do not add them before the user says "
        "yes."
    )


def _check_edge_labels(edge_labels: Any) -> Dict[str, List[Dict[str, str]]]:
    """Convert edge_labels to the connect format, or raise McpServiceError."""
    import modules.annotations as annotations
    from modules.helpers import TerravisionError

    try:
        return annotations.edge_labels_to_connect(edge_labels)
    except TerravisionError as e:
        raise McpServiceError(str(e)) from e


def _write_annotations(tfdata: Dict[str, Any], outdir: Path, name: str) -> Path:
    """Save the title, flows and edge labels as ``<name>.annotations.yml``.

    ``terravision draw --source <name>.tvg.json --annotate <this file>``
    then draws the same diagram, badges and legend included.
    """
    import yaml

    from modules.annotations import GRAPH_ANNOTATION_KEYS

    kept = {
        k: v
        for k, v in (tfdata.get("annotations") or {}).items()
        if k in GRAPH_ANNOTATION_KEYS and k != "format"
    }
    target = outdir / f"{name}.annotations.yml"
    with open(target, "w", encoding="utf-8") as fh:
        yaml.safe_dump(
            {"format": "0.3", **kept}, fh, sort_keys=False, allow_unicode=True
        )
    _RENDERED.add(target.resolve())
    return target


def _preview_png(
    path: Path, max_edge: int = 1568, max_bytes: int = 1_000_000
) -> Optional[bytes]:
    """Return a PNG small enough to send inline to a chat app, or None.

    Rendered diagrams are several thousand pixels on each side. 1568 pixels
    on the long edge is the largest size Claude models use without scaling
    down, and a typical diagram stays under 300 KB at that size. Very large
    diagrams fall back to a 256-colour palette, then to smaller sizes. The
    preview is best effort: without Pillow, or on any error, the call still
    succeeds and simply carries no image.
    """
    try:
        import io

        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            img.load()
            edge, palette = max_edge, False
            while True:
                small = img.copy()
                small.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                if palette:
                    small = small.convert("RGBA").quantize(
                        256, method=Image.Quantize.FASTOCTREE
                    )
                buf = io.BytesIO()
                small.save(buf, "PNG", optimize=True)
                data = buf.getvalue()
                if len(data) <= max_bytes or edge <= 512:
                    return data
                if palette:
                    edge = int(edge * 0.75)
                palette = True
    except Exception as e:  # noqa: BLE001 - a preview must never fail a render
        print(f"TerraVision: no preview for {path.name}: {e}", file=sys.stderr)
        return None


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
    title: Optional[str] = None,
    preview: bool = True,
    flows: Optional[Dict[str, Any]] = None,
    edge_labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Render an architecture diagram to files.

    Equivalent to ``terravision draw``, but always writes the full set: the
    requested format plus a PNG, an SVG, a draw.io file and the graph as
    ``.tvg.json``, so the result can be viewed, embedded and edited straight
    away. Returns paths rather than contents.

    Returns:
        ``{"path", "format", "provider", "title", "files"}``, where ``path``
        is the file in the requested format and ``files`` maps ``png``,
        ``svg``, ``drawio``, ``graph`` (and the requested format) to paths.
        With ``preview``, ``_preview_png`` holds a small PNG as bytes, or
        None; the MCP layer sends it inline and removes the key. With
        ``flows`` or ``edge_labels``, ``files`` also has ``annotations``,
        and ``warnings`` lists steps and labels that are not drawn.
    """
    import modules.annotations as annotations
    import modules.drawing as drawing
    import modules.helpers as helpers

    fmt = (format or "png").strip().lower()
    allowed = supported_formats()
    if fmt not in allowed:
        raise McpServiceError(
            f"Unsupported format {format!r}. Supported: {', '.join(allowed)}"
        )
    name = _validate_outfile(outfile)
    if flows:
        _check_flows(flows)
    connect = _check_edge_labels(edge_labels) if edge_labels else None

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
        if title:
            tfdata.setdefault("annotations", {})["title"] = title
        found: List[str] = []
        if flows:
            # The agent's flows replace any of the same name from a file.
            merged = {**(tfdata.get("annotations") or {}).get("flows", {}), **flows}
            tfdata.setdefault("annotations", {})["flows"] = merged
            found = annotations.flow_warnings(flows, tfdata.get("graphdict", {}))
        if connect:
            # The agent's labels win; they are also kept in the annotations
            # so the saved file draws them again.
            found += annotations.apply_edge_labels(tfdata, connect)
            saved = tfdata.setdefault("annotations", {}).setdefault("connect", {})
            for src, entries in connect.items():
                ours = {dst for entry in entries for dst in entry}
                kept = [
                    e
                    for e in saved.get(src, [])
                    if not (isinstance(e, dict) and set(e) & ours)
                ]
                saved[src] = entries + kept

        final_name = _provider_suffixed(name, tfdata)
        files = _render_set(tfdata, final_name, fmt, source, outdir)
        graph = _write_graph(tfdata, outdir, final_name, source)

        result: Dict[str, Any] = {
            "path": str(files[fmt]),
            "format": fmt,
            "provider": provider,
            "title": tfdata.get("annotations", {}).get("title") or _DEFAULT_TITLE,
            "files": {**{k: str(v) for k, v in files.items()}, "graph": str(graph)},
        }
        if flows or connect:
            result["files"]["annotations"] = str(
                _write_annotations(tfdata, outdir, final_name)
            )
        if found:
            result["warnings"] = found
        if not flows:
            result["next_step"] = _offer_flows(bool(connect))
        if preview:
            result["_preview_png"] = _preview_png(files["png"])
        return result


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
    title: Optional[str] = None,
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

    if helpers.is_graph_file_source(source):
        raise McpServiceError(helpers.VISUALISE_GRAPH_FILE_ERROR)
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
        if title:
            tfdata.setdefault("annotations", {})["title"] = title

        final_name = _provider_suffixed(name, tfdata)
        html_renderer.render_html(tfdata, False, final_name, source)

        produced = outdir / f"{final_name}.html"
        if not produced.exists():
            raise McpServiceError(
                f"HTML generation reported success but {produced.name} was "
                "not found. See the server log on stderr."
            )

        return {"path": str(produced), "provider": provider}


def run_render_graph(
    graph: Dict[str, List[str]],
    format: str = "png",
    outfile: str = "architecture",
    fontsize: Optional[int] = None,
    iconsize: Optional[int] = None,
    title: Optional[str] = None,
    preview: bool = True,
    flows: Optional[Dict[str, Any]] = None,
    edge_labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Render a diagram from an inline TerraVision graph dictionary.

    This is the renderer-only path: no Terraform, no cloud credentials, no
    files to stage. ``graph`` maps each node address (``<provider_type>.<name>``,
    e.g. ``aws_lambda_function.orders``) to the list of node addresses it
    connects to or contains. See the Graph Format reference for the rules.

    The graph is written to ``<outfile>.tvg.json`` in the output directory
    and then rendered exactly as ``terravision draw --source <that file>``
    would, so the CLI and MCP paths cannot drift.

    Returns:
        :func:`run_diagram`'s result plus ``graph_path``, ``node_count`` and
        ``edge_count``, and ``warnings`` when parts of the graph will not
        draw the way they read (see :func:`graph_warnings`), or flow steps
        and edge labels are not drawn.
    """
    import json

    if not isinstance(graph, dict) or not graph:
        raise McpServiceError(
            "graph must be a non-empty JSON object mapping node addresses to "
            "lists of connected node addresses."
        )
    for node, targets in graph.items():
        if not isinstance(node, str) or not _NODE_ADDRESS.match(node):
            raise McpServiceError(
                f"Invalid node address {node!r}: expected '<type>.<name>', "
                "e.g. 'aws_s3_bucket.assets'."
            )
        if not isinstance(targets, list) or not all(
            isinstance(t, str) for t in targets
        ):
            raise McpServiceError(
                f"Connections for {node!r} must be a list of node address strings."
            )
        for t in targets:
            if not _NODE_ADDRESS.match(t):
                raise McpServiceError(
                    f"Invalid connection {t!r} from {node!r}: expected "
                    "'<type>.<name>', e.g. 'aws_s3_bucket.assets'."
                )
    found = graph_warnings(graph)

    # Refuse a graph that mixes providers before writing anything, so a
    # rejected call leaves no file behind.
    from modules.helpers import TerravisionError
    from modules.tfwrapper import _check_single_provider

    try:
        _check_single_provider(graph)
    except TerravisionError as e:
        raise McpServiceError(str(e)) from e
    if flows:
        _check_flows(flows)
    if edge_labels:
        _check_edge_labels(edge_labels)

    # Any target that has no entry of its own is a leaf; add it so the caller
    # does not have to list every node twice. Copy first so the caller's dict
    # is left untouched.
    graph = {node: list(targets) for node, targets in graph.items()}
    for targets in list(graph.values()):
        for t in targets:
            graph.setdefault(t, [])

    name = _validate_outfile(outfile)
    outdir = get_output_dir()
    outdir.mkdir(parents=True, exist_ok=True)
    graph_path = outdir / f"{name}.tvg.json"
    with open(graph_path, "w", encoding="utf-8") as fh:
        json.dump(graph, fh, indent=2)

    result = run_diagram(
        source=str(graph_path),
        format=format,
        outfile=name,
        fontsize=fontsize,
        iconsize=iconsize,
        title=title,
        preview=preview,
        flows=flows,
        edge_labels=edge_labels,
    )
    result["graph_path"] = str(graph_path)
    found += result.pop("warnings", [])
    if found:
        result["warnings"] = found
    result["node_count"] = len(graph)
    result["edge_count"] = sum(len(v) for v in graph.values())
    return result


def _rendered_file(path: str) -> Path:
    """Resolve ``path`` and check this server rendered it.

    Raises:
        McpServiceError: For any path outside the files this process wrote.
    """
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        resolved = None
    if resolved is None or resolved not in _RENDERED or not resolved.is_file():
        raise McpServiceError(
            f"{path!r} is not a diagram file rendered by this TerraVision server."
        )
    return resolved


# Media types for the files a diagram call writes. Text formats are returned
# as text so the view can show and copy them without decoding.
_TEXT_MEDIA_TYPES = {
    ".svg": "image/svg+xml",
    ".drawio": "application/vnd.jgraph.mxfile",
    ".json": "application/json",
    ".dot": "text/vnd.graphviz",
    ".yml": "application/yaml",
}


def read_output_file(path: str) -> Dict[str, Any]:
    """Return the contents of a file this server rendered.

    Used by the diagram view to show the SVG at full resolution and to copy
    the graph JSON. Only files in the rendered set can be read.

    Returns:
        ``{"name", "mimeType", "text"}`` for text formats, otherwise
        ``{"name", "mimeType", "blob"}`` with base64 content.
    """
    import base64
    import mimetypes

    resolved = _rendered_file(path)
    media_type = _TEXT_MEDIA_TYPES.get(resolved.suffix.lower())
    if media_type:
        return {
            "name": resolved.name,
            "mimeType": media_type,
            "text": resolved.read_text(encoding="utf-8"),
        }
    return {
        "name": resolved.name,
        "mimeType": mimetypes.guess_type(resolved.name)[0]
        or "application/octet-stream",
        "blob": base64.b64encode(resolved.read_bytes()).decode("ascii"),
    }


# Where X11 display sockets live on Linux.
_X11_SOCKET_DIR = Path("/tmp/.X11-unix")


# Session variables xdg-open needs: where to display, how to reach the
# desktop's D-Bus, and which desktop it is, which decides the default apps.
_DESKTOP_VARS = (
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_TYPE",
    "XDG_DATA_DIRS",
    "DESKTOP_SESSION",
)


def _systemd_session_env(env: Dict[str, str]) -> Dict[str, str]:
    """The desktop session's variables as the systemd user manager holds them.

    GNOME, KDE and other systemd-based desktops register their session
    environment there, so it is available even to a process started with
    almost none. Returns an empty dict when systemd is not in use.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}
    found = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in _DESKTOP_VARS and not value.startswith("$'"):
            found[key] = value
    return found


def _linux_desktop_env() -> Optional[Dict[str, str]]:
    """Return an environment that can reach the user's desktop, or None.

    Desktop apps such as Claude Desktop start MCP servers with little more
    than HOME and PATH. Without DISPLAY or WAYLAND_DISPLAY xdg-open cannot
    show anything, and without XDG_CURRENT_DESKTOP it ignores the desktop's
    default apps (a PNG opened in a web browser instead of the image
    viewer). The session's own values are read from the systemd user
    manager; failing that, the display and D-Bus sockets are found in their
    standard places: the user's runtime directory (``/run/user/<uid>``) and
    ``/tmp/.X11-unix``. Variables already set are never replaced. Returns
    None when there is no desktop session at all, for example over SSH.
    """
    env = dict(os.environ)
    if (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")) and env.get(
        "XDG_CURRENT_DESKTOP"
    ):
        return env
    runtime = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    if runtime.is_dir():
        env.setdefault("XDG_RUNTIME_DIR", str(runtime))
        for key, value in _systemd_session_env(env).items():
            env.setdefault(key, value)
        bus = runtime / "bus"
        if bus.exists():
            env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={bus}")
        if not env.get("WAYLAND_DISPLAY"):
            wayland = sorted(
                p.name
                for p in runtime.glob("wayland-*")
                if not p.name.endswith(".lock")
            )
            if wayland:
                env["WAYLAND_DISPLAY"] = wayland[0]
    if not env.get("DISPLAY") and _X11_SOCKET_DIR.is_dir():
        displays = sorted(
            p.name[1:] for p in _X11_SOCKET_DIR.glob("X*") if p.name[1:].isdigit()
        )
        if displays:
            env["DISPLAY"] = f":{displays[0]}"
    return env if env.get("DISPLAY") or env.get("WAYLAND_DISPLAY") else None


def open_output_file(path: str, reveal: bool = False) -> Dict[str, Any]:
    """Open a rendered file in the user's default app, or show it in its folder.

    The server runs on the user's own machine, so this works in every chat
    app, including those whose sandbox blocks downloads. Only files in the
    rendered set can be opened.

    Raises:
        McpServiceError: For an unknown path, or when there is no desktop to
            open it on, for example a Linux server without a display.
    """
    import platform
    import subprocess

    import modules.helpers as helpers

    resolved = _rendered_file(path)
    target = str(resolved)
    system = platform.system()
    popen_kwargs: Dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if system == "Windows":
        if not reveal:
            os.startfile(target)  # type: ignore[attr-defined]  # Windows only
            return {"opened": target, "reveal": False}
        command = ["explorer", f"/select,{target}"]
    else:
        popen_kwargs["start_new_session"] = True
        if system == "Darwin":
            command = ["open", "-R", target] if reveal else ["open", target]
        elif helpers.is_wsl():
            command = ["wslview", str(resolved.parent) if reveal else target]
        else:
            desktop = _linux_desktop_env()
            if desktop is None:
                raise McpServiceError(
                    f"There is no desktop session here to open files in. "
                    f"The file is at {target}"
                )
            popen_kwargs["env"] = desktop
            command = ["xdg-open", str(resolved.parent) if reveal else target]
    try:
        subprocess.Popen(command, **popen_kwargs)
    except OSError as e:
        raise McpServiceError(f"Could not open {target}: {e}") from e
    return {"opened": target, "reveal": reveal}


# The agent skill's folder, installed alongside the package so the MCP server
# can give the same guidance to apps that have the server but not the skill.
_SKILL_DIR = (
    Path(__file__).resolve().parents[1] / "skills" / "terravision-cloud-diagrams"
)

# Worked example graphs for each provider, closest to common requests first.
_EXAMPLES = {
    "aws": ("three-tier-web", "aws-event-driven"),
    "azure": ("azure-three-tier", "azure-web-app"),
    "gcp": ("gcp-three-tier", "gcp-serverless-api"),
}

# Node address prefixes for each provider, including its tv_ pseudo-nodes.
_TYPE_PREFIXES = {
    "aws": ("aws_", "tv_aws_"),
    "azure": ("azurerm_", "tv_azurerm_", "tv_azure_"),
    "gcp": ("google_", "tv_gcp_"),
}


def diagram_guide(provider: str, pattern: Optional[str] = None) -> Dict[str, Any]:
    """Return what an agent needs to write a good graph for ``provider``.

    With ``pattern``, returns just that graph from the pattern library, built
    by scripts/gen_example_patterns.py from TerraVision's own output for real
    Terraform, so a diagram of a service mix the main examples do not cover
    keeps TerraVision's level of detail.

    The same material the agent skill gives Claude Code: the graph format
    rules (type picks, containers, what is drawn and what is not), worked
    example graphs and the node types this provider can use. The examples
    carry most of the value: they show availability zones, public and
    private subnets, NAT gateways routed to the internet and shared services
    the way a cloud architect draws them.

    Raises:
        McpServiceError: For an unknown provider, or when the skill files
            are missing from the installation.
    """
    import json

    key = (provider or "").strip().lower()
    if key not in _EXAMPLES:
        raise McpServiceError(
            f"Unknown provider {provider!r}. Use one of: aws, azure, gcp."
        )
    patterns_dir = _SKILL_DIR / "examples" / "patterns"
    try:
        catalogue = [
            entry
            for entry in json.loads((patterns_dir / "index.json").read_text())
            if entry["provider"] == key
        ]
    except OSError:
        catalogue = []
    if pattern:
        entry = next((e for e in catalogue if e["name"] == pattern), None)
        if entry is None:
            names = ", ".join(e["name"] for e in catalogue) or "none"
            raise McpServiceError(
                f"Unknown {key} pattern {pattern!r}. Available: {names}."
            )
        return {
            "provider": key,
            "pattern": pattern,
            "description": entry["description"],
            "graph": json.loads((patterns_dir / f"{pattern}.tvg.json").read_text()),
        }
    try:
        rules = (_SKILL_DIR / "references" / "graph-format.md").read_text()
        types_doc = (_SKILL_DIR / "references" / "node-types.md").read_text()
        examples = {
            name: json.loads((_SKILL_DIR / "examples" / f"{name}.tvg.json").read_text())
            for name in _EXAMPLES[key]
        }
    except OSError as e:
        raise McpServiceError(
            f"The TerraVision guide files are missing from this installation: {e}"
        ) from e
    node_types = sorted(
        t
        for t in re.findall(r"`([a-z][a-z0-9_]*)`", types_doc)
        if t.startswith(_TYPE_PREFIXES[key])
    )
    setup = setup_status()
    next_step = (
        "Start from the closest example, keep its structure (zones, public "
        "and private subnets, internet path, shared services), use the most "
        "specific node types, then call render_graph with a title. If a "
        "pattern below matches the services asked for, fetch it with "
        "diagram_guide(provider, pattern=<name>) and follow it too. "
        + _ZONE_HINTS[key]
        + " Before rendering, check the graph against the request: every "
        "service asked for is there with its specific type, each zone has its "
        "copies, and every node sits in the container you meant."
    )
    if not setup["ready_for_graphs"]:
        next_step = (
            "Graphviz or Git is missing, so diagrams cannot be drawn yet. Tell "
            "the user what to install (see setup.install) and to restart the "
            "app afterwards, before drafting the graph. " + next_step
        )
    return {
        "provider": key,
        "setup": setup,
        "rules": rules,
        "examples": examples,
        "node_types": node_types,
        "patterns": [
            {"name": e["name"], "description": e["description"]} for e in catalogue
        ],
        "next_step": next_step,
    }


# How each cloud draws resources that span availability zones, for next_step.
_ZONE_HINTS = {
    "aws": "AWS subnets are zonal: in a multi-AZ design, give every resource "
    "that spans zones (load balancer, NAT gateway, compute tier, Multi-AZ "
    "database) one numbered copy in each zone's subnet.",
    "azure": "Azure subnets span zones: draw zone-redundant services once in "
    "their subnet, and put per-zone instances in tv_azurerm_zone boxes inside "
    "it.",
    "gcp": "GCP subnets are regional: draw regional services (load balancers, "
    "managed instance groups, Cloud NAT) once, and put per-zone instances in "
    "tv_gcp_zone boxes inside the subnet.",
}


_VALIDATOR: Any = None


def graph_warnings(graph: Dict[str, List[str]]) -> List[str]:
    """Return the skill validator's warnings for a graph.

    Things that draw, but not as the graph reads: an unknown type (a blank
    icon, with the closest supported types suggested), arrows to containers
    or shared services that are not drawn, a node listed in two boxes. The
    validator ships with the skill in the package, so the MCP server and the
    skill's command-line check give the same advice. Best effort: returns an
    empty list if the validator cannot be loaded.
    """
    global _VALIDATOR
    if _VALIDATOR is None:
        import importlib.util

        path = _SKILL_DIR / "scripts" / "validate_graph.py"
        if not path.is_file():
            return []
        spec = importlib.util.spec_from_file_location(
            "terravision_validate_graph", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VALIDATOR = module
    try:
        return list(_VALIDATOR.warnings(graph))
    except Exception:  # noqa: BLE001 - advice must never fail a render
        return []


def setup_status() -> Dict[str, Any]:
    """Report whether the programs TerraVision needs are installed.

    Graphviz (dot, neato and gvpr, with neato's layout engine on Linux) and
    Git are needed for every diagram; Terraform or OpenTofu only for drawing
    from Terraform code. Uses the same checks as a diagram call, including
    finding Graphviz in its standard folders when it is not on PATH, so an
    agent can tell the user what to install before drafting anything.
    Installed extensions cannot check this themselves: Claude Desktop's
    "requirements met" only covers the operating system and Python.
    """
    import shutil

    from modules.helpers import (
        DEPENDENCIES,
        _get_os_family,
        add_graphviz_to_path,
        neato_engine_error,
    )

    add_graphviz_to_path()
    missing_graphviz = [e for e in ("dot", "neato", "gvpr") if not shutil.which(e)]
    engine_error = None if missing_graphviz else neato_engine_error()
    if missing_graphviz:
        graphviz = "missing: " + ", ".join(missing_graphviz)
    elif engine_error:
        graphviz = (
            f"neato layout engine missing ({engine_error}); on Ubuntu 26.04+ and "
            "Debian testing: sudo apt install libgvplugin-neato-layout8"
        )
    else:
        graphviz = "ok"
    git = "ok" if shutil.which("git") else "missing"
    engine = next((e for e in ("terraform", "tofu") if shutil.which(e)), None)
    terraform = (
        f"ok ({engine})"
        if engine
        else "not found: only needed for drawing from Terraform code"
    )

    os_family = _get_os_family()
    install = []
    for key, needed in (
        ("graphviz", graphviz != "ok" and not engine_error),
        ("git", git != "ok"),
        ("terraform", engine is None),
    ):
        if needed:
            hints = DEPENDENCIES[key]["install"]
            install += hints.get(os_family, hints["default"])
    status: Dict[str, Any] = {
        "graphviz": graphviz,
        "git": git,
        "terraform": terraform,
        "ready_for_graphs": graphviz == "ok" and git == "ok",
        "ready_for_terraform": graphviz == "ok" and git == "ok" and engine is not None,
    }
    if install:
        status["install"] = install
    return status
