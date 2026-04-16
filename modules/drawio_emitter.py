"""Native draw.io (mxGraph XML) emitter for TerraVision.

Generates ``.drawio`` files directly from Graphviz layout data, using draw.io's
native provider shape libraries (AWS4, Azure, GCP) instead of embedded base64
PNG icons.  Falls back to embedded PNG for unmapped resource types.

Replaces the ``graphviz2drawio`` library dependency.
"""

import base64
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Set, Tuple

import modules.helpers as helpers
from modules.xdot_parser import XdotCluster, XdotEdge, XdotGraph, XdotNode

# Graphviz uses 72 DPI — 1 inch = 72 points.
DPI = 72.0

# Icon sizes matching draw.io's Sidebar-AWS4.js (s=1 scale factor).
# Direct shapes (instance2, lambda_function, etc.) use 48×48.
# resourceIcon shapes (ec2, s3, rds category icons) use 78×78.
DIRECT_ICON_SIZE = 56
RESICON_SIZE = 78
# Fallback for unmapped nodes.
DEFAULT_ICON_SIZE = 56

# Azure card: grey rounded rectangle behind SVG icon (matches PNG output).
AZURE_CARD_SIZE = 76
AZURE_CARD_ICON_SIZE = 40

# GCP card: bordered table with icon left, text right (matches PNG output).
GCP_CARD_WIDTH = 280
GCP_CARD_HEIGHT = 70
GCP_CARD_ICON_SIZE = 48
GCP_CARD_ICON_MARGIN = 12

# Padding inside cluster containers (pixels).
CLUSTER_PADDING = 10

# draw.io native group/container shapes for cluster types.
# These render with official provider styling (border colors, corner icons).
# Keys are the Python class names used in TerraVision's resource_classes.
# Values are (grIcon, strokeColor, fillColor, fontColor) tuples.
# Sourced from draw.io Sidebar-AWS4.js / Sidebar-Azure.js / Sidebar-GCP2.js.
# Values are (grIcon, strokeColor, fillColor, fontColor) tuples for groups
# that use draw.io's group;grIcon= pattern.
# For simple-styled groups (like AZ), use None as grIcon and the style is
# built from stroke/fill/font colors + dashed flag directly.
# Sourced from draw.io Sidebar-AWS4.js.
GROUP_SHAPE_MAP = {
    # AWS groups with grIcon (have corner icons in draw.io)
    "AWSGroup": ("group_aws_cloud", "#232F3E", "none", "#232F3E"),
    "VPCgroup": ("group_vpc2", "#8C4FFF", "none", "#AAB7B8"),
    "SubnetGroup": ("group_security_group", "#7AA116", "none", "#248814"),
    "RegionGroup": ("group_region", "#00A4A6", "none", "#147EBA"),
    "AccountGroup": ("group_account", "#CD2264", "none", "#CD2264"),
    "SpotFleetGroup": ("group_spot_fleet", "#D86613", "none", "#D86613"),
    "ElasticBeanstalkGroup": ("group_elastic_beanstalk", "#D86613", "none", "#D86613"),
    "StepFunctionsGroup": (
        "group_aws_step_functions_workflow",
        "#CD2264",
        "none",
        "#CD2264",
    ),
    "OnPremGroup": ("group_on_premise", "#7D8998", "none", "#5A6C86"),
    "CorporateDataCenterGroup": (
        "group_corporate_data_center",
        "#7D8998",
        "none",
        "#5A6C86",
    ),
}

# Groups that use simple box styling (no grIcon, just dashed/filled rectangle).
# Values are (strokeColor, fillColor, fontColor, dashed).
SIMPLE_GROUP_STYLE_MAP = {
    # AWS AZ — blue dashed border, no fill, no corner icon
    "AZGroup": ("#147EBA", "none", "#147EBA", True),
    "AvailabilityZone": ("#147EBA", "none", "#147EBA", True),
    # Security group — red solid border, no fill, no corner icon
    "SecurityGroup": ("#DD3522", "none", "#DD3522", False),
    "EC2SecurityGroup": ("#DD3522", "none", "#DD3522", False),
    # Generic group — gray dashed
    "GenericGroup": ("#5A6C86", "none", "#5A6C86", True),
    "SharedServicesGroup": ("#5A6C86", "#F5F5F5", "#5A6C86", True),
}

# Groups that use groupCenter style (icon centered at top, dashed border).
# Values are the exact draw.io style string from Sidebar-AWS4.js.
_PTS_2D = (
    "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],"
    "[1,0.25],[1,0.5],[1,0.75],[1,1],"
    "[0.75,1],[0.5,1],[0.25,1],[0,1],"
    "[0,0.75],[0,0.5],[0,0.25]]"
)
GROUP_CENTER_STYLE_MAP = {
    "AutoscalingGroup": (
        f"{_PTS_2D};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;"
        "fontSize=12;fontStyle=0;container=1;pointerEvents=0;collapsible=0;"
        "recursiveResize=0;shape=mxgraph.aws4.groupCenter;"
        "grIcon=mxgraph.aws4.group_auto_scaling_group;grStroke=1;"
        "strokeColor=#D86613;fillColor=none;verticalAlign=top;"
        "align=center;fontColor=#D86613;dashed=1;spacingTop=25;"
    ),
    "GenericAutoScalingGroup": (
        f"{_PTS_2D};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;"
        "fontSize=12;fontStyle=0;container=1;pointerEvents=0;collapsible=0;"
        "recursiveResize=0;shape=mxgraph.aws4.groupCenter;"
        "grIcon=mxgraph.aws4.group_auto_scaling_group;grStroke=1;"
        "strokeColor=#D86613;fillColor=none;verticalAlign=top;"
        "align=center;fontColor=#D86613;dashed=1;spacingTop=25;"
    ),
}


