"""End-to-end checks of the draw.io export: what a user opens in draw.io.

A graph file is drawn with ``--format drawio`` and the resulting cells are
read back, so these cover the whole path (layout, xdot parsing, emitter).
"""

import json
import re
import xml.etree.ElementTree as ET

import pytest
from click.testing import CliRunner

from terravision.terravision import cli

AZURE = {
    "azurerm_resource_group.app": [
        "azurerm_virtual_network.main",
        "azurerm_key_vault.secrets",
        "azurerm_storage_account.data",
        "azurerm_cosmosdb_account.db",
        "azurerm_api_management.api",
        "azurerm_redis_cache.cache",
    ],
    "azurerm_virtual_network.main": ["azurerm_subnet.web", "azurerm_subnet.data"],
    "azurerm_subnet.web": [
        "azurerm_linux_virtual_machine.web",
        "azurerm_application_gateway.gw",
    ],
    "azurerm_subnet.data": ["azurerm_mssql_server.sql"],
    "azurerm_application_gateway.gw": ["azurerm_linux_virtual_machine.web"],
    "azurerm_linux_virtual_machine.web": ["azurerm_mssql_server.sql"],
}


def export(tmp_path, graph):
    """Draw ``graph`` as draw.io and return its cells, by id."""
    source = tmp_path / "graph.tvg.json"
    source.write_text(json.dumps(graph))
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(source),
            "--format",
            "drawio",
            "--outfile",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    [path] = tmp_path.glob("out*.drawio")
    return {c.get("id"): c for c in ET.parse(path).getroot().iter("mxCell")}


def text_of(cell):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cell.get("value") or "")).strip()


def box_of(cell, cells):
    """Absolute (left, top, right, bottom) of a cell; geometry is relative to
    its parent container."""
    geo = cell.find("mxGeometry")
    x, y = float(geo.get("x", 0)), float(geo.get("y", 0))
    parent = cells.get(cell.get("parent"))
    while parent is not None and parent.find("mxGeometry") is not None:
        pgeo = parent.find("mxGeometry")
        x += float(pgeo.get("x", 0))
        y += float(pgeo.get("y", 0))
        parent = cells.get(parent.get("parent"))
    return x, y, x + float(geo.get("width")), y + float(geo.get("height"))


def test_container_labels_have_their_names(tmp_path):
    """The label's text is wrapped in a FONT tag for its size; reading only
    cells of bare text left every Azure container label an icon with no
    name."""
    cells = export(tmp_path, AZURE)
    names = {text_of(c) for c in cells.values()}
    for expected in ("Resource Group App", "VNET Main", "Subnet Web", "Subnet Data"):
        assert expected in names


def test_container_labels_sit_inside_their_boxes(tmp_path):
    """Labels were placed against the box before it is shrunk for draw.io,
    which left them 50px to its left and below its bottom edge."""
    cells = export(tmp_path, AZURE)
    containers = [c for c in cells.values() if "container=1" in (c.get("style") or "")]
    labels = {
        text_of(c): c
        for c in cells.values()
        if "image=" in (c.get("style") or "") and "Position=middle" in c.get("style")
    }
    assert {"Subnet Web", "Subnet Data", "VNET Main"} <= set(labels)
    boxes = [box_of(c, cells) for c in containers]
    for name, label in labels.items():
        left, top, right, bottom = box_of(label, cells)
        holders = [
            b
            for b in boxes
            if b[0] <= left and right <= b[2] and b[1] <= top and bottom <= b[3]
        ]
        assert holders, f"{name} is outside every container box"


def test_only_real_connections_become_arrows(tmp_path):
    """Invisible edges arrange icons in a grid. Exported, they were arrows
    between unrelated resources (Key Vault -> API Management)."""
    cells = export(tmp_path, AZURE)
    arrows = {
        (text_of(cells[c.get("source")]), text_of(cells[c.get("target")]))
        for c in cells.values()
        if c.get("edge") == "1"
    }
    assert arrows == {
        ("Application Gateway Gw", "Linux VM Web"),
        ("Linux VM Web", "Mssql Server SQL"),
    }


