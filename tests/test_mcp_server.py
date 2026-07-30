"""Tests for the MCP server layer.

Skipped entirely when the optional ``mcp`` extra is not installed, so a
default install can still run the suite. Tool calls go through the SDK's
in-memory client, which exercises schema validation and result serialisation
without spawning a subprocess.

Anything that would invoke Terraform is driven from a replayable
``tfdata.json`` fixture instead, so nothing here needs the binary and no test
carries the ``slow`` marker. The one behaviour a replay source cannot reach --
``tfwrapper`` returning the process to its import-time directory once a plan
finishes -- is covered in ``test_mcp_service.py`` by reproducing that chdir
directly, which is faster and asserts the same invariant.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="requires the optional [mcp] extra")

import anyio  # noqa: E402
from mcp import Client  # noqa: E402

from modules.mcp_server import build_server, serve  # noqa: E402

EXPECTED_TOOLS = {
    "generate_architecture_graph",
    "generate_diagram",
    "generate_interactive_html",
}

REPLAY_SOURCE = str(Path(__file__).parent / "json" / "bastion-tfdata.json")


@pytest.fixture
def server():
    return build_server()


def _run(coro_fn):
    """Run an async helper on a fresh event loop."""
    return anyio.run(coro_fn)


# ── Registration and schemas ──────────────────────────────────────────


def test_all_tools_registered(server):
    tools = _run(server.list_tools)
    assert {t.name for t in tools} == EXPECTED_TOOLS


def test_tools_have_descriptions(server):
    """Descriptions are the contract an agent reads before calling."""
    for tool in _run(server.list_tools):
        assert tool.description and len(tool.description) > 50


def test_server_advertises_name_and_instructions(server):
    assert server.name == "terravision"
    assert "TerraVision" in (server.instructions or "")


@pytest.mark.parametrize(
    "tool_name,expected",
    [
        (
            "generate_architecture_graph",
            {
                "source",
                "varfile",
                "workspace",
                "planfile",
                "graphfile",
                "simplified",
                "annotate",
                "services_only",
                "upgrade",
            },
        ),
        (
            "generate_diagram",
            {
                "source",
                "format",
                "outfile",
                "varfile",
                "workspace",
                "planfile",
                "graphfile",
                "simplified",
                "annotate",
                "use_tf_names",
                "use_resource_names",
                "fontsize",
                "iconsize",
                "upgrade",
            },
        ),
        (
            "generate_interactive_html",
            {
                "source",
                "outfile",
                "varfile",
                "workspace",
                "planfile",
                "graphfile",
                "simplified",
                "annotate",
                "use_tf_names",
                "use_resource_names",
                "fontsize",
                "iconsize",
                "upgrade",
            },
        ),
    ],
)
def test_tool_schema_exposes_expected_parameters(server, tool_name, expected):
    tool = next(t for t in _run(server.list_tools) if t.name == tool_name)
    assert set(tool.input_schema["properties"]) == expected


def test_source_is_the_only_required_parameter(server):
    for tool in _run(server.list_tools):
        assert tool.input_schema["required"] == ["source"]


# ── In-memory client round-trip ───────────────────────────────────────


def _call(server, name, arguments):
    """Call a tool through the SDK client and return the parsed payload."""

    async def go():
        async with Client(server) as client:
            result = await client.call_tool(name, arguments)
            return result

    return _run(go)


def _payload(result):
    """Decode the JSON body of a successful tool result."""
    return json.loads(result.content[0].text)


def test_client_lists_tools_over_the_protocol(server):
    async def go():
        async with Client(server) as client:
            return await client.list_tools()

    assert {t.name for t in _run(go).tools} == EXPECTED_TOOLS


def test_services_only_returns_service_list(server):
    result = _call(
        server,
        "generate_architecture_graph",
        {"source": REPLAY_SOURCE, "services_only": True},
    )
    assert not result.is_error
    payload = _payload(result)
    assert payload["count"] == len(payload["services"])
    assert payload["count"] > 0
    # Service types are bare prefixes, not full resource addresses.
    assert all("." not in s for s in payload["services"])


def test_full_graph_returns_adjacency_list(server):
    result = _call(server, "generate_architecture_graph", {"source": REPLAY_SOURCE})
    assert not result.is_error
    payload = _payload(result)
    graphdict = payload["graphdict"]
    assert payload["node_count"] == len(graphdict)
    assert payload["edge_count"] == sum(len(v) for v in graphdict.values())
    assert all(isinstance(v, list) for v in graphdict.values())


def test_simplified_graph_is_not_larger(server):
    full = _payload(
        _call(server, "generate_architecture_graph", {"source": REPLAY_SOURCE})
    )
    simple = _payload(
        _call(
            server,
            "generate_architecture_graph",
            {"source": REPLAY_SOURCE, "simplified": True},
        )
    )
    assert simple["node_count"] <= full["node_count"]


# ── Cross-client compatibility ────────────────────────────────────────
#
# Clients other than Claude Code (Codex, Copilot/VS Code, Cursor, Zed, ...)
# negotiate a range of MCP protocol versions. A `content` block of type
# "text" is the one response field present in every version since the
# original 2024-11-05 spec, so results must always be readable from it
# rather than only from newer fields such as structuredContent.


def test_results_carry_a_text_content_block(server):
    result = _call(
        server,
        "generate_architecture_graph",
        {"source": REPLAY_SOURCE, "services_only": True},
    )
    assert result.content, "no content block; older clients would see nothing"
    assert result.content[0].type == "text"
    json.loads(result.content[0].text)  # must parse without newer fields


def test_errors_carry_a_text_content_block(server):
    """An error must be legible to an old client too, not just a flag."""
    result = _call(
        server,
        "generate_diagram",
        {"source": REPLAY_SOURCE, "format": "notaformat"},
    )
    assert result.is_error
    assert result.content and result.content[0].type == "text"
    assert result.content[0].text.strip()


def test_schemas_are_plain_json_types(server):
    """Parameters must use types any client can render in a tool form."""
    allowed = {"string", "integer", "number", "boolean", "array", "null"}
    for tool in _run(server.list_tools):
        for name, spec in tool.input_schema["properties"].items():
            declared = spec.get("type")
            if declared is None:  # optional params use anyOf
                variants = spec.get("anyOf", [])
                assert variants, f"{tool.name}.{name} has no usable type"
                assert all(
                    v.get("type") in allowed for v in variants
                ), f"{tool.name}.{name} exposes a non-primitive type"
            else:
                assert declared in allowed, f"{tool.name}.{name}: {declared}"


# ── Error handling ────────────────────────────────────────────────────


def test_missing_source_is_reported_not_fatal(server):
    """A bad request must fail one call, never take the server down."""
    result = _call(
        server,
        "generate_architecture_graph",
        {"source": "/nonexistent/path/to/terraform"},
    )
    assert result.is_error


def test_server_survives_a_failed_call(server):
    """The next call still succeeds after an error."""
    _call(
        server,
        "generate_architecture_graph",
        {"source": "/nonexistent/path/to/terraform"},
    )
    result = _call(
        server,
        "generate_architecture_graph",
        {"source": REPLAY_SOURCE, "services_only": True},
    )
    assert not result.is_error


def test_unsupported_format_is_reported(server):
    result = _call(
        server,
        "generate_diagram",
        {"source": REPLAY_SOURCE, "format": "notaformat"},
    )
    assert result.is_error
    assert "Unsupported format" in result.content[0].text


def test_outfile_path_traversal_is_rejected(server):
    result = _call(
        server,
        "generate_diagram",
        {"source": REPLAY_SOURCE, "outfile": "../escape"},
    )
    assert result.is_error


# ── Parity with the equivalent CLI command ────────────────────────────
#
# The whole design rests on the MCP tools being a pass-through to the CLI
# pipeline. If these drift, the service layer has grown behaviour of its own.


def test_graph_matches_graphdata_command(server, tmp_path, monkeypatch):
    """generate_architecture_graph must equal `terravision graphdata`."""
    from click.testing import CliRunner

    from terravision.terravision import cli

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli,
        ["graphdata", "--source", REPLAY_SOURCE, "--outfile", "cli"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    cli_graph = json.loads((tmp_path / "cli.json").read_text())

    mcp_graph = _payload(
        _call(server, "generate_architecture_graph", {"source": REPLAY_SOURCE})
    )["graphdict"]

    assert mcp_graph == cli_graph


def test_diagram_matches_draw_command(server, tmp_path, monkeypatch):
    """generate_diagram must equal `terravision draw` for the same source.

    The rendered footer carries a generation timestamp, so two runs of the
    *same* command never match byte for byte either. Timestamps are stripped
    before comparing; everything else must be identical.
    """
    import re

    from click.testing import CliRunner

    from modules import mcp_service
    from terravision.terravision import cli

    def normalise(text):
        return re.sub(r"[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+", "", text)

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            REPLAY_SOURCE,
            "--format",
            "drawio",
            "--outfile",
            "cli",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    cli_xml = (tmp_path / "cli-aws.drawio").read_text(encoding="utf-8")

    mcp_service.set_output_dir(str(tmp_path))
    payload = _payload(
        _call(
            server,
            "generate_diagram",
            {"source": REPLAY_SOURCE, "format": "drawio", "outfile": "mcp"},
        )
    )
    mcp_xml = Path(payload["path"]).read_text(encoding="utf-8")

    assert normalise(mcp_xml) == normalise(cli_xml)


def test_diagram_lands_in_the_configured_output_dir(server, tmp_path):
    from modules import mcp_service

    mcp_service.set_output_dir(str(tmp_path))
    payload = _payload(
        _call(
            server,
            "generate_diagram",
            {"source": REPLAY_SOURCE, "format": "drawio", "outfile": "out"},
        )
    )
    produced = Path(payload["path"])
    assert produced.parent == tmp_path.resolve()
    assert produced.name == "out-aws.drawio"
    assert produced.exists()


def test_interactive_html_lands_in_the_configured_output_dir(server, tmp_path):
    """Exercise the third tool end to end.

    The other two tools have round-trip tests; without this one the whole
    body of run_interactive_html is reachable only through the schema.
    """
    from modules import mcp_service

    mcp_service.set_output_dir(str(tmp_path))
    payload = _payload(
        _call(
            server,
            "generate_interactive_html",
            {"source": REPLAY_SOURCE, "outfile": "page"},
        )
    )
    produced = Path(payload["path"])
    assert produced.parent == tmp_path.resolve()
    assert produced.name == "page-aws.html", "provider suffix not applied"
    assert produced.exists()

    # Self-contained page: the markup and the resource data must both be
    # in the file, since it is meant to open offline.
    markup = produced.read_text(encoding="utf-8")
    assert "<html" in markup.lower()
    assert payload["provider"] == "aws"


# ── Transport selection ───────────────────────────────────────────────


def test_serve_rejects_unsupported_transport():
    with pytest.raises(ValueError, match="Only 'stdio' is supported"):
        serve(transport="sse")