def _build_class_to_alias_map() -> Dict[str, str]:
    """Auto-generate ClassName → terraform_alias map from resource_classes.

    Scans all provider modules (aws, azure, gcp) for module-level alias
    assignments like ``aws_eip = ElasticIP`` and builds a reverse mapping
    so the emitter can resolve Graphviz node IDs to terraform resource types.
    """
    import importlib
    import inspect
    import pkgutil

    mapping: Dict[str, str] = {}
    for provider in ("aws", "azure", "gcp"):
        pkg_name = f"resource_classes.{provider}"
        try:
            pkg = importlib.import_module(pkg_name)
        except ModuleNotFoundError:
            continue

        # Scan all submodules in the provider package
        pkg_path = getattr(pkg, "__path__", None)
        if not pkg_path:
            continue
        modules_to_scan = [pkg]
        for _importer, modname, _ispkg in pkgutil.iter_modules(pkg_path):
            try:
                modules_to_scan.append(importlib.import_module(f"{pkg_name}.{modname}"))
            except Exception:
                continue

        for mod in modules_to_scan:
            for attr_name in dir(mod):
                # Skip private/dunder and non-alias names
                if attr_name.startswith("_"):
                    continue
                # Alias names look like terraform types: aws_*, azurerm_*, google_*, tv_*
                if not any(
                    attr_name.startswith(p)
                    for p in ("aws_", "azurerm_", "azuread_", "google_", "tv_", "gcp_")
                ):
                    continue
                obj = getattr(mod, attr_name, None)
                if obj is None or not inspect.isclass(obj):
                    continue
                class_name = obj.__name__
                # First alias wins (don't overwrite)
                if class_name not in mapping:
                    mapping[class_name] = attr_name

    return mapping


# Lazily cached class-to-alias mapping.
_CLASS_TO_ALIAS_CACHE: Optional[Dict[str, str]] = None


def _get_class_to_alias() -> Dict[str, str]:
    """Return the cached ClassName → terraform_alias map."""
    global _CLASS_TO_ALIAS_CACHE
    if _CLASS_TO_ALIAS_CACHE is None:
        _CLASS_TO_ALIAS_CACHE = _build_class_to_alias_map()
    return _CLASS_TO_ALIAS_CACHE


def load_shape_map(provider: str) -> dict:
    """Dynamically load the draw.io shape mapping for *provider*.

    Follows the CO-004 dynamic dispatch pattern used elsewhere in
    TerraVision for provider-specific configuration.
    """
    module_name = f"modules.config.drawio_shape_map_{provider}"
    try:
        import importlib

        mod = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return {}

    attr_name = f"DRAWIO_SHAPE_MAP_{provider.upper()}"
    return getattr(mod, attr_name, {})