# ── Icons: a draw.io shape where draw.io has one, else the icon as an image ──


def _leaf_types(provider, prefixes):
    import importlib
    import pkgutil

    from resource_classes import Cluster

    found = {}
    pkg = importlib.import_module(f"resource_classes.{provider}")
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"resource_classes.{provider}.{mod_info.name}")
        for name, cls in vars(mod).items():
            if name.startswith(prefixes) and isinstance(cls, type):
                if not issubclass(cls, Cluster) and getattr(cls, "_icon", None):
                    found[name] = cls
    return found


def _icon_path(cls):
    from pathlib import Path

    return str(Path(__file__).parents[1] / cls._icon_dir / cls._icon)


def test_every_mapped_shape_exists_in_drawio():
    """A shape draw.io does not have draws an empty box (Private_Endpoints.svg,
    Private_DNS_Zones.svg). The library snapshot comes from draw.io's source."""
    from modules.config.drawio_aws4_shapes import (
        AWS4_DIRECT_SHAPE_NAMES,
        AWS4_RESICON_NAMES,
    )
    from modules.config.drawio_icon_shapes import (
        DRAWIO_ICON_SHAPES_AWS,
        DRAWIO_ICON_SHAPES_AZURE,
        DRAWIO_ICON_SHAPES_GCP,
    )
    from modules.config.drawio_library import AZURE2_SVGS, GCP3_SHAPES
    from modules.config.drawio_shape_map_azure import DRAWIO_SHAPE_MAP_AZURE

    aws = set(AWS4_DIRECT_SHAPE_NAMES) | set(AWS4_RESICON_NAMES)
    for icon, shape in DRAWIO_ICON_SHAPES_AWS.items():
        assert shape.removeprefix("mxgraph.aws4.") in aws, icon
    for key, path in {**DRAWIO_ICON_SHAPES_AZURE, **DRAWIO_SHAPE_MAP_AZURE}.items():
        assert path in AZURE2_SVGS, key
    for icon, stencil in DRAWIO_ICON_SHAPES_GCP.items():
        assert stencil in GCP3_SHAPES, icon


@pytest.mark.parametrize(
    "provider, prefixes",
    [
        ("aws", ("aws_", "tv_aws_")),
        ("azure", ("azurerm_", "tv_azurerm_", "tv_azure_")),
    ],
)
def test_no_resource_type_exports_as_an_empty_box(provider, prefixes):
    """176 Azure and 146 AWS types had no mapping and exported as an empty
    box. Each is now a draw.io shape or its own icon embedded."""
    from modules.drawio_emitter import _build_node_style, load_shape_map
    from modules.xdot_parser import XdotNode

    shape_map = load_shape_map(provider)
    empty = []
    for name, cls in _leaf_types(provider, prefixes).items():
        node = XdotNode(
            id=name, pos=(0, 0), width=1, height=1, label=name, image=_icon_path(cls)
        )
        style, _, _ = _build_node_style(name, node, shape_map, provider)
        if not any(k in style for k in ("mxgraph.", "img/lib/", "data:image/png")):
            empty.append(name)
    assert empty == []


def test_most_icons_are_drawio_shapes():
    """Embedding is the fallback; draw.io's own shapes are the norm."""
    from modules.config.drawio_icon_shapes import (
        DRAWIO_ICON_SHAPES_AWS,
        DRAWIO_ICON_SHAPES_AZURE,
        DRAWIO_ICON_SHAPES_GCP,
    )
    from modules.drawio_emitter import _icon_key

    for provider, prefixes, table in (
        ("aws", ("aws_",), DRAWIO_ICON_SHAPES_AWS),
        ("azure", ("azurerm_",), DRAWIO_ICON_SHAPES_AZURE),
        ("gcp", ("google_",), DRAWIO_ICON_SHAPES_GCP),
    ):
        types = _leaf_types(provider, prefixes)
        covered = [t for t, c in types.items() if _icon_key(_icon_path(c)) in table]
        assert len(covered) / len(types) > 0.95, provider


