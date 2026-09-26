"""Tests for v0.50's diagram results: the file set, the inline preview, the
helper tools that open and read rendered files, and the MCP Apps view.

Service-level tests need no ``mcp`` import; the protocol tests at the end are
skipped without the optional ``[mcp]`` extra.
"""

import base64
import io
import json
import os
import sys
from pathlib import Path

import pytest

from modules import mcp_service
from modules.mcp_service import McpServiceError

GRAPH = {
    "tv_aws_users.users": ["aws_cloudfront_distribution.cdn"],
    "aws_cloudfront_distribution.cdn": ["aws_alb.api"],
    "aws_vpc.main": ["aws_subnet.app"],
    "aws_subnet.app": ["aws_alb.api", "aws_ecs_fargate.api"],
    "aws_alb.api": ["aws_ecs_fargate.api"],
    "aws_ecs_fargate.api": ["aws_rds_sqlserver.db"],
}
REPLAY_SOURCE = str(Path(__file__).parent / "json" / "bastion-tfdata.json")


@pytest.fixture
def outdir(tmp_path):
    """Point the service at a fresh output folder and forget earlier renders."""
    saved_dir, saved_rendered = mcp_service._OUTPUT_DIR, set(mcp_service._RENDERED)
    mcp_service._RENDERED.clear()
    mcp_service.set_output_dir(str(tmp_path))
    yield tmp_path
    mcp_service._OUTPUT_DIR = saved_dir
    mcp_service._RENDERED.clear()
    mcp_service._RENDERED.update(saved_rendered)


@pytest.fixture
def rendered(outdir):
    return mcp_service.run_render_graph(GRAPH, outfile="demo", title="Demo")


# ── The file set ─────────────────────────────────────────────────────


def test_render_graph_writes_the_full_file_set(rendered, outdir):
    files = rendered["files"]
    assert set(files) == {"png", "svg", "drawio", "graph"}
    for path in files.values():
        assert Path(path).is_file()
        assert Path(path).parent == outdir
    assert rendered["path"] == files["png"]
    assert rendered["title"] == "Demo"
    assert files["graph"] == rendered["graph_path"]


def test_requested_format_is_added_to_the_set(outdir):
    result = mcp_service.run_render_graph(GRAPH, format="pdf", outfile="doc")
    assert result["path"].endswith("doc.dot.pdf")
    assert set(result["files"]) == {"pdf", "png", "svg", "drawio", "graph"}


def test_terraform_source_gets_an_editable_graph_file(outdir):
    result = mcp_service.run_diagram(REPLAY_SOURCE, outfile="bastion")
    graph_file = Path(result["files"]["graph"])
    assert graph_file.name == "bastion-aws.tvg.json"
    graph = json.loads(graph_file.read_text())
    assert graph and all(isinstance(v, list) for v in graph.values())


def test_default_title(outdir):
    result = mcp_service.run_render_graph(GRAPH, outfile="untitled")
    assert result["title"] == "Cloud Architecture Diagram"


# ── The inline preview ──────────────────────────────────────────────


def test_preview_is_a_small_png(rendered):
    from PIL import Image

    data = rendered["_preview_png"]
    assert data.startswith(b"\x89PNG")
    assert len(data) <= 1_000_000
    with Image.open(io.BytesIO(data)) as img:
        assert max(img.size) <= 1568


def test_preview_can_be_turned_off(outdir):
    result = mcp_service.run_render_graph(GRAPH, outfile="nopreview", preview=False)
    assert "_preview_png" not in result


def test_preview_shrinks_until_it_fits(tmp_path):
    from PIL import Image

    noisy = tmp_path / "noisy.png"
    Image.frombytes("RGB", (3000, 2000), os.urandom(3000 * 2000 * 3)).save(noisy)
    data = mcp_service._preview_png(noisy, max_bytes=200_000)
    with Image.open(io.BytesIO(data)) as img:
        assert len(data) <= 200_000 or max(img.size) <= 512


def test_preview_is_skipped_without_pillow(rendered, monkeypatch):
    monkeypatch.setitem(sys.modules, "PIL", None)
    assert mcp_service._preview_png(Path(rendered["files"]["png"])) is None


# ── Reading rendered files ──────────────────────────────────────────


def test_read_text_and_binary_files(rendered):
    files = rendered["files"]
    graph = mcp_service.read_output_file(files["graph"])
    assert graph["mimeType"] == "application/json"
    assert json.loads(graph["text"])
    assert "<mxfile" in mcp_service.read_output_file(files["drawio"])["text"]
    assert "<svg" in mcp_service.read_output_file(files["svg"])["text"]
    png = mcp_service.read_output_file(files["png"])
    assert png["mimeType"] == "image/png"
    assert base64.b64decode(png["blob"]).startswith(b"\x89PNG")