def emit_drawio(
    xdot_graph: XdotGraph,
    shape_map: dict,
    icon_paths: Set[str],
    node_id_map: Dict[str, str],
    cluster_id_map: Dict[str, str],
    provider: str = "aws",
) -> str:
    """Convert parsed Graphviz layout data into mxGraph XML.

    Parameters
    ----------
    xdot_graph:
        Parsed layout data from :func:`xdot_parser.parse_xdot`.
    shape_map:
        Provider-specific resource-type → draw.io shape name mapping.
    icon_paths:
        Set of icon file paths referenced in the DOT file.
    node_id_map:
        Mapping of Graphviz node-name → TerraVision resource name.
    cluster_id_map:
        Mapping of Graphviz cluster-name → TerraVision resource name.
    """
    bb = xdot_graph.bounding_box
    graph_height = bb[3] - bb[1]

    # Build mxGraphModel XML
    mx_model = ET.Element("mxGraphModel")
    mx_model.set("dx", "1326")
    mx_model.set("dy", "798")
    mx_model.set("grid", "1")
    mx_model.set("gridSize", "10")
    mx_model.set("guides", "1")
    mx_model.set("tooltips", "1")
    mx_model.set("connect", "1")
    mx_model.set("arrows", "1")
    mx_model.set("fold", "1")
    mx_model.set("page", "0")
    mx_model.set("math", "0")
    mx_model.set("shadow", "0")

    root = ET.SubElement(mx_model, "root")

    # Root cells required by draw.io
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Track generated cell IDs for edge wiring
    cell_ids: Dict[str, str] = {}
    # Map cluster names to their cell IDs
    cluster_cell_ids: Dict[str, str] = {}

    cell_counter = [2]  # mutable counter for unique IDs

    def _next_id() -> str:
        cid = str(cell_counter[0])
        cell_counter[0] += 1
        return cid

    def _flip_y(gv_y: float) -> float:
        """Convert Graphviz Y (origin bottom-left) to draw.io Y (origin top-left)."""
        return graph_height - gv_y

    def _pts_to_px(inches: float) -> float:
        """Convert inches to pixels (at 72 DPI, 1 inch = 72 px)."""
        return inches * DPI

    # ── Clusters ──────────────────────────────────────────────────────
    # Sort clusters so parents are emitted before children.
    sorted_clusters = _topo_sort_clusters(xdot_graph.clusters)

    # Store absolute draw.io top-left position of each cluster
    # so child clusters and nodes can compute relative offsets.
    cluster_abs_pos: Dict[str, Tuple[float, float]] = {}

    for cluster_name in sorted_clusters:
        cluster = xdot_graph.clusters[cluster_name]
        cid = _next_id()
        cluster_cell_ids[cluster_name] = cid

        # Determine parent cell
        parent_id = "1"
        if cluster.parent and cluster.parent in cluster_cell_ids:
            parent_id = cluster_cell_ids[cluster.parent]

        # Bounding box → absolute draw.io coords
        x1, y1, x2, y2 = cluster.bb
        abs_x = x1
        abs_y = _flip_y(y2)  # top-left in draw.io coords
        dx_w = x2 - x1
        dx_h = y2 - y1

        # Add bottom padding for clusters that have label nodes (icons
        # at bottom) so child containers don't obscure them.
        has_label_node = any(
            n.attrs.get("_clusterlabel") == "1"
            and n.attrs.get("_clusterid") == cluster_name
            for n in xdot_graph.nodes.values()
        )
        if has_label_node:
            dx_h += 50

        cluster_abs_pos[cluster_name] = (abs_x, abs_y)

        # draw.io geometry is relative to immediate parent only
        dx_x = abs_x
        dx_y = abs_y
        if cluster.parent and cluster.parent in cluster_abs_pos:
            px, py = cluster_abs_pos[cluster.parent]
            dx_x = abs_x - px
            dx_y = abs_y - py

        # Cluster style — use native draw.io group shape if available
        # Extract class name from cluster name (e.g., "cluster_VPCgroup.123" → "VPCgroup")
        class_name = cluster_name.replace("cluster_", "").split(".")[0]
        # AWS-specific group shapes; non-AWS providers use generic dashed style
        # with colors from the DOT file (set by resource_classes group definitions)
        group_shape = GROUP_SHAPE_MAP.get(class_name) if provider == "aws" else None
        center_style = (
            GROUP_CENTER_STYLE_MAP.get(class_name) if provider == "aws" else None
        )
        simple_style = (
            SIMPLE_GROUP_STYLE_MAP.get(class_name) if provider == "aws" else None
        )

        if center_style:
            # groupCenter — exact raw style from Sidebar-AWS4.js
            style_str = center_style
        elif group_shape:
            gr_icon, stroke_c, fill_c, font_c = group_shape
            style_parts = [
                "sketch=0",
                "outlineConnect=0",
                "gradientColor=none",
                "html=1",
                "whiteSpace=wrap",
                "fontSize=12",
                "fontStyle=0",
                "shape=mxgraph.aws4.group",
                f"grIcon=mxgraph.aws4.{gr_icon}",
                f"strokeColor={stroke_c}",
                f"fillColor={fill_c}",
                "verticalAlign=top",
                "align=left",
                "spacingLeft=30",
                f"fontColor={font_c}",
                "dashed=0",
                "container=1",
                "collapsible=0",
                "recursiveResize=0",
                "pointerEvents=0",
            ]
        elif simple_style:
            stroke_c, fill_c, font_c, is_dashed = simple_style
            style_parts = [
                f"fillColor={fill_c}",
                f"strokeColor={stroke_c}",
                f"dashed={'1' if is_dashed else '0'}",
                "verticalAlign=top",
                "fontStyle=0",
                f"fontColor={font_c}",
                "whiteSpace=wrap",
                "html=1",
                "container=1",
                "collapsible=0",
            ]
        else:
            raw_style = cluster.style.get("style", "")
            is_invisible = "invis" in raw_style
            stroke = cluster.style.get(
                "color", cluster.style.get("pencolor", "#666666")
            )
            fill = cluster.style.get("fillcolor", cluster.style.get("bgcolor", "none"))
            is_dashed = "dashed" in raw_style
            if is_invisible:
                stroke = "none"
                fill = "none"
            style_parts = [
                "rounded=1",
                "arcSize=3",
                "whiteSpace=wrap",
                "html=1",
                f"fillColor={fill}",
                f"strokeColor={stroke}",
                f"dashed={'1' if is_dashed else '0'}",
                "verticalAlign=top",
                "align=left",
                "spacingLeft=10",
                "spacingTop=5",
                "fontStyle=1",
                "fontSize=14",
                "container=1",
                "collapsible=0",
            ]

        if not center_style:
            style_str = ";".join(style_parts) + ";"

        # Handle cluster labels — for non-AWS providers, if the label is an
        # HTML table with only an image (cloud provider logo), clear the text
        # and emit the logo as a separate child cell after all clusters.
        # AWS keeps its cluster label text ("AWS Cloud") as-is.
        raw_label = cluster.label or ""
        if provider != "aws" and ("<IMG" in raw_label.upper() or "<img" in raw_label):
            label = ""
        else:
            label = _sanitize_label(raw_label)

        cell = ET.SubElement(
            root,
            "mxCell",
            id=cid,
            value=label,
            style=style_str,
            vertex="1",
            parent=parent_id,
        )
        geo = ET.SubElement(
            cell,
            "mxGeometry",
            x=f"{dx_x:.1f}",
            y=f"{dx_y:.1f}",
            width=f"{dx_w:.1f}",
            height=f"{dx_h:.1f}",
        )
        geo.set("as", "geometry")

    # ── Cluster logo images (provider logos at bottom of cloud group) ──
    # AWS doesn't use provider logos in clusters.
    if provider != "aws":
        for cluster_name in sorted_clusters:
            cluster = xdot_graph.clusters[cluster_name]
            raw_label = cluster.label or ""
            if "<IMG" not in raw_label.upper() and "<img" not in raw_label:
                continue
            # Extract image path from HTML label
            img_match = re.search(r'<IMG\s+SRC="([^"]+)"', raw_label, re.IGNORECASE)
            if not img_match or not os.path.isfile(img_match.group(1)):
                continue
            icon_path = img_match.group(1)
            icon_basename = os.path.basename(icon_path)
            logo_size = _LOGO_ICON_SIZES.get(icon_basename, (180, 32))

            b64 = _encode_icon_base64(icon_path)
            logo_id = _next_id()
            logo_style = (
                f"shape=image;imageAspect=0;aspect=fixed;"
                f"verticalLabelPosition=bottom;verticalAlign=top;"
                f"image=data:image/png,{b64};"
            )
            # Position at bottom-left of parent cluster
            x1, y1, x2, y2 = cluster.bb
            cluster_w = x2 - x1
            cluster_h = y2 - y1
            w_px, h_px = logo_size
            margin = 15
            logo_x = margin
            logo_y = cluster_h - h_px - margin

            parent_cid = cluster_cell_ids.get(cluster_name, "1")
            logo_cell = ET.SubElement(
                root,
                "mxCell",
                id=logo_id,
                value="",
                style=logo_style,
                vertex="1",
                parent=parent_cid,
            )
            logo_geo = ET.SubElement(
                logo_cell,
                "mxGeometry",
                x=f"{logo_x:.1f}",
                y=f"{logo_y:.1f}",
                width=f"{w_px:.1f}",
                height=f"{h_px:.1f}",
            )
            logo_geo.set("as", "geometry")

    # ── Nodes ─────────────────────────────────────────────────────────
    footer_label = ""
    _title_cell_id = None
    _title_node = None

    for node_name, node in xdot_graph.nodes.items():
        cid = _next_id()
        cell_ids[node_name] = cid

        # Determine if this is a special node
        is_title = node.attrs.get("_titlenode") == "1"
        is_footer = node.attrs.get("_footernode") == "1"
        is_legend = node.attrs.get("_legendnode") == "1"
        is_cluster_label = node.attrs.get("_clusterlabel") == "1"

        # Find innermost parent cluster (smallest area that contains node)
        parent_id = "1"
        parent_cluster = None
        if not (is_title or is_footer or is_legend):
            parent_cluster = _find_innermost_cluster(node, xdot_graph.clusters)
            if parent_cluster and parent_cluster.name in cluster_cell_ids:
                parent_id = cluster_cell_ids[parent_cluster.name]

        # Node center in Graphviz coords
        cx, cy = node.pos

        if is_footer:
            # Skip footer — its content is merged into the title as a subtitle
            footer_label = _sanitize_label(node.label)
            continue
        elif is_title:
            # Title node — will have footer subtitle appended below
            style_str = _build_special_node_style(node)
            label = _sanitize_label(node.label)
            # Store title cell ID so we can append footer subtitle later
            _title_cell_id = cid
            _title_node = node
            parent_id = "1"
            w_px = _pts_to_px(node.width)
            h_px = _pts_to_px(node.height)
        elif is_legend:
            style_str = _build_special_node_style(node)
            label = _sanitize_label(node.label)
            parent_id = "1"
            w_px = _pts_to_px(node.width)
            h_px = _pts_to_px(node.height)
        elif is_cluster_label:
            # Defer cluster labels to emit AFTER all other cells
            # so they render on top (z-order = XML order in draw.io)
            continue
        else:
            # Regular resource node — extract terraform resource type.
            # First try node_id_map (Graphviz ID → terraform address).
            # If not found, try the Python class alias from the Graphviz
            # node name (e.g., "aws.compute.ElasticIP.xxx" → "aws_eip").
            resource_name = node_id_map.get(node_name, "")
            if resource_name:
                no_module = helpers.get_no_module_name(resource_name) or resource_name
                resource_type = (
                    no_module.split(".")[0] if "." in no_module else no_module
                )
            else:
                # Fallback: extract class alias from Graphviz node ID
                # Format: "provider.category.ClassName.uuid"
                parts = node_name.split(".")
                if len(parts) >= 3:
                    class_name = parts[-2]  # e.g., "ElasticIP"
                    # Map Python class name to terraform alias using
                    # auto-generated mapping from resource_classes.
                    class_alias_map = _get_class_to_alias()
                    resource_type = class_alias_map.get(class_name, class_name)
                    if resource_type == class_name:
                        # Try automated match
                        class_lower = class_name.lower()
                        for alias in shape_map:
                            stripped = alias.replace("aws_", "").replace("tv_aws_", "")
                            compact = stripped.replace("_", "").lower()
                            if class_lower == compact:
                                resource_type = alias
                                break
                else:
                    resource_type = node_name
            if "~" in resource_type:
                resource_type = resource_type.split("~")[0]

            # GCP table card: bordered card with PNG icon left, text right
            if provider == "gcp":
                _emit_gcp_card(
                    root,
                    cid,
                    node,
                    resource_type,
                    node.label or "",
                    parent_id,
                    parent_cluster,
                    cluster_abs_pos,
                    _flip_y,
                )
                continue

            style_str, w_px, h_px = _build_node_style(
                resource_type, node, shape_map, provider
            )
            label = _sanitize_label(node.label)

        # Compute absolute draw.io position (top-left of node)
        dx_x = cx - w_px / 2
        dx_y = _flip_y(cy) - h_px / 2

        # Convert to coordinates relative to immediate parent container
        if parent_cluster and parent_cluster.name in cluster_abs_pos:
            px, py = cluster_abs_pos[parent_cluster.name]
            dx_x -= px
            dx_y -= py

        cell = ET.SubElement(
            root,
            "mxCell",
            id=cid,
            value=label,
            style=style_str,
            vertex="1",
            parent=parent_id,
        )
        geo = ET.SubElement(
            cell,
            "mxGeometry",
            x=f"{dx_x:.1f}",
            y=f"{dx_y:.1f}",
            width=f"{w_px:.1f}",
            height=f"{h_px:.1f}",
        )
        geo.set("as", "geometry")

    # ── Footer subtitle (below title) ────────────────────────────────
    if footer_label and _title_node:
        subtitle_id = _next_id()
        # Convert record syntax to one-line subtitle
        subtitle_text = _convert_record_to_html(footer_label)
        # Replace <br> with " | " for a compact single line
        subtitle_text = subtitle_text.replace("<b>", "").replace("</b>", "")
        subtitle_text = subtitle_text.replace("<br>", " &nbsp;|&nbsp; ")
        # Position just below the title
        tcx, tcy = _title_node.pos
        sub_y = _flip_y(tcy) + _pts_to_px(_title_node.height) / 2 + 5
        sub_x = tcx - 300
        subtitle_style = (
            "text;html=1;align=center;verticalAlign=top;"
            "resizable=0;points=[];autosize=1;strokeColor=none;"
            "fillColor=none;fontSize=16;fontColor=#999999;"
        )
        sub_cell = ET.SubElement(
            root,
            "mxCell",
            id=subtitle_id,
            value=subtitle_text,
            style=subtitle_style,
            vertex="1",
            parent="1",
        )
        sub_geo = ET.SubElement(
            sub_cell,
            "mxGeometry",
            x=f"{sub_x:.1f}",
            y=f"{sub_y:.1f}",
            width="600",
            height="30",
        )
        sub_geo.set("as", "geometry")

    # ── Cluster labels (emitted last for z-order — on top of children) ──
    for node_name, node in xdot_graph.nodes.items():
        if node.attrs.get("_clusterlabel") != "1":
            continue
        cid = _next_id()
        cell_ids[node_name] = cid

        style_str, label, w_px, h_px = _build_cluster_label_style(node, shape_map)
        # Use absolute positioning (parent="1") so icons render on top of
        # all child containers.  Relative positioning inside clusters
        # causes icons to be obscured by overlapping child containers.
        parent_id = "1"
        clid = node.attrs.get("_clusterid", "")

        # Position based on _labelposition relative to parent cluster bounds
        label_pos = node.attrs.get("_labelposition", "bottom-left")
        parent_cluster = None
        if clid:
            for cname, cl in xdot_graph.clusters.items():
                if cname == clid:
                    parent_cluster = cl
                    break

        if parent_cluster:
            x1, y1, x2, y2 = parent_cluster.bb
            cluster_w = x2 - x1
            cluster_h = y2 - y1 + 50  # padded height
            # Absolute position: cluster origin + offset within cluster
            abs_x = x1
            abs_y = _flip_y(y2)
            margin = 10
            if "left" in label_pos:
                dx_x = abs_x + margin
            elif "right" in label_pos:
                dx_x = abs_x + cluster_w - w_px - margin
            else:  # center
                dx_x = abs_x + (cluster_w - w_px) / 2
            # Always at bottom of padded area
            dx_y = abs_y + cluster_h - h_px - margin
        else:
            cx, cy = node.pos
            dx_x = cx - w_px / 2
            dx_y = _flip_y(cy) - h_px / 2

        cell = ET.SubElement(
            root,
            "mxCell",
            id=cid,
            value=label,
            style=style_str,
            vertex="1",
            parent=parent_id,
        )
        geo = ET.SubElement(
            cell,
            "mxGeometry",
            x=f"{dx_x:.1f}",
            y=f"{dx_y:.1f}",
            width=f"{w_px:.1f}",
            height=f"{h_px:.1f}",
        )
        geo.set("as", "geometry")

    # ── Edges ─────────────────────────────────────────────────────────
    for edge in xdot_graph.edges:
        eid = _next_id()
        source_cid = cell_ids.get(edge.source)
        target_cid = cell_ids.get(edge.target)
        if not source_cid or not target_cid:
            continue

        # Use the edge color from the DOT if available, else default
        style_parts = [
            "html=1",
            "edgeStyle=orthogonalEdgeStyle",
            "rounded=0",
            "orthogonalLoop=1",
            "jettySize=auto",
            "strokeColor=#7B8894",
            "endArrow=classic",
            "endFill=1",
        ]
        if edge.is_bidirectional:
            style_parts.append("startArrow=classic")
            style_parts.append("startFill=1")
        style_str = ";".join(style_parts) + ";"

        label = _sanitize_label(edge.label) if edge.label else ""

        edge_cell = ET.SubElement(
            root,
            "mxCell",
            id=eid,
            value=label,
            style=style_str,
            edge="1",
            parent="1",
            source=source_cid,
            target=target_cid,
        )
        geo = ET.SubElement(edge_cell, "mxGeometry", relative="1")
        geo.set("as", "geometry")

        # Let draw.io's orthogonalEdgeStyle handle routing natively.
        # Graphviz spline waypoints caused edges to cross through containers.

    # Wrap in draw.io's <mxfile><diagram> structure for full compatibility
    ET.indent(mx_model, space="      ")
    graph_xml = ET.tostring(mx_model, encoding="unicode")

    xml_str = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mxfile host="TerraVision" agent="TerraVision" version="1.0">\n'
        '  <diagram id="terravision" name="Architecture">\n'
        f"    {graph_xml}\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )
    return xml_str