GCP = {
    "google_compute_network.main": ["google_compute_subnetwork.app"],
    "google_compute_subnetwork.app": [
        "google_compute_instance.vm",
        "google_cloud_run_service.run",
    ],
    "google_compute_instance.vm": ["google_bigquery_dataset.bq"],
}


def test_gcp_cards_hold_drawio_gcp3_stencils(tmp_path):
    """GCP cards embedded a PNG; draw.io's gcp3 set has the same current
    icons as editable shapes, drawn inside the card."""
    cells = export(tmp_path, GCP)
    stencils = {
        re.search(r"shape=mxgraph\.gcp3\.([a-z_]+)", c.get("style")).group(1)
        for c in cells.values()
        if "mxgraph.gcp3." in (c.get("style") or "")
    }
    assert {"computeengine", "cloudrun", "bigquery"} <= stencils
    for cell in cells.values():
        if "mxgraph.gcp3." in (cell.get("style") or ""):
            assert "connectable=0" in cell.get("style")
            assert cells[cell.get("parent")].get("value"), "icon sits in its card"


def test_azure_export_has_no_empty_boxes(tmp_path):
    graph = dict(AZURE)
    graph["azurerm_subnet.web"] = graph["azurerm_subnet.web"] + [
        "azurerm_private_endpoint.pe",
        "azurerm_ai_foundry.ai",
    ]
    cells = export(tmp_path, graph)
    styles = [c.get("style") or "" for c in cells.values() if c.get("vertex") == "1"]
    assert not [s for s in styles if "fillColor=#dae8fc" in s]
    assert any("networking/Private_Endpoint.svg" in s for s in styles)


def test_gcp_cards_are_white_like_the_png(tmp_path):
    """Cards had no fill, so one outside a subnet showed the Google Cloud
    blue behind its dark text. The PNG draws them white."""
    graph = dict(GCP)
    graph["google_compute_instance.vm"] = graph["google_compute_instance.vm"] + [
        "google_storage_bucket.outside"
    ]
    cells = export(tmp_path, graph)
    cards = [
        c
        for c in cells.values()
        if "strokeColor=#DDDDDD" in (c.get("style") or "") and c.get("vertex") == "1"
    ]
    assert len(cards) >= 4
    assert all("fillColor=#FFFFFF" in c.get("style") for c in cards)


# ── Layout: compact, icons at draw.io's palette size, nothing overlapping ──


def export_source(tmp_path, source):
    """Draw a saved example (a replayed tfdata file) and return its cells."""
    from pathlib import Path

    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(Path(__file__).parent / "json" / source),
            "--format",
            "drawio",
            "--outfile",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    [path] = tmp_path.glob("out*.drawio")
    return {c.get("id"): c for c in ET.parse(path).getroot().iter("mxCell")}


def _resources(cells):
    """(cell, absolute box) for every resource icon or card."""
    found = []
    for cell in cells.values():
        style = cell.get("style") or ""
        if cell.get("vertex") != "1" or "container=1" in style:
            continue
        if style.startswith("text;") or "Position=middle" in style:
            continue  # titles and container labels
        if "connectable=0" in style:
            continue  # a GCP stencil inside its card
        if re.search(r"mxgraph\.|img/lib/|data:image|strokeColor=#DDDDDD", style):
            found.append((cell, box_of(cell, cells)))
    return found


def _overlap(a, b, pad=1):
    return (
        a[0] < b[2] - pad
        and b[0] < a[2] - pad
        and a[1] < b[3] - pad
        and b[1] < a[3] - pad
    )


def test_layout_is_pulled_together(tmp_path):
    """The layout is sized for TerraVision's PNG icons, two or three times
    draw.io's; nodes stood 5-8 icon widths apart. It is scaled down now."""
    import statistics

    for graph in (AZURE, GCP):
        resources = _resources(export(tmp_path, graph))
        centres = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for _, b in resources]
        widths = [b[2] - b[0] for _, b in resources]
        nearest = [
            min(
                ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
                for q in centres
                if q is not p
            )
            for p in centres
        ]
        assert statistics.median(nearest) < 4.5 * statistics.median(widths)
        for f in tmp_path.glob("out*.drawio"):
            f.unlink()