@pytest.mark.parametrize("attempt", ["outsider", "/etc/hostname", "../demo.dot.png"])
def test_only_rendered_files_can_be_read_or_opened(rendered, outdir, attempt):
    if attempt == "outsider":
        stray = outdir / "stray.png"
        stray.write_bytes(b"\x89PNG not ours")
        attempt = str(stray)
    with pytest.raises(McpServiceError, match="not a diagram file"):
        mcp_service.read_output_file(attempt)
    with pytest.raises(McpServiceError, match="not a diagram file"):
        mcp_service.open_output_file(attempt)


# ── Opening rendered files ──────────────────────────────────────────


_LAUNCH = {}


def launched_env():
    return _LAUNCH["env"]


@pytest.fixture
def launched(monkeypatch):
    """Capture the command open_output_file would run instead of running it."""
    import subprocess

    import modules.helpers as helpers

    calls = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        _LAUNCH["env"] = kwargs.get("env")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(helpers, "is_wsl", lambda: False)
    return calls


def _on(monkeypatch, system):
    import platform

    monkeypatch.setattr(platform, "system", lambda: system)


def test_open_on_linux_desktop(rendered, launched, monkeypatch):
    _on(monkeypatch, "Linux")
    monkeypatch.setenv("DISPLAY", ":0")
    png = rendered["files"]["png"]
    mcp_service.open_output_file(png)
    mcp_service.open_output_file(png, reveal=True)
    assert launched == [["xdg-open", png], ["xdg-open", str(Path(png).parent)]]


@pytest.fixture
def stripped_env(monkeypatch, tmp_path):
    """An environment like Claude Desktop gives MCP servers: no desktop vars."""
    for var in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
        monkeypatch.delenv(var, raising=False)
    runtime = tmp_path / "run-user"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr(mcp_service, "_X11_SOCKET_DIR", tmp_path / "no-x11")
    return runtime


def test_open_on_linux_without_a_desktop(rendered, launched, monkeypatch, stripped_env):
    _on(monkeypatch, "Linux")
    with pytest.raises(McpServiceError, match="no desktop session"):
        mcp_service.open_output_file(rendered["files"]["png"])
    assert launched == []