# ── Style builders ────────────────────────────────────────────────────


def _build_node_style(
    resource_type: str,
    node: XdotNode,
    shape_map: dict,
    provider: str = "aws",
) -> Tuple[str, int, int]:
    """Build an mxCell style string for a resource node.

    Returns ``(style_string, width_px, height_px)`` so the caller can set
    the correct geometry dimensions.

    Priority:
    1. AWS: Direct shape or resourceIcon with correct fill colour
    2. Azure: Grey card with SVG image (``shape=label``)
    3. GCP: Handled separately in emit loop (table card); falls back here
    4. Fallback: Generic rounded rectangle as last resort.
    """
    from modules.config.drawio_aws4_shapes import (
        AWS4_DIRECT_SHAPE_NAMES,
        AWS4_DIRECT_SHAPE_FILLS,
        AWS4_RESICON_NAMES,
    )
    from modules.config.drawio_resicon_colors import AWS_RESICON_FILL_COLORS

    drawio_shape = shape_map.get(resource_type)

    if drawio_shape:
        shape_ref = drawio_shape.replace(" ", "_")
        bare_name = (
            shape_ref.replace("mxgraph.aws4.", "")
            .replace("mxgraph.azure.", "")
            .replace("mxgraph.gcp2.", "")
        )

        # Azure shapes: grey rounded card with SVG icon inside
        if "img/lib/azure2/" in drawio_shape:
            parts = [
                "shape=label",
                "rounded=1",
                "arcSize=10",
                "fillColor=#F2F2F2",
                "strokeColor=#E0E0E0",
                "html=1",
                "align=center",
                "verticalLabelPosition=bottom",
                "verticalAlign=top",
                "fontSize=12",
                "fontColor=#2C2C2C",
                f"image={drawio_shape}",
                f"imageWidth={AZURE_CARD_ICON_SIZE}",
                f"imageHeight={AZURE_CARD_ICON_SIZE}",
                "imageAlign=center",
                "imageVerticalAlign=middle",
                "spacingTop=4",
                "spacing=6",
            ]
            return ";".join(parts) + ";", AZURE_CARD_SIZE, AZURE_CARD_SIZE

        # Connection points used by draw.io for resourceIcon shapes
        _PTS = (
            "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],"
            "[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],"
            "[0,0.25,0],[0,0.5,0],[0,0.75,0],"
            "[1,0.25,0],[1,0.5,0],[1,0.75,0]]"
        )

        if bare_name in AWS4_DIRECT_SHAPE_NAMES:
            # Direct shape — exact style from draw.io Sidebar-AWS4.js
            fill = AWS4_DIRECT_SHAPE_FILLS.get(bare_name, "#232F3E")
            parts = [
                "sketch=0",
                "outlineConnect=0",
                "fontColor=#232F3E",
                "gradientColor=none",
                f"fillColor={fill}",
                "strokeColor=none",
                "dashed=0",
                "verticalLabelPosition=bottom",
                "verticalAlign=top",
                "align=center",
                "html=1",
                "fontSize=12",
                "fontStyle=0",
                "aspect=fixed",
                "pointerEvents=1",
                f"shape={shape_ref}",
            ]
            return ";".join(parts) + ";", DIRECT_ICON_SIZE, DIRECT_ICON_SIZE

        if bare_name in AWS4_RESICON_NAMES:
            # resourceIcon — exact style from draw.io Sidebar-AWS4.js
            fill = AWS_RESICON_FILL_COLORS.get(bare_name, "#232F3E")
            parts = [
                "sketch=0",
                _PTS,
                "outlineConnect=0",
                "fontColor=#232F3E",
                f"fillColor={fill}",
                "strokeColor=#ffffff",
                "dashed=0",
                "verticalLabelPosition=bottom",
                "verticalAlign=top",
                "align=center",
                "html=1",
                "fontSize=12",
                "fontStyle=0",
                "aspect=fixed",
                "shape=mxgraph.aws4.resourceIcon",
                f"resIcon={shape_ref}",
            ]
            return ";".join(parts) + ";", RESICON_SIZE, RESICON_SIZE

        # Shape name not in either set — try direct with default fill
        parts = [
            "sketch=0",
            "outlineConnect=0",
            "fontColor=#232F3E",
            "gradientColor=none",
            "fillColor=#232F3E",
            "strokeColor=none",
            "dashed=0",
            "verticalLabelPosition=bottom",
            "verticalAlign=top",
            "align=center",
            "html=1",
            "fontSize=12",
            "fontStyle=0",
            "aspect=fixed",
            f"shape={shape_ref}",
        ]
        return ";".join(parts) + ";", DIRECT_ICON_SIZE, DIRECT_ICON_SIZE

    # No shape map entry — generic rectangle
    parts = [
        "rounded=1",
        "whiteSpace=wrap",
        "html=1",
        "fillColor=#dae8fc",
        "strokeColor=#6c8ebf",
        "verticalLabelPosition=bottom",
        "verticalAlign=top",
        "align=center",
    ]

    return ";".join(parts) + ";", DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE


