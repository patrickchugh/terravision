"""Parse Graphviz JSON layout output into structured data for drawio emitter.

Runs the Graphviz `neato` engine with `-n2 -Tjson0` on a post-processed DOT
file to extract node positions, cluster bounding boxes, edge connections,
and custom TerraVision attributes (_titlenode, _footernode, etc.).
"""

import json
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class XdotNode:
    """A parsed node from Graphviz layout output."""

    id: str
    pos: Tuple[float, float]  # center position in points
    width: float  # in inches
    height: float  # in inches
    label: str = ""
    image: Optional[str] = None
    label_pos: Optional[Tuple[float, float]] = None
    attrs: Dict[str, str] = field(default_factory=dict)


@dataclass
class XdotCluster:
    """A parsed cluster/subgraph from Graphviz layout output."""

    name: str
    bb: Tuple[float, float, float, float]  # x1, y1, x2, y2 in points
    label: str = ""
    parent: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)


@dataclass
class XdotEdge:
    """A parsed edge from Graphviz layout output."""

    source: str
    target: str
    label: Optional[str] = None
    label_pos: Optional[Tuple[float, float]] = None
    is_bidirectional: bool = False
    spline_points: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class XdotGraph:
    """Complete parsed Graphviz layout output."""

    bounding_box: Tuple[float, float, float, float]
    nodes: Dict[str, XdotNode] = field(default_factory=dict)
    clusters: Dict[str, XdotCluster] = field(default_factory=dict)
    edges: List[XdotEdge] = field(default_factory=list)


def run_xdot(dot_file_path: str) -> str:
    """Run Graphviz neato to get JSON layout output from a post-processed DOT file.

    Uses ``neato -n2`` to preserve existing positions set by gvpr, and
    ``-Tjson0`` to produce structured JSON output.
    """
    result = subprocess.run(
        ["neato", "-n2", "-Tjson0", dot_file_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if result.stdout.strip():
            return result.stdout
        raise RuntimeError(f"Graphviz neato failed: {stderr}")
    return result.stdout


def parse_xdot(json_text: str) -> XdotGraph:
    """Parse Graphviz JSON layout output into an XdotGraph structure."""
    data = json.loads(json_text)

    bb = _parse_bb(data.get("bb", "0,0,100,100"))
    graph = XdotGraph(bounding_box=bb)

    gvid_to_name: Dict[int, str] = {}

    for obj in data.get("objects", []):
        _parse_object(obj, graph, gvid_to_name, parent=None)

    for edge_data in data.get("edges", []):
        source_id = gvid_to_name.get(
            edge_data.get("tail"), str(edge_data.get("tail", ""))
        )
        target_id = gvid_to_name.get(
            edge_data.get("head"), str(edge_data.get("head", ""))
        )

        label = edge_data.get("xlabel") or edge_data.get("label")
        label_pos = None
        if "lp" in edge_data:
            label_pos = _parse_pos(edge_data["lp"])

        is_bidi = edge_data.get("dir") == "both"

        # Parse edge spline control points from pos attribute
        spline_points = []
        pos_str = edge_data.get("pos", "")
        if pos_str:
            spline_points = _parse_edge_pos(pos_str)

        graph.edges.append(
            XdotEdge(
                source=source_id,
                target=target_id,
                label=label,
                label_pos=label_pos,
                is_bidirectional=is_bidi,
                spline_points=spline_points,
            )
        )

    return graph


def _parse_object(obj, graph, gvid_to_name, parent):
    """Parse a single object from the Graphviz JSON objects array.

    Objects can be subgraphs (clusters) that contain node references,
    or leaf nodes with position data.
    """
    gvid = obj.get("_gvid")
    name = obj.get("name", "")

    is_subgraph = "nodes" in obj or "subgraphs" in obj

    if is_subgraph:
        if name.startswith("cluster_"):
            bb_str = obj.get("bb")
            if bb_str:
                bb = _parse_bb(bb_str)
            else:
                bb = (0.0, 0.0, 100.0, 100.0)

            style_attrs = {}
            for k in (
                "color",
                "fillcolor",
                "style",
                "pencolor",
                "penwidth",
                "bgcolor",
            ):
                if k in obj:
                    style_attrs[k] = obj[k]

            cluster = XdotCluster(
                name=name,
                bb=bb,
                label=obj.get("label", ""),
                parent=parent,
                style=style_attrs,
            )
            graph.clusters[name] = cluster

        current_parent = name if name.startswith("cluster_") else parent

        for sub_obj in obj.get("objects", []):
            _parse_object(sub_obj, graph, gvid_to_name, parent=current_parent)
    else:
        if gvid is not None:
            gvid_to_name[gvid] = name

        pos_str = obj.get("pos")
        if not pos_str:
            return

        pos = _parse_pos(pos_str)
        width = float(obj.get("width", "1.0"))
        height = float(obj.get("height", "1.0"))

        custom_attrs = {}
        for key in (
            "_titlenode",
            "_footernode",
            "_legendnode",
            "_clusterlabel",
            "_edgenode",
            "_clusterid",
            "_clustertype",
            "_labelposition",
        ):
            if key in obj:
                custom_attrs[key] = obj[key]

        node = XdotNode(
            id=name,
            pos=pos,
            width=width,
            height=height,
            label=obj.get("label", name),
            image=obj.get("image"),
            label_pos=_parse_pos(obj["lp"]) if "lp" in obj else None,
            attrs=custom_attrs,
        )
        graph.nodes[name] = node


def _parse_bb(bb_str: str) -> Tuple[float, float, float, float]:
    """Parse bounding box string ``'x1,y1,x2,y2'`` into a float tuple."""
    parts = bb_str.split(",")
    return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))


def _parse_pos(pos_str: str) -> Tuple[float, float]:
    """Parse position string ``'x,y'`` or ``'x,y!'`` into a float tuple."""
    clean = pos_str.rstrip("!").strip()
    parts = clean.split(",")
    return (float(parts[0]), float(parts[1]))


def _parse_edge_pos(pos_str: str) -> List[Tuple[float, float]]:
    """Parse Graphviz edge ``pos`` attribute into a list of (x, y) points.

    Format: ``e,endx,endy startx,starty x1,y1 x2,y2 ...`` or
    ``s,startx,starty x1,y1 x2,y2 ... e,endx,endy``

    The ``e,`` and ``s,`` prefixes mark arrow endpoint/startpoint.
    We strip those and return all coordinate pairs in order.
    """
    points = []
    # Split on whitespace to get individual coordinate pairs
    for token in pos_str.strip().split():
        # Strip e, or s, prefix
        if token.startswith("e,") or token.startswith("s,"):
            token = token[2:]
        parts = token.split(",")
        if len(parts) == 2:
            try:
                points.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return points