def test_icons_are_the_size_draw_io_gives_them():
    """Icons match the size draw.io's palette gives the same shape, so an
    icon a user drags in afterwards looks like the rest."""
    from modules.config.drawio_library import (
        AWS4_PALETTE_SIZES,
        AZURE2_PALETTE_SIZES,
    )
    from modules.drawio_emitter import _build_node_style, load_shape_map
    from modules.xdot_parser import XdotNode

    node = XdotNode(id="n", pos=(0, 0), width=1, height=1, label="x")
    style, w, h = _build_node_style(
        "aws_lambda_function", node, load_shape_map("aws"), "aws"
    )
    shape = re.search(r"shape=mxgraph\.aws4\.([a-z0-9_]+);", style)
    if shape and shape.group(1) in AWS4_PALETTE_SIZES:
        assert (w, h) == AWS4_PALETTE_SIZES[shape.group(1)]
    style, w, h = _build_node_style(
        "azurerm_linux_virtual_machine", node, load_shape_map("azure"), "azure"
    )
    image = re.search(r"image=img/lib/azure2/[^;]*/([^/;]+\.svg);", style).group(1)
    iw = float(re.search(r"imageWidth=([\d.]+)", style).group(1))
    ih = float(re.search(r"imageHeight=([\d.]+)", style).group(1))
    assert (iw, ih) == AZURE2_PALETTE_SIZES[image]


@pytest.mark.parametrize(
    "source",
    [
        "wordpress-tfdata.json",
        "azure-appgw-lb-tfdata.json",
        "gcp-three-tier-webapp-tfdata.json",
    ],
)
def test_nothing_overlaps_and_every_resource_is_in_its_box(tmp_path, source):
    cells = export_source(tmp_path, source)
    resources = _resources(cells)
    for i, (a, box_a) in enumerate(resources):
        for b, box_b in resources[i + 1 :]:
            assert not _overlap(box_a, box_b), (text_of(a), text_of(b))
        parent = cells.get(a.get("parent"))
        if parent is not None and "container=1" in (parent.get("style") or ""):
            outer = box_of(parent, cells)
            assert outer[0] - 1 <= box_a[0] and box_a[2] <= outer[2] + 1, text_of(a)
            assert outer[1] - 1 <= box_a[1] and box_a[3] <= outer[3] + 1, text_of(a)


def test_box_titles_show_text_not_markup(tmp_path):
    """Box titles are sized with <FONT POINT-SIZE=...>, which was escaped and
    shown as raw markup ("<FONT POINT-SIZE="20">Zone1</FONT>")."""
    cells = export_source(tmp_path, "azure-appgw-lb-tfdata.json")
    values = [c.get("value") or "" for c in cells.values()]
    assert not [v for v in values if "POINT-SIZE" in v]
    assert "Zone1" in {text_of(c) for c in cells.values()}


def test_gcp_wordmark_and_vpc_title_show_on_the_blue(tmp_path):
    """The white "Google Cloud" wordmark was placed below the blue box,
    invisible on the page, and the VPC title was dark on the blue."""
    cells = export_source(tmp_path, "gcp-us1-compute-tfdata.json")
    logos = [
        c
        for c in cells.values()
        if (c.get("style") or "").startswith("shape=image;imageAspect=0")
        and "container=1" in (cells[c.get("parent")].get("style") or "")
    ]
    assert logos, "the Google Cloud wordmark"
    for logo in logos:
        outer = box_of(cells[logo.get("parent")], cells)
        b = box_of(logo, cells)
        assert (
            outer[0] <= b[0]
            and b[2] <= outer[2]
            and outer[1] <= b[1]
            and b[3] <= outer[3]
        )
    vpc = next(c for c in cells.values() if text_of(c) == "VPC Main")
    assert "fontColor=#FFFFFF" in vpc.get("style")