def _build_special_node_style(node: XdotNode) -> str:
    """Build style for title / footer / legend nodes."""
    is_title = node.attrs.get("_titlenode") == "1"
    if is_title:
        return (
            "text;html=1;align=center;verticalAlign=middle;"
            "resizable=0;points=[];autosize=1;strokeColor=none;"
            "fillColor=none;fontSize=28;fontStyle=1;fontColor=#2D3436;"
        )
    # Footer and legend
    return (
        "text;html=1;align=left;verticalAlign=middle;"
        "resizable=0;points=[];autosize=1;strokeColor=none;"
        "fillColor=none;fontSize=14;fontColor=#666666;"
    )


# Map TerraVision PNG icon basenames to draw.io SVG paths for cluster labels.
# This avoids fragile fuzzy matching — just hardcode known icon filenames.
_ICON_TO_DRAWIO_SVG = {
    # Azure cluster label icons
    "subnet.png": "img/lib/azure2/networking/Subnet.svg",
    "virtual-networks.png": "img/lib/azure2/networking/Virtual_Networks_Classic.svg",
    "resource-groups.png": "img/lib/azure2/general/Resource_Groups.svg",
    "network-security-groups.png": "img/lib/azure2/networking/Network_Security_Groups.svg",
    # Azure logo — base64-embed the local PNG (it includes "Microsoft Azure" text)
    "azure.png": None,
    # AWS cluster label icons — base64-embed
    "vpc.png": None,
    "private_subnet.png": None,
    "public_subnet.png": None,
    "aws.png": None,
}

