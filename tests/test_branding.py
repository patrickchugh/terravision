"""The TerraVision logo is the same everywhere it appears.

images/logo/ holds the master copies. Places that need their own copy (the
docs site, the Claude Desktop extension, the package the diagrams and MCP
server use) must match it byte for byte, so changing the logo means
replacing every copy.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "images" / "logo"

COPIES = {
    "mcpb/icon.png": "terravision-icon-512.png",
    "docs/assets/logo/terravision-icon.svg": "terravision-icon.svg",
    "docs/assets/logo/favicon.ico": "favicon.ico",
    "resource_images/terravision/terravision-icon.svg": "terravision-icon.svg",
    "resource_images/terravision/terravision-icon-64.png": "terravision-icon-64.png",
    "resource_images/terravision/terravision-icon-256.png": "terravision-icon-256.png",
}


@pytest.mark.parametrize("copy, master", COPIES.items())
def test_copies_match_the_master_logo(copy, master):
    assert (ROOT / copy).read_bytes() == (
        LOGO / master
    ).read_bytes(), (
        f"{copy} differs from images/logo/{master}; copy the new logo over it"
    )


def test_footer_shows_the_logo():
    from modules.drawing import _FOOTER_LOGO, _footer_html

    assert _FOOTER_LOGO.is_file()
    assert f'<IMG SRC="{_FOOTER_LOGO}"' in _footer_html("gen", "now", "src")


def test_interactive_html_has_the_favicon():
    from modules.html_renderer import _favicon_data_uri

    template = (ROOT / "modules" / "templates" / "interactive.html").read_text()
    assert 'rel="icon"' in template and "{{FAVICON}}" in template
    assert _favicon_data_uri().startswith("data:image/svg+xml;base64,")


def test_diagram_view_header_has_the_logo():
    from modules.mcp_view import VIEW_HTML

    assert "__LOGO__" not in VIEW_HTML
    assert 'class="logo" aria-hidden="true"' in VIEW_HTML
    assert 'fill="#3A36A0"' in VIEW_HTML


def test_mcp_server_advertises_the_logo():
    pytest.importorskip("mcp", reason="requires the optional [mcp] extra")
    from modules.mcp_server import _icons

    icons = _icons()
    assert [i.mime_type for i in icons] == ["image/svg+xml", "image/png"]
    assert all(i.src.startswith(f"data:{i.mime_type};base64,") for i in icons)


def test_docs_site_uses_the_logo():
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    assert "logo: assets/logo/terravision-icon.svg" in mkdocs
    assert "favicon: assets/logo/favicon.ico" in mkdocs
