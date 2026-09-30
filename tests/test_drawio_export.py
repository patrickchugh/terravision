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