# Cluster label icons that are logos (contain text, need larger sizing).
# Values are (width, height) in pixels.
_LOGO_ICON_SIZES = {
    "azure.png": (200, 112),  # 500x281 original, scaled to fit
    "gcp.png": (180, 32),  # 384x68 original, scaled to fit
    "aws.png": (150, 90),
}


def _build_cluster_label_style(
    node: XdotNode, shape_map: Optional[dict] = None
) -> Tuple[str, str, int, int]:
    """Build style and label for cluster label nodes with optional icons.

    Parses HTML-table labels to extract image paths and text.
    If a draw.io SVG path exists for the icon, uses that.
    Otherwise base64-encodes the local PNG.
    Returns (style_string, sanitized_label, width, height).
    """
    label = node.label
    # Try to extract image path and text from HTML label
    img_match = re.search(r'<img\s+src="([^"]+)"', label, re.IGNORECASE)
    # Get ALL text content from TD elements
    text_parts = re.findall(r"<td[^>]*>([^<]+)</td>", label, re.IGNORECASE)
    clean_label = " ".join(t.strip() for t in text_parts if t.strip())

    w_px = 40
    h_px = 40

    if img_match:
        icon_path = img_match.group(1)
        icon_basename = os.path.basename(icon_path)

        # Direct lookup from known PNG filename → draw.io SVG path
        svg_path = _ICON_TO_DRAWIO_SVG.get(icon_basename)

        # Check if this is a logo icon (needs larger sizing, no label text)
        logo_size = _LOGO_ICON_SIZES.get(icon_basename)

        if svg_path:
            # Use draw.io's built-in SVG
            style = (
                f"image;aspect=fixed;html=1;points=[];align=center;"
                f"fontSize=10;image={svg_path};"
            )
        elif os.path.isfile(icon_path):
            b64 = _encode_icon_base64(icon_path)
            if logo_size:
                # Logo icon — standalone image, no label text
                w_px, h_px = logo_size
                clean_label = ""
                style = (
                    f"shape=image;imageAspect=0;aspect=fixed;"
                    f"verticalLabelPosition=bottom;verticalAlign=top;"
                    f"image=data:image/png,{b64};"
                )
            else:
                style = (
                    f"shape=image;html=1;verticalAlign=top;"
                    f"verticalLabelPosition=bottom;labelBackgroundColor=default;"
                    f"imageAspect=0;aspect=fixed;"
                    f"image=data:image/png,{b64};"
                    f"fontSize=10;fontColor=#232F3E;"
                )
        else:
            style = (
                "text;html=1;align=left;verticalAlign=middle;"
                "resizable=0;points=[];autosize=1;strokeColor=none;"
                "fillColor=none;fontSize=10;fontStyle=1;fontColor=#232F3E;"
            )
    else:
        style = (
            "text;html=1;align=left;verticalAlign=middle;"
            "resizable=0;points=[];autosize=1;strokeColor=none;"
            "fillColor=none;fontSize=10;fontStyle=1;fontColor=#232F3E;"
        )
        if not clean_label:
            clean_label = _sanitize_label(label)

    return style, clean_label, w_px, h_px