def test_open_recovers_the_desktop_session(
    rendered, launched, monkeypatch, stripped_env
):
    """Claude Desktop strips DISPLAY and friends; they are found again."""
    _on(monkeypatch, "Linux")
    for name in ("bus", "wayland-0", "wayland-0.lock"):
        (stripped_env / name).touch()
    x11 = stripped_env.parent / "x11"
    x11.mkdir()
    (x11 / "X1").touch()
    monkeypatch.setattr(mcp_service, "_X11_SOCKET_DIR", x11)
    png = rendered["files"]["png"]
    mcp_service.open_output_file(png)
    assert launched == [["xdg-open", png]]
    env = launched_env()
    assert env["WAYLAND_DISPLAY"] == "wayland-0"
    assert env["DISPLAY"] == ":1"
    assert env["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={stripped_env / 'bus'}"
    assert env["XDG_RUNTIME_DIR"] == str(stripped_env)


def test_open_on_macos(rendered, launched, monkeypatch):
    _on(monkeypatch, "Darwin")
    drawio = rendered["files"]["drawio"]
    mcp_service.open_output_file(drawio)
    mcp_service.open_output_file(drawio, reveal=True)
    assert launched == [["open", drawio], ["open", "-R", drawio]]


def test_open_on_windows(rendered, launched, monkeypatch):
    _on(monkeypatch, "Windows")
    started = []
    monkeypatch.setattr(os, "startfile", started.append, raising=False)
    png = rendered["files"]["png"]
    mcp_service.open_output_file(png)
    mcp_service.open_output_file(png, reveal=True)
    assert started == [png]
    assert launched == [["explorer", f"/select,{png}"]]


def test_open_on_wsl(rendered, launched, monkeypatch):
    import modules.helpers as helpers

    _on(monkeypatch, "Linux")
    monkeypatch.setattr(helpers, "is_wsl", lambda: True)
    png = rendered["files"]["png"]
    mcp_service.open_output_file(png)
    assert launched == [["wslview", png]]


def test_open_reports_a_missing_opener(rendered, monkeypatch):
    import subprocess

    _on(monkeypatch, "Darwin")

    def missing(cmd, **kw):
        raise FileNotFoundError("open")

    monkeypatch.setattr(subprocess, "Popen", missing)
    with pytest.raises(McpServiceError, match="Could not open"):
        mcp_service.open_output_file(rendered["files"]["png"])


# ── The view document ───────────────────────────────────────────────


def test_view_is_self_contained_and_escapes_content():
    from modules.mcp_view import VIEW_HTML

    assert "http://" not in VIEW_HTML and "https://" not in VIEW_HTML
    assert "innerHTML" not in VIEW_HTML
    for method in (
        "ui/initialize",
        "ui/notifications/initialized",
        "ui/notifications/tool-result",
        "ui/notifications/size-changed",
        "tools/call",
    ):
        assert method in VIEW_HTML
    assert '"2026-01-26"' in VIEW_HTML


# ── Over the protocol ───────────────────────────────────────────────


@pytest.fixture
def client_call():
    pytest.importorskip("mcp", reason="requires the optional [mcp] extra")
    import anyio
    from mcp import Client

    from modules.mcp_server import build_server

    server = build_server()

    def call(fn):
        async def go():
            async with Client(server) as client:
                return await fn(client)

        return anyio.run(go)

    return call


def test_diagram_result_carries_text_image_and_structured_data(outdir, client_call):
    result = client_call(
        lambda c: c.call_tool("render_graph", {"graph": GRAPH, "outfile": "proto"})
    )
    assert not result.is_error
    summary = json.loads(result.content[0].text)
    assert set(summary["files"]) == {"png", "svg", "drawio", "graph"}
    assert "_preview_png" not in summary
    image = result.content[1]
    assert image.type == "image" and image.mime_type == "image/png"
    assert base64.b64decode(image.data).startswith(b"\x89PNG")
    assert result.structured_content == summary


def test_diagram_tools_are_bound_to_the_view(client_call):
    from modules.mcp_view import VIEW_URI

    tools = {t.name: t for t in client_call(lambda c: c.list_tools()).tools}
    for name in ("render_graph", "generate_diagram"):
        assert tools[name].meta["ui"]["resourceUri"] == VIEW_URI
    assert tools["diagram_file"].meta["ui"]["visibility"] == ["app"]
    assert tools["open_diagram_file"].meta is None


def test_view_resource_is_served(client_call):
    from modules.mcp_view import VIEW_URI

    contents = client_call(lambda c: c.read_resource(VIEW_URI)).contents
    assert contents[0].mime_type == "text/html;profile=mcp-app"
    assert "ui/initialize" in contents[0].text
    assert "__VERSION__" not in contents[0].text


def test_diagram_file_result_is_wrapped_by_the_sdk(outdir, client_call):
    """The SDK wraps a dict result as {"result": ...}; the view unwraps it."""

    async def go(c):
        rendered = await c.call_tool("render_graph", {"graph": GRAPH, "outfile": "w"})
        graph = rendered.structured_content["files"]["graph"]
        return await c.call_tool("diagram_file", {"path": graph})

    result = client_call(go)
    assert json.loads(result.structured_content["result"]["text"])
    from modules.mcp_view import VIEW_HTML

    assert "data.result" in VIEW_HTML


def test_open_tool_refuses_unknown_files(outdir, client_call):
    result = client_call(
        lambda c: c.call_tool("open_diagram_file", {"path": "/etc/hostname"})
    )
    assert result.is_error
    assert "not a diagram file" in result.content[0].text


# ── The Claude Desktop extension (mcpb/) ────────────────────────────

MCPB = Path(__file__).resolve().parents[1] / "mcpb"


def test_extension_manifest_matches_the_server(client_call):
    manifest = json.loads((MCPB / "manifest.json").read_text())
    assert manifest["version"] == "__VERSION__"
    assert manifest["server"]["type"] == "uv"
    args = manifest["server"]["mcp_config"]["args"]
    assert args[args.index("--output-dir") + 1] == "${user_config.output_dir}"
    assert manifest["user_config"]["output_dir"]["type"] == "directory"
    listed = {t["name"] for t in manifest["tools"]}
    served = {t.name for t in client_call(lambda c: c.list_tools()).tools}
    # diagram_file only serves the view, so it is not advertised to users.
    assert listed == served - {"diagram_file"}


def test_extension_pins_the_release_and_runs_the_mcp_command():
    import tomllib

    project = tomllib.loads((MCPB / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == ["terravision[mcp]==__VERSION__"]
    assert (
        "default"
        not in json.loads((MCPB / "manifest.json").read_text())["user_config"][
            "output_dir"
        ]
    ), "hosts may not expand ${DOCUMENTS}; server.py picks the default"


def _entry():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mcpb_server", MCPB / "src" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--output-dir"],
        ["--output-dir", ""],
        ["--output-dir", "${user_config.output_dir}"],
        ["--output-dir", "${DOCUMENTS}/TerraVision"],
    ],
)
def test_extension_falls_back_to_documents(argv):
    entry = _entry()
    args = entry.server_args(argv)
    assert args[:2] == ["terravision", "mcp"]
    assert args[args.index("--output-dir") + 1] == str(entry.DEFAULT_OUTPUT_DIR)


def test_extension_keeps_a_chosen_folder():
    assert _entry().server_args(["--output-dir", "/home/me/diagrams"]) == [
        "terravision",
        "mcp",
        "--output-dir",
        "/home/me/diagrams",
    ]
