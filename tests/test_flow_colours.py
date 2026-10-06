"""A flow's colour reaches the diagram, and arrow labels read on any canvas.

The colour set on a flow only coloured the legend: the circles on the
diagram stayed red and the text beside them a light blue that vanished on
Google Cloud's blue canvas.
"""

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from modules import drawing
from terravision.terravision import cli

GRAPH = {
    "tv_gcp_users_icon.customers": ["google_cloud_run_v2_service.api"],
    "google_cloud_run_v2_service.api": ["google_pubsub_topic.orders"],
    "google_pubsub_topic.orders": ["google_bigquery_dataset.sales"],
}
ANNOTATIONS = {
    "format": "0.3",
    "connect": {
        "google_cloud_run_v2_service.api": [
            {"google_pubsub_topic.orders": "Publishes order events"}
        ]
    },
    "flows": {
        "order": {
            "description": "An order",
            "color": "#FFD600",
            "steps": [
                {
                    "resource": "google_cloud_run_v2_service.api -> google_pubsub_topic.orders"
                },
                {
                    "resource": "google_pubsub_topic.orders -> google_bigquery_dataset.sales"
                },
            ],
        }
    },
}


def _draw(tmp_path, monkeypatch, fmt):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "g.tvg.json").write_text(json.dumps(GRAPH))
    (tmp_path / "a.yml").write_text(yaml.safe_dump(ANNOTATIONS))
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            "g.tvg.json",
            "--annotate",
            "a.yml",
            "--format",
            fmt,
            "--outfile",
            str(tmp_path / "out"),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return next(tmp_path.glob(f"out*.{fmt}")).read_text()


def test_flow_colour_reaches_the_diagram_badges_and_label(tmp_path, monkeypatch):
    dot = _draw(tmp_path, monkeypatch, "dot")
    # Circles carry the flow's colour, for the draw.io export too
    assert '_flowcolors="#FFD600' in dot
    # The label text takes the flow's colour, on a dark ground for light text
    assert 'COLOR="#FFD600">Publishes order events' in dot
    assert 'BGCOLOR="#2D3436"' in dot


def test_drawio_circles_take_the_flow_colour(tmp_path, monkeypatch):
    drawio = _draw(tmp_path, monkeypatch, "drawio")
    assert (
        "fillColor=#FFD600;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#2D3436"
        in drawio
    )


def test_label_ground_is_dark_for_light_text_and_white_otherwise():
    assert drawing._label_ground("#FFD600") == "#2D3436"
    assert drawing._label_ground("#FFFFFF") == "#2D3436"
    assert drawing._label_ground("#5b9bd5") == "white"
    assert drawing._label_ground("#E74C3C") == "white"


def test_a_plain_arrow_label_sits_on_a_white_ground():
    from resource_classes import Edge

    edge = Edge(label="TDS 8.0, port 1433")
    assert 'BGCOLOR="white"' in edge._attrs["xlabel"]
    assert edge._attrs["_edgetext"] == "TDS 8.0, port 1433"