# ── GCP table-card helpers ────────────────────────────────────────────


def _format_gcp_label(raw_label: str, resource_type: str) -> str:
    """Format a GCP node label with bold service name and regular resource name.

    Extracts bold/regular parts directly from the Graphviz HTML label, which
    already uses ``<B>`` tags to mark the service name (set by GCP's
    ``resource_classes/gcp/__init__.py``).
    """
    label = str(raw_label)

    # Extract bold text (service name) from <B>...</B> tags
    bold_match = re.search(r"<B>([^<]+)</B>", label, re.IGNORECASE)

    if bold_match:
        service_name = bold_match.group(1).strip()

        # Extract all non-bold text from FONT/TD elements (resource name)
        # Remove everything up to and including the </B> to get remaining text
        after_bold = label[bold_match.end() :]
        # Get text from remaining TD/FONT elements
        remaining_texts = re.findall(
            r"<(?:FONT|TD)[^>]*>([^<]+)</(?:FONT|TD)>", after_bold, re.IGNORECASE
        )
        resource_name = " ".join(t.strip() for t in remaining_texts if t.strip())

        if service_name and resource_name:
            return f"<b>{service_name}</b><br>{resource_name}"
        elif service_name:
            return f"<b>{service_name}</b>"

    # Fallback: extract all text and bold it
    clean = _extract_text_from_html(label)
    if not clean:
        clean = resource_type.replace("google_", "").replace("_", " ").title()
    return f"<b>{clean}</b>"


def _emit_gcp_card(
    root: ET.Element,
    card_id: str,
    node: XdotNode,
    resource_type: str,
    raw_label: str,
    parent_id: str,
    parent_cluster: Optional[XdotCluster],
    cluster_abs_pos: Dict[str, Tuple[float, float]],
    flip_y_fn,
) -> None:
    """Emit a GCP table-card node: bordered card with PNG icon left, text right.

    Uses ``shape=label`` with a base64-embedded PNG icon extracted from the
    Graphviz HTML label.  Matches the PNG output's two-column table card.
    """
    card_w = GCP_CARD_WIDTH
    card_h = GCP_CARD_HEIGHT
    icon_size = GCP_CARD_ICON_SIZE
    icon_margin = GCP_CARD_ICON_MARGIN

    # Compute card top-left position (centered on node position)
    cx, cy = node.pos
    card_x = cx - card_w / 2
    card_y = flip_y_fn(cy) - card_h / 2

    # Relative to parent container
    if parent_cluster and parent_cluster.name in cluster_abs_pos:
        px, py = cluster_abs_pos[parent_cluster.name]
        card_x -= px
        card_y -= py

    # Format label for right side of card
    gcp_label = _format_gcp_label(raw_label, resource_type)

    # Extract icon path from the Graphviz HTML label and base64-encode it
    img_match = re.search(r'<IMG\s+SRC="([^"]+)"', raw_label, re.IGNORECASE)
    if not img_match:
        img_match = re.search(r'<img\s+src="([^"]+)"', raw_label, re.IGNORECASE)

    spacing_left = icon_size + icon_margin * 2
    if img_match and os.path.isfile(img_match.group(1)):
        icon_b64 = _encode_icon_base64(img_match.group(1))
        card_style = (
            f"shape=label;rounded=0;strokeColor=#DDDDDD;fillColor=none;"
            f"html=1;whiteSpace=wrap;"
            f"image=data:image/png,{icon_b64};"
            f"imageWidth={icon_size};imageHeight={icon_size};"
            f"imageAlign=left;imageVerticalAlign=middle;"
            f"align=left;verticalAlign=middle;"
            f"spacingLeft={spacing_left};fontSize=12;fontColor=#2D3436;"
        )
    else:
        # No icon available — plain card
        card_style = (
            "rounded=0;strokeColor=#DDDDDD;fillColor=none;"
            "html=1;whiteSpace=wrap;"
            "align=left;verticalAlign=middle;"
            "fontSize=12;fontColor=#2D3436;"
        )

    card_cell = ET.SubElement(
        root,
        "mxCell",
        id=card_id,
        value=gcp_label,
        style=card_style,
        vertex="1",
        parent=parent_id,
    )
    card_geo = ET.SubElement(
        card_cell,
        "mxGeometry",
        x=f"{card_x:.1f}",
        y=f"{card_y:.1f}",
        width=f"{card_w:.1f}",
        height=f"{card_h:.1f}",
    )
    card_geo.set("as", "geometry")


