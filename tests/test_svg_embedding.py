"""Tests for portable SVG export (issue #207).

Standalone SVG output must embed icon images as base64 data URIs instead of
referencing absolute local paths inside the TerraVision installation.
"""

from pathlib import Path

from modules.drawing import _embed_icons_as_data_uris, make_svg_portable

REPO_ROOT = Path(__file__).parent.parent
ICON_PATH = REPO_ROOT / "resource_images" / "aws" / "general" / "aws.png"


def _write_svg(tmp_path, body):
    svg_file = tmp_path / "diagram.svg"
    svg_file.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink">{body}</svg>',
        encoding="utf-8",
    )
    return svg_file


def test_make_svg_portable_embeds_local_icons(tmp_path):
    svg_file = _write_svg(
        tmp_path,
        f'<image xlink:href="{ICON_PATH}" width="50" height="50"/>',
    )

    make_svg_portable(str(svg_file))

    result = svg_file.read_text(encoding="utf-8")
    assert str(ICON_PATH) not in result
    assert 'xlink:href="data:image/png;base64,' in result


def test_make_svg_portable_handles_plain_href(tmp_path):
    svg_file = _write_svg(
        tmp_path,
        f'<image href="{ICON_PATH}" width="50" height="50"/>',
    )

    make_svg_portable(str(svg_file))

    result = svg_file.read_text(encoding="utf-8")
    assert str(ICON_PATH) not in result
    assert 'href="data:image/png;base64,' in result


def test_make_svg_portable_leaves_urls_and_missing_paths(tmp_path):
    svg_file = _write_svg(
        tmp_path,
        '<a xlink:href="https://example.com/page">link</a>'
        '<image xlink:href="/nonexistent/path/icon.png"/>',
    )
    original = svg_file.read_text(encoding="utf-8")

    make_svg_portable(str(svg_file))

    assert svg_file.read_text(encoding="utf-8") == original


def test_make_svg_portable_is_idempotent(tmp_path):
    svg_file = _write_svg(
        tmp_path,
        f'<image xlink:href="{ICON_PATH}" width="50" height="50"/>',
    )

    make_svg_portable(str(svg_file))
    first_pass = svg_file.read_text(encoding="utf-8")
    make_svg_portable(str(svg_file))

    assert svg_file.read_text(encoding="utf-8") == first_pass


def test_embed_icons_as_data_uris_replaces_all_occurrences():
    text = f'image="{ICON_PATH}" and again image="{ICON_PATH}"'
    result = _embed_icons_as_data_uris(text, {str(ICON_PATH)})
    assert str(ICON_PATH) not in result
    assert result.count("data:image/png;base64,") == 2


def test_embed_icons_as_data_uris_skips_missing_files():
    text = 'image="/does/not/exist.png"'
    result = _embed_icons_as_data_uris(text, {"/does/not/exist.png"})
    assert result == text
