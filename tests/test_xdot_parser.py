"""Unit tests for the xdot parser module."""

import json
import pytest
from modules.xdot_parser import (
    XdotGraph,
    XdotNode,
    XdotCluster,
    XdotEdge,
    parse_xdot,
    _parse_bb,
    _parse_pos,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_json(objects=None, edges=None, bb="0,0,800,600"):
    """Build a minimal Graphviz json0 structure."""
    data = {
        "name": "G",
        "directed": True,
        "strict": False,
        "bb": bb,
        "objects": objects or [],
        "edges": edges or [],
    }
    return json.dumps(data)


def _make_node(gvid, name, pos="100,200", width="1.0", height="0.8", **extra):
    obj = {
        "_gvid": gvid,
        "name": name,
        "pos": pos,
        "width": width,
        "height": height,
        "label": name,
    }
    obj.update(extra)
    return obj


def _make_cluster(name, nodes=None, bb="50,50,400,300", **extra):
    obj = {
        "name": name,
        "bb": bb,
        "label": name,
        "_gvid": 999,
        "nodes": nodes or [],
    }
    obj.update(extra)
    return obj


# ── Tests ─────────────────────────────────────────────────────────────


class TestParseBB:
    def test_basic(self):
        assert _parse_bb("0,0,800,600") == (0.0, 0.0, 800.0, 600.0)

    def test_floating_point(self):
        assert _parse_bb("10.5,20.3,500.7,400.1") == (10.5, 20.3, 500.7, 400.1)


class TestParsePos:
    def test_basic(self):
        assert _parse_pos("100,200") == (100.0, 200.0)

    def test_pinned(self):
        assert _parse_pos("100,200!") == (100.0, 200.0)

    def test_float(self):
        assert _parse_pos("123.45,678.90") == (123.45, 678.90)


class TestParseXdotNodes:
    def test_single_node(self):
        json_text = _make_json(objects=[_make_node(0, "aws_lambda.my_func")])
        graph = parse_xdot(json_text)
        assert len(graph.nodes) == 1
        node = graph.nodes["aws_lambda.my_func"]
        assert node.pos == (100.0, 200.0)
        assert node.width == 1.0
        assert node.height == 0.8

    def test_node_with_image(self):
        json_text = _make_json(
            objects=[_make_node(0, "node1", image="/path/to/icon.png")]
        )
        graph = parse_xdot(json_text)
        assert graph.nodes["node1"].image == "/path/to/icon.png"

    def test_node_with_custom_attrs(self):
        json_text = _make_json(
            objects=[
                _make_node(
                    0,
                    "title",
                    _titlenode="1",
                    _footernode="0",
                )
            ]
        )
        graph = parse_xdot(json_text)
        assert graph.nodes["title"].attrs["_titlenode"] == "1"

    def test_node_without_pos_skipped(self):
        obj = {"_gvid": 0, "name": "no_pos", "width": "1.0", "height": "1.0"}
        json_text = _make_json(objects=[obj])
        graph = parse_xdot(json_text)
        assert len(graph.nodes) == 0

    def test_multiple_nodes(self):
        json_text = _make_json(
            objects=[
                _make_node(0, "node_a", pos="100,100"),
                _make_node(1, "node_b", pos="200,200"),
                _make_node(2, "node_c", pos="300,300"),
            ]
        )
        graph = parse_xdot(json_text)
        assert len(graph.nodes) == 3


class TestParseXdotClusters:
    def test_cluster_parsed(self):
        cluster = _make_cluster("cluster_vpc", bb="10,10,400,300")
        json_text = _make_json(objects=[cluster])
        graph = parse_xdot(json_text)
        assert "cluster_vpc" in graph.clusters
        assert graph.clusters["cluster_vpc"].bb == (10.0, 10.0, 400.0, 300.0)

    def test_nested_clusters(self):
        inner = _make_cluster("cluster_subnet", bb="50,50,200,200")
        outer = _make_cluster("cluster_vpc", bb="10,10,400,300")
        outer["objects"] = [inner]
        json_text = _make_json(objects=[outer])
        graph = parse_xdot(json_text)
        assert graph.clusters["cluster_subnet"].parent == "cluster_vpc"

    def test_cluster_style_attrs(self):
        cluster = _make_cluster(
            "cluster_test",
            fillcolor="#E5F5FD",
            color="#2196F3",
            style="rounded",
        )
        json_text = _make_json(objects=[cluster])
        graph = parse_xdot(json_text)
        c = graph.clusters["cluster_test"]
        assert c.style["fillcolor"] == "#E5F5FD"
        assert c.style["color"] == "#2196F3"

    def test_non_cluster_subgraph_ignored(self):
        """Subgraphs not starting with 'cluster_' are not stored as clusters."""
        sub = {"name": "some_subgraph", "nodes": [0], "_gvid": 10}
        node = _make_node(0, "inner_node")
        sub["objects"] = [node]
        json_text = _make_json(objects=[sub])
        graph = parse_xdot(json_text)
        assert len(graph.clusters) == 0
        assert "inner_node" in graph.nodes


class TestParseXdotEdges:
    def test_basic_edge(self):
        json_text = _make_json(
            objects=[
                _make_node(0, "src"),
                _make_node(1, "dst"),
            ],
            edges=[{"tail": 0, "head": 1}],
        )
        graph = parse_xdot(json_text)
        assert len(graph.edges) == 1
        assert graph.edges[0].source == "src"
        assert graph.edges[0].target == "dst"

    def test_edge_with_label(self):
        json_text = _make_json(
            objects=[
                _make_node(0, "a"),
                _make_node(1, "b"),
            ],
            edges=[{"tail": 0, "head": 1, "label": "connects to", "lp": "150,150"}],
        )
        graph = parse_xdot(json_text)
        assert graph.edges[0].label == "connects to"
        assert graph.edges[0].label_pos == (150.0, 150.0)

    def test_bidirectional_edge(self):
        json_text = _make_json(
            objects=[
                _make_node(0, "a"),
                _make_node(1, "b"),
            ],
            edges=[{"tail": 0, "head": 1, "dir": "both"}],
        )
        graph = parse_xdot(json_text)
        assert graph.edges[0].is_bidirectional is True

    def test_edge_with_xlabel(self):
        json_text = _make_json(
            objects=[
                _make_node(0, "a"),
                _make_node(1, "b"),
            ],
            edges=[{"tail": 0, "head": 1, "xlabel": "ext label"}],
        )
        graph = parse_xdot(json_text)
        assert graph.edges[0].label == "ext label"


class TestParseXdotGraph:
    def test_bounding_box(self):
        json_text = _make_json(bb="0,0,1000,800")
        graph = parse_xdot(json_text)
        assert graph.bounding_box == (0.0, 0.0, 1000.0, 800.0)

    def test_empty_graph(self):
        json_text = _make_json()
        graph = parse_xdot(json_text)
        assert len(graph.nodes) == 0
        assert len(graph.clusters) == 0
        assert len(graph.edges) == 0
