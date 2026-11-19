"""Text from a terravision.yml or a plan never becomes markup, links or files.

A terravision.yml in a folder someone else diagrams is loaded automatically,
even with --planfile, so its title and labels are untrusted. They must stay
text in the DOT source, the interactive HTML page and the SVG, and only
TerraVision's own icons may be embedded into the output.
"""

import base64
import re
from html.parser import HTMLParser
from pathlib import Path

import graphviz

from modules import drawing, drawio_emitter, helpers, html_renderer
from resource_classes import Edge

MARKER = "tvmark"
HOSTILE = f'<x> URL="{MARKER}:1" y=<z>'
ICON = Path(helpers.__file__).resolve().parents[1] / (
    "resource_images/aws/compute/batch.png"
)


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


def _parsed_tags(page: str) -> list:
    parser = _Tags()
    parser.feed(page)
    return parser.tags


# Interactive HTML page


def _page(tmp_path, monkeypatch, title, svg="<svg></svg>", meta='{"a": 1}'):
    monkeypatch.chdir(tmp_path)
    path = html_renderer._assemble_html(svg, meta, "out.html", title=title)
    return Path(path).read_text(encoding="utf-8")


def test_title_naming_a_placeholder_stays_literal(tmp_path, monkeypatch):
    meta = '{"v": "tv<i>MARK</i>"}'
    page = _page(tmp_path, monkeypatch, "Prod {{METADATA_JSON}}", meta=meta)
    assert '<div id="diagram-title">Prod {{METADATA_JSON}}</div>' in page
    assert "i" not in _parsed_tags(page)


def test_svg_text_naming_a_placeholder_stays_literal(tmp_path, monkeypatch):
    svg = "<svg><text>{{METADATA_JSON}} {{TITLE}}</text></svg>"
    meta = '{"v": "tv<i>MARK</i>"}'
    page = _page(tmp_path, monkeypatch, "Prod", svg=svg, meta=meta)
    assert "<text>{{METADATA_JSON}} {{TITLE}}</text>" in page
    assert "i" not in _parsed_tags(page)


def test_metadata_cannot_close_its_script(tmp_path, monkeypatch):
    meta = '{"v": "</script><script>alert(1)</script> & <!--"}'
    page = _page(tmp_path, monkeypatch, "Prod", meta=meta)
    data = page.split("var TERRAVISION_DATA = ", 1)[1].split(";\n", 1)[0]
    assert "<" not in data and ">" not in data and "&" not in data
    assert "\\u003c/script\\u003e" in data


# DOT source


def _dot_with_node(label: str) -> str:
    graph = graphviz.Digraph()
    graph.node("n", label)
    return graph.source


def test_hostile_label_is_quoted_text_in_dot():
    source = _dot_with_node(helpers.dot_text(HOSTILE))
    assert "label=<" not in source
    assert 'label="&lt;x&gt; URL=' in source


def test_annotation_label_is_escaped_for_nodes_and_boxes():
    tfdata = {
        "annotations": {"update": {"aws_vpc.main": {"label": HOSTILE}}},
        "graphdict": {"aws_vpc.main": []},
        "meta_data": {"aws_vpc.main": {}},
    }
    for is_group in (False, True):
        label = helpers.node_label("aws_vpc.main", tfdata, is_group=is_group)
        assert "<" not in label and ">" not in label
        assert "&lt;x&gt;" in label


def test_box_caption_cannot_add_a_cell():
    caption = helpers.dot_text('</TD><TD HREF="tvmark:1">x')
    assert "</TD>" not in caption and "<TD" not in caption


def test_edge_text_is_always_quoted():
    edge = Edge(label=HOSTILE)
    graph = graphviz.Digraph()
    graph.edge("a", "b", **edge._attrs)
    assert "_edgetext=<" not in graph.source
    assert '_edgetext="<x> URL=' in graph.source


# Embedding files into the output


def test_only_bundled_icons_count_as_images(tmp_path):
    secret = tmp_path / "credentials"
    secret.write_text("SECRET")
    assert helpers.is_bundled_image(str(ICON))
    assert not helpers.is_bundled_image(str(secret))
    assert not helpers.is_bundled_image(str(ICON.parent / "../../../pyproject.toml"))
    assert not helpers.is_bundled_image("/proc/self/environ")
    assert not helpers.is_bundled_image("")


def test_svg_embeds_icons_but_not_other_files(tmp_path):
    secret = tmp_path / "credentials"
    secret.write_text("SECRET")
    svg = tmp_path / "d.svg"
    svg.write_text(
        f'<svg><a xlink:href="{secret}"/><image xlink:href="{ICON}"/></svg>',
        encoding="utf-8",
    )
    drawing.make_svg_portable(str(svg))
    out = svg.read_text(encoding="utf-8")
    assert f'xlink:href="{secret}"' in out
    assert base64.b64encode(b"SECRET").decode() not in out
    assert str(ICON) not in out
    assert re.search(r'xlink:href="data:image/png;base64,[A-Za-z0-9+/=]+"', out)


def test_drawio_reads_only_bundled_icons(tmp_path):
    secret = tmp_path / "credentials"
    secret.write_text("SECRET")
    assert drawio_emitter._encode_icon_base64(str(secret)) == ""
    assert drawio_emitter._encode_icon_base64(str(ICON))


def test_drawio_label_decodes_before_escaping():
    assert drawio_emitter._sanitize_label("R&amp;D &lt;x&gt;") == "R&amp;D &lt;x&gt;"
