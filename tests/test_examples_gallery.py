"""Every example graph in examples/graphs/ is a complete gallery example.

An example is <name>.tvg.json and <name>.annotations.yml, rendered to
<name>.png and <name>.svg by scripts/render_examples.py, a web-sized
docs/assets/gallery/<name>.webp, a section in docs/gallery.md and a row in
examples/graphs/README.md. These tests hold each one to that bar, so adding a
file to examples/graphs/ without the rest fails here.
"""

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "graphs"
GALLERY = ROOT / "docs" / "gallery.md"
README = EXAMPLES / "README.md"
WEBP_DIR = ROOT / "docs" / "assets" / "gallery"
RAW = "https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs"
BLOB = "https://github.com/patrickchugh/terravision/blob/main/examples/graphs"
MIN_NODES = 25
# Examples that had no annotations or gallery entry until the gallery
# expansion; held to the same bar as the rest.
FORMERLY_LIGHT = ("aws-event-driven", "azure-web-app", "gcp-serverless-api")
# Known gaps against the bar, each failing until it is fixed (strict xfail).
BELOW_BAR = {
    "gcp-three-tier": "has one flow; gallery examples have two or more",
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render_examples = _load("render_examples", ROOT / "scripts" / "render_examples.py")
STEMS = render_examples.stems()


def gallery_sections():
    """Map each example name to the gallery section whose image shows it."""
    sections = {}
    for section in re.split(r"\n(?=## )", GALLERY.read_text()):
        match = re.search(r"\(assets/gallery/([a-z0-9-]+)\.webp\)", section)
        if match:
            sections[match.group(1)] = section
    return sections


SECTIONS = gallery_sections()


def nodes_of(stem):
    graph = json.loads((EXAMPLES / f"{stem}.tvg.json").read_text())
    return set(graph) | {t for targets in graph.values() for t in targets}


def test_examples_found():
    assert len(STEMS) >= 15
    for stem in FORMERLY_LIGHT:
        assert stem in STEMS


@pytest.mark.parametrize("stem", STEMS)
def test_validates(stem):
    errors, _ = render_examples.check(stem)
    assert errors == []


@pytest.mark.parametrize("stem", STEMS)
def test_annotations_file_exists(stem):
    assert (EXAMPLES / f"{stem}.annotations.yml").is_file()


@pytest.mark.parametrize(
    "stem",
    [
        (
            pytest.param(s, marks=pytest.mark.xfail(reason=BELOW_BAR[s], strict=True))
            if s in BELOW_BAR
            else s
        )
        for s in STEMS
    ],
)
def test_draws_without_warnings(stem):
    """No flow step without a badge, label on a missing arrow, node listed in
    two boxes, network or subnet without a CIDR range, or fewer than two flows."""
    _, warnings = render_examples.check(stem)
    assert warnings == []


@pytest.mark.parametrize("stem", STEMS)
def test_has_enough_nodes(stem):
    assert len(nodes_of(stem)) >= MIN_NODES


@pytest.mark.parametrize("stem", STEMS)
def test_renders_to_svg(stem, tmp_path):
    if not shutil.which("dot"):
        pytest.skip("Graphviz 'dot' is not installed, so nothing can be rendered")
    render_examples.render(stem, outdir=tmp_path, formats=("svg",))
    svg = tmp_path / f"{stem}.svg"
    assert svg.stat().st_size > 0
    assert "<svg" in svg.read_text()[:2000]


@pytest.mark.parametrize("stem", STEMS)
def test_rendered_files_exist(stem):
    for path in (
        EXAMPLES / f"{stem}.png",
        EXAMPLES / f"{stem}.svg",
        WEBP_DIR / f"{stem}.webp",
    ):
        assert path.is_file(), f"{path.relative_to(ROOT)} is missing"


@pytest.mark.parametrize("stem", STEMS)
def test_gallery_section(stem):
    """The section follows the gallery's format and shows this example."""
    section = SECTIONS.get(stem)
    assert section, f"docs/gallery.md has no section showing assets/gallery/{stem}.webp"
    assert re.match(r"## .+ \{ #[a-z0-9-]+ \}\n", section)
    prompt = re.search(r"\*\*Ask your AI assistant:\*\*\n\n> (.+)\n", section)
    assert prompt, "no '**Ask your AI assistant:**' prompt"
    assert (
        len(prompt.group(1).split()) >= 25
    ), "the prompt is too short to describe the diagram"
    assert f"]({RAW}/{stem}.png)" in section
    assert (
        f"**Or reproduce it exactly** from the source file [{stem}.tvg.json]({BLOB}/{stem}.tvg.json)"
        in section
    )
    assert f"[{stem}.annotations.yml]({BLOB}/{stem}.annotations.yml)" in section
    assert (
        f"terravision draw --source {stem}.tvg.json --annotate {stem}.annotations.yml --format svg"
        in section
    )
    assert (
        f"terravision draw --source {stem}.tvg.json --annotate {stem}.annotations.yml --format drawio"
        in section
    )
    assert section.count(f"{RAW}/{stem}.") >= 5, "Download line incomplete"


@pytest.mark.parametrize("stem", STEMS)
def test_gallery_image_size_matches_webp(stem):
    section = SECTIONS.get(stem)
    assert section, f"docs/gallery.md has no section for {stem}"
    manifest = json.loads((WEBP_DIR / "sources.json").read_text())
    match = re.search(
        rf"\(assets/gallery/{re.escape(stem)}\.webp\)\{{ width=(\d+) height=(\d+)",
        section,
    )
    assert match, "the image has no explicit width and height"
    assert (int(match.group(1)), int(match.group(2))) == (
        manifest[stem]["width"],
        manifest[stem]["height"],
    ), "run scripts/render_examples.py to update the size"


def test_gallery_images_load_lazily_after_the_first():
    images = re.findall(
        r"\(assets/gallery/[a-z0-9-]+\.webp\)\{([^}]*)\}", GALLERY.read_text()
    )
    for attributes in images[1:]:
        assert "loading=lazy" in attributes


@pytest.mark.parametrize("stem", STEMS)
def test_readme_row(stem):
    row = re.search(
        rf"^\| `{re.escape(stem)}\.tvg\.json` \| (AWS|Azure|GCP) \| .+ \|$",
        README.read_text(),
        re.M,
    )
    assert row, f"examples/graphs/README.md has no table row for {stem}.tvg.json"


@pytest.mark.parametrize("path", ["docs/llms.txt", "docs/llms-full.txt"])
def test_llms_example_list_is_current(path):
    """The generated block matches the README table: run render_examples.py."""
    update = _load("update_llms_examples", ROOT / "scripts" / "update_llms_examples.py")
    assert update.block() in (ROOT / path).read_text()
    for stem in STEMS:
        assert f"[{stem}.tvg.json]({RAW}/{stem}.tvg.json)" in update.block()


@pytest.mark.parametrize("stem", FORMERLY_LIGHT)
def test_formerly_light_example_is_complete(stem):
    assert len(nodes_of(stem)) >= MIN_NODES
    assert (EXAMPLES / f"{stem}.annotations.yml").is_file()
    assert stem in SECTIONS
    _, warnings = render_examples.check(stem)
    assert warnings == []
