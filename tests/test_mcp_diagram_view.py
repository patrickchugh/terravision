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
    """An environment like Claude Desktop gives MCP servers: no desktop vars.

    The systemd user manager is stubbed out and holds nothing; tests that
    need a session put its variables in ``_SYSTEMD``.
    """
    for var in mcp_service._DESKTOP_VARS:
        monkeypatch.delenv(var, raising=False)
    runtime = tmp_path / "run-user"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr(mcp_service, "_X11_SOCKET_DIR", tmp_path / "no-x11")
    _SYSTEMD.clear()
    monkeypatch.setattr(mcp_service, "_systemd_session_env", lambda env: dict(_SYSTEMD))
    return runtime


_SYSTEMD = {}


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


def test_open_uses_the_systemd_session(rendered, launched, monkeypatch, stripped_env):
    """The session's own values win, so xdg-open picks the desktop's apps."""
    _on(monkeypatch, "Linux")
    _SYSTEMD.update(
        DISPLAY=":0",
        WAYLAND_DISPLAY="wayland-0",
        XDG_CURRENT_DESKTOP="ubuntu:GNOME",
        XDG_DATA_DIRS="/usr/share/ubuntu:/usr/share",
    )
    monkeypatch.setenv("XDG_DATA_DIRS", "/already/set")
    mcp_service.open_output_file(rendered["files"]["png"])
    env = launched_env()
    assert env["XDG_CURRENT_DESKTOP"] == "ubuntu:GNOME"
    assert env["DISPLAY"] == ":0"
    assert env["XDG_DATA_DIRS"] == "/already/set"


def test_systemd_session_env_parsing(monkeypatch):
    import subprocess

    output = (
        "HOME=/home/me\n"
        "DISPLAY=:0\n"
        "XDG_CURRENT_DESKTOP=ubuntu:GNOME\n"
        "DESKTOP_SESSION=$'odd\\nvalue'\n"
        "not a variable\n"
    )
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=output, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert mcp_service._systemd_session_env({}) == {
        "DISPLAY": ":0",
        "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
    }
    assert seen["cmd"] == ["systemctl", "--user", "show-environment"]


@pytest.mark.parametrize(
    "outcome",
    [FileNotFoundError("systemctl"), "timeout", 1],
    ids=["no systemctl", "timeout", "failed"],
)
def test_systemd_session_env_unavailable(monkeypatch, outcome):
    import subprocess

    def fake_run(cmd, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, 5)
        return subprocess.CompletedProcess(cmd, outcome, stdout="DISPLAY=:0", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert mcp_service._systemd_session_env({}) == {}


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


# ── The guide for apps without the skill ────────────────────────────


@pytest.mark.parametrize(
    "provider, expected_types, example",
    [
        (
            "aws",
            {
                "aws_ecs_fargate",
                "aws_rds_sqlserver",
                "aws_alb",
                "aws_az",
                "tv_aws_internet",
            },
            "three-tier-web",
        ),
        (
            "azure",
            {"azurerm_linux_web_app", "azurerm_mssql_database", "tv_azurerm_users"},
            "azure-three-tier",
        ),
        (
            "gcp",
            {
                "google_cloud_run_v2_service",
                "google_sql_database_instance",
                "tv_gcp_region",
            },
            "gcp-three-tier",
        ),
    ],
)
def test_diagram_guide(provider, expected_types, example):
    guide = mcp_service.diagram_guide(provider.upper())
    assert guide["provider"] == provider
    assert "## Drawn as written" in guide["rules"]
    assert expected_types <= set(guide["node_types"])
    others = {"aws": "azurerm_", "azure": "google_", "gcp": "aws_"}[provider]
    assert not any(t.startswith(others) for t in guide["node_types"])
    assert example in guide["examples"]


def test_aws_guide_example_has_the_detail_to_copy():
    """The worked example is what gives diagrams zones and an internet path."""
    example = mcp_service.diagram_guide("aws")["examples"]["three-tier-web"]
    types = {node.split(".")[0] for node in example}
    assert {"tv_aws_az", "aws_nat_gateway", "aws_internet_gateway"} <= types
    assert any("tv_aws_internet" in t for targets in example.values() for t in targets)


@pytest.mark.parametrize(
    "provider, example, network_types",
    [
        (
            "azure",
            "azure-three-tier",
            {
                "azurerm_virtual_network",
                "azurerm_subnet",
                "tv_azurerm_zone",
                "azurerm_nat_gateway",
            },
        ),
        (
            "gcp",
            "gcp-three-tier",
            {
                "google_compute_network",
                "tv_gcp_region",
                "google_compute_subnetwork",
                "tv_gcp_zone",
                "google_compute_router_nat",
            },
        ),
    ],
)
def test_azure_and_gcp_examples_have_the_detail_to_copy(
    provider, example, network_types
):
    guide = mcp_service.diagram_guide(provider)
    assert list(guide["examples"])[0] == example
    graph = guide["examples"][example]
    types = {
        n.split(".")[0] for n in set(graph) | {t for v in graph.values() for t in v}
    }
    assert network_types <= types


def test_diagram_guide_rejects_unknown_provider():
    with pytest.raises(McpServiceError, match="Use one of: aws, azure, gcp"):
        mcp_service.diagram_guide("oracle")


def test_skill_folder_ships_in_the_package():
    """diagram_guide reads the skill's files, so the wheel must include them."""
    import tomllib

    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    )
    includes = [i["path"] for i in pyproject["tool"]["poetry"]["include"]]
    assert "skills/**/*" in includes