# ── Helpers ───────────────────────────────────────────────────────────


def _extract_text_from_html(html: str) -> str:
    """Extract visible text from a Graphviz HTML-table label.

    Strips ``<TABLE>``, ``<TR>``, ``<TD>``, ``<IMG>``, ``<FONT>`` etc.
    and returns only the human-readable text content.
    """
    text = html
    # Strip Graphviz HTML-label outer delimiters: <<TABLE...>> → <TABLE...>
    if text.startswith("<<") and text.endswith(">>"):
        text = text[1:-1]
    # Remove all HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove any stray angle brackets (from Graphviz delimiters)
    text = text.replace("<", "").replace(">", "")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _convert_record_to_html(record: str) -> str:
    """Convert Graphviz record label syntax to HTML for draw.io.

    Record syntax uses ``|`` for column separation and ``{ }`` for row
    stacking.  Example::

        "Title|{ Timestamp:|Source: }|{ 2026-04-16|path/to/src }"

    Output::

        "<b>Title</b><br>Timestamp: 2026-04-16<br>Source: path/to/src"
    """
    # Split into top-level groups by matching { ... } blocks
    groups: list = []
    current = ""
    depth = 0
    for ch in record:
        if ch == "{":
            depth += 1
            current += ch
        elif ch == "}":
            depth -= 1
            current += ch
        elif ch == "|" and depth == 0:
            groups.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        groups.append(current.strip())

    # First group is the title
    if not groups:
        return record

    title = groups[0].strip("{} ")
    result = f"<b>{title}</b>"

    # Remaining groups contain { field1|field2|... } blocks
    # Collect all blocks, split their contents, then zip keys+values
    block_contents: list = []
    for g in groups[1:]:
        inner = g.strip("{} ")
        block_contents.append([f.strip() for f in inner.split("|")])

    # Zip across blocks: block[0] has keys, block[1] has values, etc.
    if len(block_contents) >= 2:
        keys = block_contents[0]
        values = block_contents[1]
        for k, v in zip(keys, values):
            result += f"<br>{k} {v}"
    elif len(block_contents) == 1:
        for item in block_contents[0]:
            result += f"<br>{item}"

    return result


def _encode_icon_base64(icon_path: str) -> str:
    """Read an icon file and return its base64-encoded content."""
    with open(icon_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _sanitize_label(label: Optional[str]) -> str:
    """Strip HTML wrapper and escape XML-unsafe characters in a label."""
    if not label:
        return ""
    text = label
    # Remove Graphviz HTML-label delimiters << >>
    # Graphviz wraps HTML labels in << >>, so strip both layers.
    while text.startswith("<") and text.endswith(">"):
        inner = text[1:-1]
        if inner.startswith("<") or "<TABLE" in inner.upper():
            text = inner
        else:
            break
    # For complex HTML labels, extract just the visible text content
    if "<TABLE" in text.upper() or "<table" in text:
        return _extract_text_from_html(text)
    # Convert Graphviz record syntax to HTML line breaks
    # e.g., "Title|{ Key:|Value }|{ Key2:|Value2 }" → "Title<br>Key: Value<br>..."
    if "|{" in text or "|}|" in text:
        text = _convert_record_to_html(text)
        return text
    # Escape XML specials (ET handles this, but be safe for value= attrs)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def _node_inside_cluster(node: XdotNode, cluster: XdotCluster) -> bool:
    """Check if a node's position falls within a cluster's bounding box."""
    cx, cy = node.pos
    x1, y1, x2, y2 = cluster.bb
    return x1 <= cx <= x2 and y1 <= cy <= y2


def _find_innermost_cluster(
    node: XdotNode, clusters: Dict[str, XdotCluster]
) -> Optional[XdotCluster]:
    """Find the smallest (innermost) cluster that contains the node."""
    best = None
    best_area = float("inf")
    for cluster in clusters.values():
        if _node_inside_cluster(node, cluster):
            x1, y1, x2, y2 = cluster.bb
            area = (x2 - x1) * (y2 - y1)
            if area < best_area:
                best_area = area
                best = cluster
    return best


def _topo_sort_clusters(
    clusters: Dict[str, XdotCluster],
) -> list:
    """Sort clusters so that parents appear before children."""
    sorted_names: list = []
    visited: set = set()

    def _visit(name: str):
        if name in visited:
            return
        visited.add(name)
        cluster = clusters.get(name)
        if cluster and cluster.parent and cluster.parent in clusters:
            _visit(cluster.parent)
        sorted_names.append(name)

    for name in clusters:
        _visit(name)

    return sorted_names