def test_diagram_guide_lists_and_fetches_patterns():
    guide = mcp_service.diagram_guide("aws")
    names = [p["name"] for p in guide["patterns"]]
    assert "aws-eks" in names and all(n.startswith("aws-") for n in names)
    eks = mcp_service.diagram_guide("aws", pattern="aws-eks")
    assert set(eks) == {"provider", "pattern", "description", "graph"}
    assert any(n.startswith("aws_eks") for n in eks["graph"])


def test_diagram_guide_rejects_unknown_pattern():
    with pytest.raises(McpServiceError, match="Available: azure-aks"):
        mcp_service.diagram_guide("azure", pattern="aws-eks")


# ── Warnings in render_graph results ────────────────────────────────


def test_render_graph_warns_about_unknown_types_with_suggestions(outdir):
    result = mcp_service.run_render_graph(
        {"aws_lambda_function.fn": ["aws_rds_sql_server.db", "aws_vpc.main"]},
        outfile="warn",
        preview=False,
    )
    joined = "\n".join(result["warnings"])
    assert "Unknown type 'aws_rds_sql_server'" in joined
    assert "Did you mean aws_rds_sqlserver" in joined
    assert "aws_vpc is a container" in joined


def test_clean_graph_has_no_warnings(outdir):
    result = mcp_service.run_render_graph(GRAPH, outfile="clean", preview=False)
    assert "warnings" not in result


def test_warnings_reach_the_model_and_the_view(outdir, client_call):
    result = client_call(
        lambda c: c.call_tool(
            "render_graph",
            {"graph": {"aws_lambda_function.fn": ["aws_lamda_function.typo"]}},
        )
    )
    assert "Did you mean aws_lambda_function" in result.content[0].text
    assert result.structured_content["warnings"]
    from modules.mcp_view import VIEW_HTML

    assert "result.warnings" in VIEW_HTML


def test_interactive_html_refuses_graph_files(outdir, client_call):
    graph = outdir / "g.tvg.json"
    graph.write_text(json.dumps(GRAPH))
    result = client_call(
        lambda c: c.call_tool("generate_interactive_html", {"source": str(graph)})
    )
    assert result.is_error
    assert "a graph file (.tvg.json) has none" in result.content[0].text


# ── Setup status in diagram_guide ───────────────────────────────────


def test_setup_status_here():
    """CI and development machines always have Graphviz and Git."""
    status = mcp_service.setup_status()
    assert status["graphviz"] == "ok" and status["git"] == "ok"
    assert status["ready_for_graphs"] is True


@pytest.fixture
def machine(monkeypatch):
    """Pretend only some programs exist, on a chosen OS family."""
    import shutil

    import modules.helpers as helpers

    installed = set()
    monkeypatch.setattr(
        shutil, "which", lambda exe: f"/bin/{exe}" if exe in installed else None
    )
    monkeypatch.setattr(helpers, "_graphviz_install_dirs", lambda: [])
    monkeypatch.setattr(helpers, "neato_engine_error", lambda: None)

    def setup(os_family, *programs):
        installed.clear()
        installed.update(programs)
        monkeypatch.setattr(helpers, "_get_os_family", lambda: os_family)

    return setup


def test_missing_graphviz_on_macos(machine):
    machine("macos", "git", "terraform")
    status = mcp_service.setup_status()
    assert status["graphviz"] == "missing: dot, neato, gvpr"
    assert status["ready_for_graphs"] is False
    assert "brew install graphviz" in status["install"]
    guide = mcp_service.diagram_guide("aws")
    assert guide["setup"] == status
    assert guide["next_step"].startswith("Graphviz or Git is missing")


def test_terraform_is_optional(machine):
    machine("debian", "dot", "neato", "gvpr", "git")
    status = mcp_service.setup_status()
    assert status["ready_for_graphs"] is True
    assert status["ready_for_terraform"] is False
    assert status["terraform"].startswith("not found: only needed")
    assert not mcp_service.diagram_guide("aws")["next_step"].startswith("Graphviz")


def test_tofu_counts_as_terraform(machine):
    machine("debian", "dot", "neato", "gvpr", "git", "tofu")
    assert mcp_service.setup_status()["terraform"] == "ok (tofu)"


def test_missing_neato_engine_is_explained(machine, monkeypatch):
    import modules.helpers as helpers

    machine("debian", "dot", "neato", "gvpr", "git", "terraform")
    monkeypatch.setattr(
        helpers,
        "neato_engine_error",
        lambda: 'There is no layout engine support for "neato"',
    )
    status = mcp_service.setup_status()
    assert "libgvplugin-neato-layout8" in status["graphviz"]
    assert status["ready_for_graphs"] is False
    assert "install" not in status


def test_view_explains_calls_that_get_no_answer():
    """Claude Desktop connects only the newest view in a conversation.

    Calls from older views are never answered, so the view gives up after a
    while and says why instead of doing nothing.
    """
    from modules.mcp_view import VIEW_HTML

    assert "CALL_TIMEOUT_MS" in VIEW_HTML
    assert "Promise.race" in VIEW_HTML
    assert "newest diagram in a conversation" in VIEW_HTML


def test_view_uri_changes_with_the_view():
    """Claude Desktop caches the view by URI, so a changed view needs a new one."""
    import hashlib

    from modules.mcp_view import VIEW_HTML, VIEW_URI

    digest = hashlib.sha256(VIEW_HTML.encode()).hexdigest()[:12]
    assert VIEW_URI == f"ui://terravision/diagram-{digest}.html"


def test_guide_next_step_explains_each_clouds_zones():
    """AWS subnets are zonal; Azure and GCP subnets span zones."""
    steps = {
        p: mcp_service.diagram_guide(p)["next_step"] for p in ("aws", "azure", "gcp")
    }
    assert "one numbered copy in each zone's subnet" in steps["aws"]
    assert "tv_azurerm_zone" in steps["azure"]
    assert "tv_gcp_zone" in steps["gcp"]
    for step in steps.values():
        assert "Before rendering, check the graph against the request" in step


# ── Flows ────────────────────────────────────────────────────────────

FLOWS = {
    "order": {
        "description": "A customer places an order",
        "steps": [
            {"resource": "tv_aws_users.users", "detail": "Customer opens the app"},
            {
                "resource": "aws_alb.api -> aws_ecs_fargate.api",
                "detail": "Request -> Fargate task",
            },
            {"resource": "aws_rds_sqlserver.db", "detail": "Order saved"},
        ],
    }
}


def test_render_graph_draws_and_saves_flows(outdir):
    import yaml

    result = mcp_service.run_render_graph(
        GRAPH, outfile="flows", title="Orders", flows=FLOWS, preview=False
    )
    assert "warnings" not in result
    saved = yaml.safe_load(Path(result["files"]["annotations"]).read_text())
    assert saved == {"format": "0.3", "title": "Orders", "flows": FLOWS}
    drawio = Path(result["files"]["drawio"]).read_text()
    assert "Order saved" in drawio
    # The view may read it, like every file in the set.
    assert (
        "Customer opens"
        in mcp_service.read_output_file(result["files"]["annotations"])["text"]
    )


def test_saved_flows_redraw_with_the_cli(outdir, monkeypatch):
    """The .tvg.json and .annotations.yml reproduce the diagram."""
    from click.testing import CliRunner

    from terravision.terravision import cli

    result = mcp_service.run_render_graph(
        GRAPH, outfile="again", flows=FLOWS, preview=False
    )
    monkeypatch.chdir(outdir)
    run = CliRunner().invoke(
        cli,
        ["draw", "--source", result["files"]["graph"], "--annotate",
         result["files"]["annotations"], "--format", "dot", "--outfile", "cli"],
    )  # fmt: skip
    assert run.exit_code == 0, run.output
    assert "Request -&gt; Fargate task" in (outdir / "cli.dot.dot").read_text()


def test_flow_steps_without_a_badge_are_warnings(outdir):
    flows = {"order": {"steps": [{"resource": "aws_ecs_fargate.missing"}]}}
    result = mcp_service.run_render_graph(
        GRAPH, outfile="flowwarn", flows=flows, preview=False
    )
    assert result["warnings"] == [
        "Step 1 of flow 'order' draws no badge: aws_ecs_fargate.missing is not "
        "in the graph."
    ]


def test_malformed_flows_leave_no_files(outdir):
    with pytest.raises(McpServiceError, match="Invalid flows"):
        mcp_service.run_render_graph(GRAPH, outfile="bad", flows={"order": {}})
    assert list(outdir.iterdir()) == []


def test_generate_diagram_takes_flows(outdir):
    flows = {"order": {"steps": [{"resource": "aws_nothing.here"}]}}
    result = mcp_service.run_diagram(
        source=REPLAY_SOURCE, outfile="tf", flows=flows, preview=False
    )
    assert Path(result["files"]["annotations"]).is_file()
    assert "aws_nothing.here is not in the graph" in result["warnings"][0]


def test_diagram_tools_take_flows(client_call):
    tools = {t.name: t for t in client_call(lambda c: c.list_tools()).tools}
    for name in ("render_graph", "generate_diagram"):
        assert "flows" in tools[name].input_schema["properties"]
    assert "offer" in tools["render_graph"].description


def test_instructions_offer_flows_after_delivering():
    from modules.mcp_server import _INSTRUCTIONS

    text = " ".join(_INSTRUCTIONS.split())
    assert "Include them when the user asks how requests, data or events move" in text
    assert "offering to add it as numbered steps" in text


def test_render_graph_labels_arrows_and_saves_them(outdir):
    import yaml

    result = mcp_service.run_render_graph(
        GRAPH,
        outfile="labels",
        edge_labels={
            "aws_ecs_fargate.api -> aws_rds_sqlserver.db": "Reads orders",
            "aws_rds_sqlserver.db -> tv_aws_users.users": "Nope",
        },
        preview=False,
    )
    assert "Reads orders" in Path(result["files"]["svg"]).read_text()
    assert "no arrow between them" in result["warnings"][0]
    saved = yaml.safe_load(Path(result["files"]["annotations"]).read_text())
    assert saved["connect"]["aws_ecs_fargate.api"] == [
        {"aws_rds_sqlserver.db": "Reads orders"}
    ]


def test_malformed_edge_labels_leave_no_files(outdir):
    with pytest.raises(McpServiceError, match="edge_labels"):
        mcp_service.run_render_graph(GRAPH, outfile="bad", edge_labels={"x": "y"})
    assert list(outdir.iterdir()) == []


def test_button_feedback_shows_as_a_toast():
    """The status line sits under the diagram, often out of sight."""
    from modules.mcp_view import VIEW_HTML

    assert '<div id="toast" role="status" aria-live="polite"></div>' in VIEW_HTML
    assert '" copied to the clipboard."' in VIEW_HTML


def test_source_panel_holds_the_graph_and_annotations():
    """One Source button instead of Show JSON and Copy JSON, to keep the
    toolbar short; the annotations tab appears once flows are saved."""
    from modules.mcp_view import VIEW_HTML

    assert 'id="source"' in VIEW_HTML and 'id="tab-annotations"' in VIEW_HTML
    assert 'id="json"' not in VIEW_HTML
    assert "files().annotations" in VIEW_HTML


def test_plain_result_asks_the_model_to_offer_flows(outdir):
    plain = mcp_service.run_render_graph(GRAPH, outfile="plain", preview=False)
    assert "adding that flow to the diagram" in plain["next_step"]
    assert "Do neither before the user says yes" in plain["next_step"]
    flowed = mcp_service.run_render_graph(
        GRAPH, outfile="flowed", flows=FLOWS, preview=False
    )
    labelled = mcp_service.run_render_graph(
        GRAPH,
        outfile="labelled",
        edge_labels={"aws_alb.api -> aws_ecs_fargate.api": "Routes"},
        preview=False,
    )
    assert "next_step" not in flowed
    # Labels alone still get the flows offer, without offering labels again.
    assert "short labels" not in labelled["next_step"]
    assert "short labels" in plain["next_step"]


def test_graph_diagrams_offer_terraform_and_terraform_diagrams_do_not(outdir):
    """A diagram from a description has no code yet; one from Terraform does."""
    graph = mcp_service.run_render_graph(GRAPH, outfile="g", preview=False)
    assert "writing Terraform for this architecture" in graph["next_step"]
    assert "needs cloud credentials" in graph["next_step"]
    terraform = mcp_service.run_diagram(
        source=REPLAY_SOURCE, outfile="tf", preview=False
    )
    assert "adding that flow" in terraform["next_step"]
    assert "Terraform" not in terraform["next_step"]


def test_next_step_reaches_the_model(outdir, client_call):
    result = client_call(lambda c: c.call_tool("render_graph", {"graph": GRAPH}))
    assert "adding that flow to the diagram" in result.content[0].text
