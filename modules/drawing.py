"""Drawing module for TerraVision.

This module handles the rendering of Terraform infrastructure as architecture diagrams.
It processes the graph data structure and creates visual representations using Graphviz,
including nodes, clusters, connections, and edge labels.
"""

import base64
import datetime
import importlib
import os
import pkgutil
import re
import subprocess
import sys
import warnings
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any, Optional

import click

try:
    _TERRAVISION_VERSION = version("terravision")
except PackageNotFoundError:
    _TERRAVISION_VERSION = "dev"

import modules.config_loader as config_loader
import modules.helpers as helpers
from modules.provider_detector import (
    get_primary_provider_or_default,
    get_provider_for_resource,
    SUPPORTED_PROVIDERS,
)

# Import base resource classes
# pylint: disable=unused-wildcard-import
from resource_classes import *

# Generic resources (always needed)
from resource_classes.generic.blank import Blank

# Track available classes - will be populated dynamically per provider
avl_classes = []
_loaded_provider = None

# User-configurable diagram sizing (set by CLI or YAML annotations)
DIAGRAM_FONTSIZE: Optional[int] = None
DIAGRAM_ICONSIZE: Optional[int] = None


_DEFAULT_FONTSIZE = 28
_DEFAULT_NODE_WIDTH = 2.8
_DEFAULT_NODE_HEIGHT = 2.8
_DEFAULT_ICON_NODE_HEIGHT = 3.8
_DEFAULT_NODESEP = 3.0
_DEFAULT_RANKSEP = 6.0


def _run_gvpr_label_shift(path_to_predot: str, outfile: str) -> Path:
    """Run the shiftLabel.gvpr post-processing script on a pre-rendered DOT file.

    Returns the path to the post-processed DOT file. Raises if gvpr fails so
    a stale or missing output file is never silently reused.
    """
    bundle_dir = Path(__file__).parent.parent
    path_to_script = Path.cwd() / bundle_dir / "shiftLabel.gvpr"
    path_to_postdot = Path.cwd() / f"{outfile}.dot"
    subprocess.run(
        [
            "gvpr",
            "-c",
            "-q",
            "-f",
            str(path_to_script),
            str(path_to_predot),
            "-o",
            str(path_to_postdot),
        ],
        check=True,
    )
    return path_to_postdot


def _apply_size_overrides(tfdata: Dict[str, Any]) -> None:
    """Apply user-specified fontsize/iconsize overrides to resource class defaults.

    Reads from DIAGRAM_FONTSIZE / DIAGRAM_ICONSIZE globals (set by CLI) and
    falls back to tfdata["annotations"] values. Scales the node layout box,
    spacing, and label height proportionally so larger text doesn't overflow
    cluster boundaries or overlap neighboring labels.
    """
    global DIAGRAM_FONTSIZE, DIAGRAM_ICONSIZE

    annotations = tfdata.get("annotations") or {}
    fontsize = DIAGRAM_FONTSIZE or annotations.get("fontsize")
    iconsize = DIAGRAM_ICONSIZE or annotations.get("iconsize")

    if not fontsize and not iconsize:
        return

    if fontsize:
        fontsize = int(fontsize)
        import math

        linear = fontsize / _DEFAULT_FONTSIZE
        sqrt_scale = math.sqrt(linear)

        Canvas._default_node_attrs["fontsize"] = str(fontsize)
        Cluster._default_graph_attrs["fontsize"] = str(int(24 * sqrt_scale))

        # Node layout box scales linearly with fontsize
        Canvas._default_node_attrs["width"] = f"{_DEFAULT_NODE_WIDTH * linear:.1f}"
        Canvas._default_node_attrs["height"] = f"{_DEFAULT_NODE_HEIGHT * linear:.1f}"

        # Spacing uses dampened sqrt scaling
        Canvas._default_graph_attrs["nodesep"] = f"{_DEFAULT_NODESEP * sqrt_scale:.1f}"
        Canvas._default_graph_attrs["ranksep"] = f"{_DEFAULT_RANKSEP * sqrt_scale:.1f}"

        Node._height = _DEFAULT_ICON_NODE_HEIGHT * linear

        Cluster._margin_scale = linear

    if iconsize:
        iconsize = int(iconsize)
        node_inches = iconsize / 72 + 1.0
        if fontsize:
            linear = fontsize / _DEFAULT_FONTSIZE
            node_inches = max(node_inches, _DEFAULT_NODE_WIDTH * linear)
            Canvas._default_node_attrs["width"] = f"{node_inches:.1f}"
            Canvas._default_node_attrs["height"] = f"{node_inches:.1f}"
            Node._height = _DEFAULT_ICON_NODE_HEIGHT * linear
        else:
            Canvas._default_node_attrs["width"] = f"{node_inches:.1f}"
            Canvas._default_node_attrs["height"] = f"{node_inches:.1f}"
            Node._height = node_inches + 1.0


def _load_provider_resources(provider: str) -> None:
    """Dynamically load resource classes for the specified cloud provider.

    Args:
        provider: Cloud provider name ('aws', 'azure', 'gcp')
    """
    global avl_classes, _loaded_provider

    # Skip if already loaded for this provider
    if _loaded_provider == provider:
        return

    # Map provider names to package names
    provider_packages = {
        "aws": "resource_classes.aws",
        "azure": "resource_classes.azure",
        "gcp": "resource_classes.gcp",
    }

    package_name = provider_packages.get(provider)
    if not package_name:
        click.echo(
            click.style(
                f"\nERROR: Unknown provider '{provider}'. Exiting.",
                fg="red",
                bold=True,
            )
        )
        exit()

    # Import all submodules from the provider package
    try:
        package = importlib.import_module(package_name)
        package_path = Path(package.__file__).parent

        for _, module_name, _ in pkgutil.iter_modules([str(package_path)]):
            full_module_name = f"{package_name}.{module_name}"
            module = importlib.import_module(full_module_name)

            # Import all public names from the module into this module's namespace
            for name in dir(module):
                if not name.startswith("_"):
                    obj = getattr(module, name)
                    globals()[name] = obj

        # Update available classes list
        avl_classes = list(globals().keys())
        _loaded_provider = provider

    except ImportError as e:
        click.echo(
            click.style(
                f"\nERROR: Failed to load resource classes for provider '{provider}': {e}. Exiting.",
                fg="red",
                bold=True,
            )
        )
        exit()


# Module-level constants that get set per-provider in render_diagram
# Initialize with empty defaults
CONSOLIDATED_NODES = []
GROUP_NODES = []
DRAW_ORDER = []
NODE_VARIANTS = {}
OUTER_NODES = []
AUTO_ANNOTATIONS = []
EDGE_NODES = []
SHARED_SERVICES = []
GROUP_LINKS = []
ALWAYS_DRAW_LINE = []
NEVER_DRAW_LINE = []


# ---------------------------------------------------------------------------
# Flow badge helpers (US5)
# ---------------------------------------------------------------------------


def generate_badge_xlabel(step_numbers: List[int], color: str = "#E74C3C") -> str:
    """Return an HTML-table xlabel badge for one or more step numbers.

    Args:
        step_numbers: Ordered list of step numbers to display in the badge.
        color: Background colour of the badge circle.

    Returns:
        A Graphviz HTML-label string (angle-bracket delimited) suitable
        for use as an ``xlabel`` attribute on a node or edge.
    """
    nums = ", ".join(str(n) for n in step_numbers)
    return (
        f'<<TABLE BORDER="0"><TR>'
        f'<TD BGCOLOR="{color}" STYLE="ROUNDED" WIDTH="24" HEIGHT="24">'
        f'<FONT COLOR="white"><B>{nums}</B></FONT></TD>'
        f"</TR></TABLE>>"
    )


def generate_legend_html(legend_entries: List[Dict[str, Any]]) -> str:
    """Build an HTML-table label string for the flow legend node.

    Args:
        legend_entries: Ordered list of dicts with keys ``step_number``,
            ``flow_name``, ``description``, ``xlabel``, ``detail``,
            ``color``.

    Returns:
        Graphviz HTML-label string (angle-bracket delimited).
    """
    if not legend_entries:
        return '<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="4" BGCOLOR="white"></TABLE>>'

    rows: List[str] = []
    current_flow: Optional[str] = None

    for entry in legend_entries:
        flow = entry["flow_name"]
        if flow != current_flow:
            current_flow = flow
            rows.append(f'<TR><TD COLSPAN="3"><B>Flow: {flow}</B></TD></TR>')

        color = entry.get("color", "#E74C3C")
        num = entry["step_number"]
        xlabel = entry.get("xlabel", "")
        detail = entry.get("detail", "")
        rows.append(
            f"<TR>"
            f'<TD BGCOLOR="{color}" WIDTH="20" HEIGHT="20" STYLE="ROUNDED">'
            f'<FONT COLOR="white"><B>{num}</B></FONT></TD>'
            f'<TD ALIGN="LEFT">{xlabel}</TD>'
            f'<TD ALIGN="LEFT">{detail}</TD>'
            f"</TR>"
        )

    body = "\n".join(rows)
    return (
        f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="4" BGCOLOR="white">\n'
        f"{body}\n"
        f"</TABLE>>"
    )


def _apply_flow_badges(
    tfdata: Dict[str, Any],
    diagram: "Canvas",
    cloud_group: "Cluster",
) -> None:
    """Apply pre-computed flow badge xlabels to drawn nodes.

    Iterates ``tfdata["flow_badges"]`` and for each resource that has
    been drawn (has a ``node`` entry in ``meta_data``), sets the
    ``xlabel`` attribute on the underlying Graphviz node object.

    Edge badges are NOT applied here — they are applied during edge
    creation via ``tfdata["flow_edge_badges"]``.
    """
    flow_badges = tfdata.get("flow_badges") or {}
    if not flow_badges:
        return

    for resource, badge_html in flow_badges.items():
        meta = tfdata.get("meta_data", {}).get(resource)
        if not meta or "node" not in meta:
            continue
        node_obj = meta["node"]
        # Re-declare the node with the xlabel attribute.  In the
        # graphviz Python library calling .node() again with the same
        # ID simply appends a second node statement whose attributes
        # merge with the first.
        cluster = node_obj._cluster or diagram
        cluster.dot.node(node_obj._id, xlabel=badge_html)


def _badge_html(target: str, tfdata: Dict[str, Any]) -> Tuple[Optional[str], float]:
    """Graphviz HTML label for a badge drawn on *target*, or None if unbadged.

    A badge is an icon in the corner of the resource it applies to rather than
    a separate node wired up with a line. Every provider's architecture guide
    uses that convention for things which qualify a resource instead of sitting
    beside it - Azure NSGs, AWS security groups, GCP firewall rules - and drawn
    as ordinary nodes they read as devices traffic passes through, which they
    are not.

    Nothing here is provider-specific. A handler records {target: badge node}
    in tfdata["badges"] and the icon is taken from the badge resource's own
    node class, so any provider can badge any resource without adding code to
    this module.

    Returns (html, width_in_points). The width lets shiftLabel.gvpr pin the
    icon cell itself over the node's corner; graphviz only records where an
    xlabel ended up, never how wide it is.
    """
    # Compared without the ~N count suffix: handlers record badges before
    # create_multiple_resources() numbers the instances, so the names in
    # tfdata["badges"] are the pre-numbering ones and a literal lookup misses
    # every counted resource.
    badges = {k.split("~")[0]: v for k, v in (tfdata.get("badges") or {}).items()}
    badge_resource = badges.get(target.split("~")[0])
    if not badge_resource:
        return None, 0.0

    resource_type = helpers.get_no_module_name(badge_resource).split(".")[0]
    badge_class = _node_class_for(resource_type, tfdata)
    icon_dir = getattr(badge_class, "_icon_dir", None)
    icon_file = getattr(badge_class, "_icon", None)
    if not icon_dir or not icon_file:
        # Falls back to a generic class with no icon of its own; a badge is
        # only meaningful as a picture, so skip rather than draw a bare label.
        return None, 0.0

    repo_root = Path(os.path.abspath(os.path.dirname(__file__))).parent
    icon = f"{repo_root}/{icon_dir}/{icon_file}"
    name = helpers.pretty_name(badge_resource)
    icon_pts = 64.0
    text_pts = len(name) * 22.0 * 0.55
    html = (
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>'
        f'<TD FIXEDSIZE="TRUE" WIDTH="{icon_pts:.0f}" HEIGHT="{icon_pts:.0f}">'
        f'<IMG SCALE="TRUE" SRC="{icon}"/></TD>'
        f'<TD><FONT POINT-SIZE="22">{name}</FONT></TD>'
        "</TR></TABLE>>"
    )
    return html, icon_pts + text_pts


def _badged_nodes(tfdata: Dict[str, Any]) -> Set[str]:
    """Resources already shown as a badge, so they must not draw twice.

    Returned without the ~N count suffix, for the same reason _badge_html()
    strips it - compare with resource.split("~")[0].
    """
    return {v.split("~")[0] for v in (tfdata.get("badges") or {}).values()}


def _drawn_node_inside(resource: str, tfdata: Dict[str, Any]):
    """Find any drawn node within a group, however deeply nested.

    A cluster-to-cluster edge still has to name two real nodes as endpoints;
    lhead/ltail only clip it back to the cluster borders.
    """
    seen = set()
    queue = [resource]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        node = tfdata.get("meta_data", {}).get(current, {}).get("node")
        if node is not None and current != resource:
            return node
        queue.extend(tfdata["graphdict"].get(current, []))
    return None


def _draw_group_links(tfdata: Dict[str, Any], diagram) -> None:
    """Draw links between two group boxes as a clipped edge between the boxes.

    Some resources describe a relationship between two whole networks rather
    than anything inside them - VNet/VPC peerings, network peerings, transit
    gateway attachments. Drawn as an icon inside one of the groups they read as
    a device that lives there, which is not what they are.

    Graphviz has no true cluster-to-cluster edge, but with compound=true an edge
    between two member nodes is clipped at both cluster borders, so it reads as
    a link between the boxes themselves.

    Driven by <PROVIDER>_GROUP_LINKS so every provider gets this from config:
    each entry names the linking resource type and the attribute holding the
    remote group's identity.
    """
    link_types = GROUP_LINKS
    if not link_types:
        return

    clusters = {res: name for name, res in (tfdata.get("cluster_id_map") or {}).items()}
    if len(clusters) < 2:
        return

    # Shared with the reference matching in graphmaker rather than
    # reimplemented, because a link needs BOTH metadata views and which one
    # holds the answer varies per attribute. A single peering shows it:
    #   virtual_network_name      'VNET.apps'   the plan resolved this
    #   remote_virtual_network_id True          only the HCL names the target
    # terravision plans against empty state, so anything the provider assigns
    # is usually unknown - reading the plan alone drew no peering at all.
    from modules.graphmaker import _resolved_metadata as resolved_metadata

    def resolved(node: str) -> Dict[str, Any]:
        return resolved_metadata(node, tfdata)

    # Index every drawn group by the values a link resource might reference it
    # by. The Terraform address is included because it is what survives when
    # the id does not: the HCL expression left in place of an unknown id names
    # its target as azurerm_virtual_network.generic_vnet["security"], which is
    # the graph key rather than any provider identifier.
    by_identity = {}
    for group in clusters:
        by_identity[group.split("~")[0]] = group
        metadata = resolved(group)
        for key in ("id", "self_link", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                by_identity[value] = group

    def group_referenced_by(reference: str):
        return next(
            (
                g
                for identity, g in by_identity.items()
                if identity and identity in reference
            ),
            None,
        )

    drawn_pairs = set()
    for owner in clusters:
        for child in tfdata["graphdict"].get(owner, []):
            child_type = helpers.get_no_module_name(child).split(".")[0]
            link = next(
                (l for l in link_types if l["resource_type"] == child_type), None
            )
            if not link:
                continue

            remote = group_referenced_by(
                str(resolved(child).get(link["remote_attribute"], ""))
            )

            # Prefer the link's own idea of which group it belongs to. Graph
            # parentage is unreliable here: a peering frequently ends up nested
            # under the VNET it points AT rather than the one that declares it,
            # which made both ends resolve to the same box and every line was
            # skipped as a self-link.
            local_attribute = link.get("local_attribute")
            local = (
                group_referenced_by(str(resolved(child).get(local_attribute, "")))
                if local_attribute
                else None
            )
            owner = local or owner

            # These are declared from both sides; one line between them is enough
            if not remote or remote == owner:
                continue
            pair = frozenset((owner, remote))
            if pair in drawn_pairs:
                continue

            tail_node = _drawn_node_inside(owner, tfdata)
            head_node = _drawn_node_inside(remote, tfdata)
            if tail_node is None or head_node is None:
                continue

            drawn_pairs.add(pair)
            diagram.dot.edge(
                tail_node._id,
                head_node._id,
                ltail=clusters[owner],
                lhead=clusters[remote],
                dir="both",
                color=link.get("color", "#7B2CBF"),
                penwidth="4",
                xlabel=link.get("label", ""),
                fontsize="24",
                fontcolor=link.get("color", "#7B2CBF"),
                _grouplink="1",
            )
            tfdata.setdefault("group_links_drawn", []).append(
                f"{helpers.pretty_name(owner)} <-> {helpers.pretty_name(remote)}"
            )


def _node_class_for(resource_type: str, tfdata: Dict[str, Any]):
    """Return the icon class for a resource type, falling back to a generic one.

    Only the primary provider's icon package is loaded, so anything from a
    second provider (Route53 records in an Azure-primary plan) or any type with
    no icon yet used to fail the avl_classes check and vanish from the diagram
    with no message at all. Drawing a generic box is far better than silently
    losing infrastructure - and the warning says what to add an icon for.
    """
    node_class = getattr(sys.modules[__name__], resource_type, None)
    if node_class is not None:
        return node_class

    missing = tfdata.setdefault("missing_icons", [])
    if resource_type not in missing:
        missing.append(resource_type)
        click.echo(
            click.style(
                f"   WARNING: no icon for '{resource_type}', drawing a generic node",
                fg="yellow",
            )
        )
    return Blank


def _make_edge_with_badge(
    tfdata: Dict[str, Any],
    origin_resource: str,
    dest_resource: str,
    **edge_kwargs,
) -> "Edge":
    """Create an Edge, injecting a flow-badge xlabel if one exists.

    Checks ``tfdata["flow_edge_badges"]`` for a badge matching the
    ``(origin_resource, dest_resource)`` pair and, if found, sets the
    ``xlabel`` attribute on the Edge.
    """
    edge_badges = tfdata.get("flow_edge_badges") or {}
    badge = edge_badges.get((origin_resource, dest_resource))
    if badge:
        edge_kwargs["xlabel"] = badge
    return Edge(**edge_kwargs)


def _add_legend_node(
    tfdata: Dict[str, Any],
    diagram: "Canvas",
) -> None:
    """Add a flow-legend HTML-table node to the diagram (if flows exist).

    The node is tagged with ``_legendnode="1"`` so the ``shiftLabel.gvpr``
    post-processor can position it below the footer.
    """
    legend_entries = tfdata.get("flow_legend_entries") or []
    if not legend_entries:
        return

    legend_html = generate_legend_html(legend_entries)
    setcluster(diagram)
    legend_style = {
        "_legendnode": "1",
        "shape": "plaintext",
        "label": legend_html,
    }
    getattr(sys.modules[__name__], "Node")(**legend_style)


def _get_provider_config(tfdata: Dict[str, Any]):
    """Load provider-specific configuration dynamically.

    Args:
        tfdata: Terraform data dictionary with provider_detection

    Returns:
        Configuration module for detected provider
    """
    provider = get_primary_provider_or_default(tfdata)
    return config_loader.load_config(provider)


def _load_provider_constants(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Load provider-specific configuration constants.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        Dictionary with provider-specific drawing constants
    """
    config = _get_provider_config(tfdata)
    provider = get_primary_provider_or_default(tfdata)
    provider_upper = provider.upper()

    return {
        "CONSOLIDATED_NODES": getattr(
            config, f"{provider_upper}_CONSOLIDATED_NODES", []
        ),
        "GROUP_NODES": getattr(config, f"{provider_upper}_GROUP_NODES", []),
        "DRAW_ORDER": getattr(config, f"{provider_upper}_DRAW_ORDER", []),
        "NODE_VARIANTS": getattr(config, f"{provider_upper}_NODE_VARIANTS", {}),
        "OUTER_NODES": getattr(config, f"{provider_upper}_OUTER_NODES", []),
        "AUTO_ANNOTATIONS": getattr(config, f"{provider_upper}_AUTO_ANNOTATIONS", []),
        "EDGE_NODES": getattr(config, f"{provider_upper}_EDGE_NODES", []),
        "SHARED_SERVICES": getattr(config, f"{provider_upper}_SHARED_SERVICES", []),
        "ALWAYS_DRAW_LINE": getattr(config, f"{provider_upper}_ALWAYS_DRAW_LINE", []),
        "NEVER_DRAW_LINE": getattr(config, f"{provider_upper}_NEVER_DRAW_LINE", []),
        "GROUP_LINKS": getattr(config, f"{provider_upper}_GROUP_LINKS", []),
    }


def get_edge_labels(origin: Node, destination: Node, tfdata: Dict[str, Any]) -> str:
    """Extract custom edge labels for connections between nodes.

    Searches for user-defined edge labels in metadata, handling both direct
    resource matches and consolidated node patterns.

    Args:
        origin: Source node object
        destination: Destination node object
        tfdata: Terraform data dictionary containing meta_data with edge_labels

    Returns:
        Label string for the edge, or empty string if no label found
    """
    label = ""
    origin_resource = origin._attrs["tf_resource_name"]
    dest_resource = destination._attrs["tf_resource_name"]

    # Check if destination matches any consolidated node patterns
    consolidated_dest_prefix = [
        k
        for k in list(CONSOLIDATED_NODES)
        if helpers.get_no_module_name(dest_resource).startswith(list(k.keys())[0])
    ]

    # Check if origin matches any consolidated node patterns
    consolidated_origin_prefix = [
        k
        for k in CONSOLIDATED_NODES
        if helpers.get_no_module_name(origin_resource).startswith(list(k.keys())[0])
    ]

    # Find edge labels from consolidated or direct origin resource
    if consolidated_origin_prefix:
        candidate_resources = helpers.list_of_dictkeys_containing(
            tfdata["meta_data"],
            list(consolidated_origin_prefix[0].keys())[0],
        )
        edge_labels_list = None
        for resource in candidate_resources:
            edge_labels_list = tfdata["meta_data"][resource].get("edge_labels")
            if edge_labels_list:
                break
    else:
        edge_labels_list = tfdata["meta_data"][origin_resource].get("edge_labels")

    # Match edge label to destination resource
    if edge_labels_list:
        for labeldict in edge_labels_list:
            key = [k for k in labeldict][0]
            # Check for exact match or consolidated pattern match
            if key == dest_resource or (
                consolidated_dest_prefix
                and key.startswith(list(consolidated_dest_prefix[0].keys())[0])
            ):
                label = labeldict[key]
                break

    return label


def handle_nodes(
    resource: str,
    inGroup: Cluster,
    cloudGroup: Cluster,
    diagramCanvas: Canvas,
    tfdata: Dict[str, Any],
    drawn_resources: List[str],
) -> Tuple[Node, List[str]]:
    """Recursively draw nodes and their connections in the diagram.

    Creates visual nodes for Terraform resources and establishes connections
    between them. Handles circular references and prevents duplicate drawings.

    Args:
        resource: Terraform resource name (e.g., 'aws_lambda_function.my_func')
        inGroup: Current cluster/group to add nodes to
        cloudGroup: Main cloud provider cluster
        diagramCanvas: Root canvas object for the diagram
        tfdata: Terraform data dictionary with graphdict and meta_data
        drawn_resources: List of already drawn resource names

    Returns:
        Tuple of (created Node object, updated drawn_resources list)
    """
    resource_type = helpers.get_no_module_name(resource).split(".")[0]
    if resource_type in tfdata["hidden"]:
        return None, drawn_resources

    # A resource drawn as a badge must not also appear as a standalone icon
    if resource.split("~")[0] in _badged_nodes(tfdata):
        return None, drawn_resources

    # Reuse existing node if already drawn
    if resource in drawn_resources:
        newNode = tfdata["meta_data"][resource]["node"]
    else:
        # Create new node and add to appropriate group
        is_outer = resource_type in OUTER_NODES
        is_edge = any(resource_type.startswith(e) for e in EDGE_NODES)
        targetGroup = diagramCanvas if is_outer else inGroup
        node_label = helpers.pretty_name(resource)
        setcluster(targetGroup)
        nodeClass = _node_class_for(resource_type, tfdata)
        # Build extra node attrs
        extra_attrs = {}
        if is_edge:
            extra_attrs["_edgenode"] = "1"
        # A badged resource carries its badge as an xlabel on its own icon,
        # mirroring how these are drawn by hand (a small shield on the NIC)
        node_badge, node_badge_w = _badge_html(resource, tfdata)
        if node_badge:
            extra_attrs["xlabel"] = node_badge
            extra_attrs["_badgewidth"] = f"{node_badge_w:.1f}"
            # graphviz drops xlabels wherever they fit; _badgenode tells
            # shiftLabel.gvpr to pin this one to the node card's top-right
            extra_attrs["_badgenode"] = "1"
        # Only pass outer_node for GCP nodes (they use it for border styling)
        provider = get_primary_provider_or_default(tfdata)
        if provider == "gcp":
            newNode = nodeClass(
                label=node_label,
                tf_resource_name=resource,
                outer_node=is_outer,
                **extra_attrs,
            )
        else:
            newNode = nodeClass(
                label=node_label, tf_resource_name=resource, **extra_attrs
            )
        drawn_resources.append(resource)
        tfdata["meta_data"].setdefault(resource, {})["node"] = newNode
        tfdata.setdefault("node_id_map", {})[newNode._id] = resource

    # Process connections to other nodes
    if tfdata["graphdict"].get(resource):
        for node_connection in tfdata["graphdict"][resource]:
            connectedNode = None
            c_resource = helpers.get_no_module_name(node_connection)
            node_type = str(c_resource).split(".")[0]

            # Determine target group based on node type
            if node_type in OUTER_NODES:
                connectedGroup = diagramCanvas
            else:
                connectedGroup = cloudGroup

            # Process non-group nodes
            if node_type not in GROUP_NODES:
                if node_type in avl_classes and resource != node_connection:
                    # Check if node already exists in metadata (was drawn earlier)
                    if (
                        node_connection in tfdata["meta_data"]
                        and "node" in tfdata["meta_data"][node_connection]
                    ):
                        connectedNode = tfdata["meta_data"][node_connection]["node"]
                    elif node_connection in tfdata["graphdict"].keys():
                        # Defer auto-grouped resources so they draw inside their group
                        if node_connection in tfdata.get(
                            "auto_grouped_resources", set()
                        ):
                            tfdata["deferred_connections"].append(
                                (resource, node_connection)
                            )
                            continue
                        # Node exists in graphdict, try to draw it
                        circular_reference = resource in tfdata["graphdict"].get(
                            node_connection, []
                        )
                        if not circular_reference:
                            connectedNode, drawn_resources = handle_nodes(
                                node_connection,
                                connectedGroup,
                                cloudGroup,
                                diagramCanvas,
                                tfdata,
                                drawn_resources,
                            )
                            if connectedNode is None:
                                # Defer connection if node couldn't be drawn yet
                                tfdata["deferred_connections"].append(
                                    (resource, node_connection)
                                )
                                continue
                        elif node_connection not in drawn_resources:
                            # This branch draws a node itself rather than going
                            # through handle_nodes(), so it has to repeat the
                            # hidden check - otherwise anything reachable via a
                            # circular reference ignores the hide list entirely.
                            if node_type in tfdata["hidden"]:
                                continue
                            nodeClass = _node_class_for(node_type, tfdata)
                            connectedNode = nodeClass(
                                label=helpers.pretty_name(node_connection),
                                tf_resource_name=node_connection,
                            )
                            drawn_resources.append(node_connection)
                            tfdata.setdefault("node_id_map", {})[
                                connectedNode._id
                            ] = node_connection
                            tfdata["meta_data"].update(
                                {node_connection: {"node": connectedNode}}
                            )
                            # Defer the circular node's own connections so they
                            # get processed after all nodes are drawn
                            for dest in tfdata["graphdict"].get(node_connection, []):
                                if dest != resource:
                                    tfdata["deferred_connections"].append(
                                        (node_connection, dest)
                                    )
                    else:
                        # Node not in graphdict yet, defer
                        tfdata["deferred_connections"].append(
                            (resource, node_connection)
                        )
                        continue

                # Create edge connection if node was drawn
                if connectedNode:
                    label = get_edge_labels(newNode, connectedNode, tfdata)

                    # Determine origin node for connection
                    if (
                        not tfdata["connected_nodes"].get(newNode._id)
                        and tfdata["meta_data"][resource]["node"]
                    ):
                        originNode = tfdata["meta_data"][resource]["node"]
                    else:
                        originNode = newNode

                    # Create connection if not already exists and connection is allowed
                    if not tfdata["connected_nodes"].get(
                        originNode._id
                    ) or connectedNode._id not in tfdata["connected_nodes"].get(
                        originNode._id
                    ):
                        if originNode != connectedNode and ok_to_connect(
                            resource_type, node_type
                        ):
                            # Determine edge visibility
                            line_style = (
                                "solid"
                                if always_draw_edge(resource_type, node_type, tfdata)
                                else "invis"
                            )
                            # Check if this is a bidirectional link
                            is_bidir = frozenset(
                                (resource, node_connection)
                            ) in tfdata.get("bidirectional_edges", set())
                            originNode.connect(
                                connectedNode,
                                _make_edge_with_badge(
                                    tfdata,
                                    resource,
                                    node_connection,
                                    forward=True,
                                    reverse=is_bidir,
                                    label=label,
                                    style=line_style,
                                ),
                            )
                            # Track connection to prevent duplicates
                            if not tfdata["connected_nodes"].get(originNode._id):
                                tfdata["connected_nodes"][originNode._id] = list()
                            tfdata["connected_nodes"][originNode._id] = (
                                helpers.append_dictlist(
                                    tfdata["connected_nodes"][originNode._id],
                                    connectedNode._id,
                                )
                            )
                            # For bidirectional edges, also track the reverse to prevent duplicate
                            if is_bidir:
                                if not tfdata["connected_nodes"].get(connectedNode._id):
                                    tfdata["connected_nodes"][
                                        connectedNode._id
                                    ] = list()
                                tfdata["connected_nodes"][connectedNode._id] = (
                                    helpers.append_dictlist(
                                        tfdata["connected_nodes"][connectedNode._id],
                                        originNode._id,
                                    )
                                )

    return newNode, drawn_resources


def always_draw_edge(origin: str, destination: str, tfdata: Dict[str, Any]) -> bool:
    """Determine if an edge should be visible in the diagram.

    Controls edge visibility based on configuration rules. By default, edges
    are visible unless the origin is in the NEVER_DRAW_LINE list.

    Args:
        origin: Origin resource type
        destination: Destination resource type
        tfdata: Terraform data dictionary

    Returns:
        True if edge should be visible (solid), False for invisible edge
    """
    if origin in NEVER_DRAW_LINE:
        return False
    return True


def ok_to_connect(origin: str, destination: str) -> bool:
    """Determine if a connection should be created between two nodes.

    Prevents connections to/from shared services unless explicitly allowed,
    helping maintain proper diagram layout and ranking.

    Args:
        origin: Origin resource type
        destination: Destination resource type

    Returns:
        True if connection is allowed, False otherwise
    """
    if (
        origin in SHARED_SERVICES
        or destination in SHARED_SERVICES
        and origin not in ALWAYS_DRAW_LINE
        and destination not in ALWAYS_DRAW_LINE
    ):
        return False
    return True


def create_cluster_label_node(cluster_obj: Cluster) -> None:
    """Create a label node for clusters that have label metadata.

    Generates HTML table labels with optional icons and adds special
    attributes for gvpr positioning.

    Args:
        cluster_obj: Cluster object with label_text attribute
    """
    if not hasattr(cluster_obj, "label_text"):
        return

    # Cluster captions stay on a single line - shiftLabel.gvpr widens the box
    # to whatever the label needs, so there is no reason to stack "name (cidr)"
    # onto two rows.
    text = " ".join(cluster_obj.label_text.split())
    # A caption should not compete with the resource labels inside the box, and
    # a narrower label needs less of the box-widening in shiftLabel.gvpr, which
    # is what pushes neighbouring boxes into each other
    if text.strip():
        text = (
            '<FONT POINT-SIZE="' + str(CLUSTER_LABEL_FONTSIZE) + '">' + text + "</FONT>"
        )

    # Build HTML table label with icon and text (or just text if no icon)
    if hasattr(cluster_obj, "label_icon") and cluster_obj.label_icon is not None:
        icon_first = getattr(cluster_obj, "label_icon_first", True)
        # A cluster can ask for its icon at a specific size (the Azure logo is
        # a branding mark, not a glyph, so it wants to be bigger than a subnet
        # chevron). Without this an image renders at its natural size.
        icon_w = getattr(cluster_obj, "label_icon_width", None)
        icon_h = getattr(cluster_obj, "label_icon_height", None)
        if icon_w and icon_h:
            icon_cell = (
                f'<TD FIXEDSIZE="TRUE" WIDTH="{icon_w}" HEIGHT="{icon_h}">'
                f'<IMG SCALE="TRUE" SRC="{cluster_obj.label_icon}"/></TD>'
            )
        else:
            icon_cell = f'<TD><img src="{cluster_obj.label_icon}"/></TD>'

        cells = (
            icon_cell + f"<TD>{text}</TD>"
            if icon_first
            else f"<TD>{text}</TD>" + icon_cell
        )
        label_html = (
            '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>'
            + cells
            + "</TR></TABLE>>"
        )
    else:
        label_html = text

    # Create label node with special attributes for gvpr positioning.
    #
    # fixedsize/width/height are overridden per-node so graphviz sizes the box
    # to the label instead of the 2.8in square in the graph-level node defaults.
    # That matters twice over: the box now actually contains its text, and the
    # measured width lands in the layout output where shiftLabel.gvpr can read
    # it to align the label's edge with the cluster's corner. Inheriting the
    # default made every label 2.8in wide no matter how long the text was, so
    # any offset computed from it drifted as soon as label lengths changed.
    #
    # The node is declared on the ROOT graph rather than inside the cluster.
    # shiftLabel.gvpr pins it to an absolute position anyway, so cluster
    # membership buys nothing - and a label wider than the resources it sits
    # under would otherwise stretch that cluster to fit, widening the whole
    # diagram for nothing.
    label_node_id = f"_label_{cluster_obj.dot.name}"
    cluster_type = cluster_obj.__class__.__name__
    diagram = getdiagram()
    target = diagram.dot if diagram is not None else cluster_obj.dot
    target.node(
        label_node_id,
        label=label_html,
        shape="plaintext",
        pin="true",
        fixedsize="false",
        width="0",
        height="0",
        _clusterlabel="1",
        _clusterid=cluster_obj.dot.name,
        _clustertype=cluster_type,
        _labelposition=cluster_obj.label_position,
    )


def handle_group(
    inGroup: Cluster,
    cloudGroup: Cluster,
    diagramCanvas: Canvas,
    resource: str,
    tfdata: Dict[str, Any],
    drawn_resources: List[str],
) -> Tuple[Cluster, List[str]]:
    """Recursively draw groups, subgroups, and their contained nodes.

    Creates cluster/group visual elements for resources like VPCs, subnets,
    and security groups, then populates them with their child resources.

    Args:
        inGroup: Parent cluster to add this group to
        cloudGroup: Main cloud provider cluster
        diagramCanvas: Root canvas object for the diagram
        resource: Terraform resource name for the group
        tfdata: Terraform data dictionary with graphdict and meta_data
        drawn_resources: List of already drawn resource names

    Returns:
        Tuple of (created Cluster object, updated drawn_resources list)
    """
    resource_type = helpers.get_no_module_name(resource).split(".")[0]
    if resource_type not in avl_classes or resource_type in tfdata["hidden"]:
        return None, drawn_resources

    # Skip empty groups (groups with no children)
    # Empty subnets/groups cause layout issues where they get huge bounding boxes
    if not tfdata["graphdict"].get(resource):
        return None, drawn_resources

    if resource in drawn_resources:
        return None, drawn_resources

    # Create new group/cluster
    node_label = helpers.pretty_name(resource, is_group=True)
    cidr = helpers.get_cidr_label(resource, tfdata)
    if cidr:
        node_label = f"{node_label} ({cidr})"
    group_class = getattr(sys.modules[__name__], resource_type)
    # A badged group carries its badge in the corner of the box rather than
    # as a separate icon inside it
    badge, _badge_w = _badge_html(resource, tfdata)
    if badge:
        newGroup = group_class(label=node_label, badge_label=badge)
        newGroup.dot.graph_attr["labelloc"] = "t"
        newGroup.dot.graph_attr["labeljust"] = "r"
    else:
        newGroup = group_class(label=node_label)
    targetGroup = diagramCanvas if resource_type in OUTER_NODES else inGroup
    targetGroup.subgraph(newGroup.dot)
    drawn_resources.append(resource)

    # Track cluster ID to terraform resource mapping for HTML renderer
    if "cluster_id_map" not in tfdata:
        tfdata["cluster_id_map"] = {}
    tfdata["cluster_id_map"][newGroup.name] = resource

    # Create separate label node for clusters that have label metadata
    create_cluster_label_node(newGroup)

    # Add child nodes and subgroups
    child_node_ids = []
    child_group_ids = []
    if tfdata["graphdict"].get(resource):
        for node_connection in tfdata["graphdict"][resource]:
            node_type = str(helpers.get_no_module_name(node_connection).split(".")[0])

            # Handle nested subgroups
            if (
                node_type in GROUP_NODES
                and node_type in avl_classes
                and node_type not in tfdata["hidden"]
            ):
                subGroup, drawn_resources = handle_group(
                    newGroup,
                    cloudGroup,
                    diagramCanvas,
                    node_connection,
                    tfdata,
                    drawn_resources,
                )
                if subGroup is not None:
                    newGroup.subgraph(subGroup.dot)
                    drawn_resources.append(node_connection)
                    # Remember one node from inside the subgroup. Clusters
                    # cannot be ranked directly, but ranking a member node
                    # drags its cluster with it, which is how the grid below
                    # wraps subnets onto rows instead of one endless line.
                    anchor = _drawn_node_inside(node_connection, tfdata)
                    if anchor is not None:
                        child_group_ids.append(anchor._id)

            # Handle regular nodes within the group
            elif (
                node_type not in GROUP_NODES
                and node_type in avl_classes
                and node_type not in tfdata["hidden"]
                and node_connection != resource
            ):
                targetGroup = diagramCanvas if node_type in OUTER_NODES else cloudGroup
                newNode, drawn_resources = handle_nodes(
                    node_connection,
                    targetGroup,
                    cloudGroup,
                    diagramCanvas,
                    tfdata,
                    drawn_resources,
                )
                if newNode is not None:
                    # Don't overwrite HTML labels (GCP nodes have custom HTML tables)
                    node_label = newNode._attrs.get(
                        "label", helpers.pretty_name(node_connection)
                    )
                    newGroup.add_node(newNode._id, label=node_label)
                    child_node_ids.append(newNode._id)
                elif (
                    node_connection in tfdata["meta_data"]
                    and "node" in tfdata["meta_data"][node_connection]
                ):
                    child_node_ids.append(
                        tfdata["meta_data"][node_connection]["node"]._id
                    )

    # Wrap many children into a grid so a group cannot grow into one long row.
    # Applies to plain nodes and to nested groups alike - a VNET with several
    # subnets was previously laid out in a single line, which is most of why
    # these diagrams end up far wider than they are tall.
    _wrap_into_grid(newGroup, child_node_ids, MAX_NODES_PER_ROW)
    # Nested groups get invisible edges only. Ranking their member nodes here
    # would pull each node out of its own cluster ("already in a rankset,
    # deleted from cluster"), which corrupts the nesting and segfaults dot.
    _wrap_into_grid(newGroup, child_group_ids, MAX_GROUPS_PER_ROW, rank_rows=False)

    return newGroup, drawn_resources


def _wrap_into_grid(
    group: Cluster, node_ids: List[str], per_row: int, rank_rows: bool = True
) -> None:
    """Wrap node_ids into rows of per_row, joined by invisible column edges.

    Graphviz has no "wrap after N" option: you get one row unless something
    forces a new rank. Putting each row in a rank=same subgraph and joining the
    rows with invisible edges is the standard way to build a grid.

    rank_rows must be False when the ids belong to nested clusters: a node can
    only be in one rankset, so ranking it here removes it from its own cluster.
    The invisible edges alone still push later rows downwards.
    """
    if len(node_ids) <= per_row:
        return

    from graphviz import Digraph

    rows = [node_ids[i : i + per_row] for i in range(0, len(node_ids), per_row)]
    for row in rows:
        if rank_rows and len(row) > 1:
            rank_sub = Digraph()
            rank_sub.attr(rank="same")
            for nid in row:
                rank_sub.node(nid)
            group.dot.subgraph(rank_sub)
    # Vertical column edges hold the rows apart: row1[0]->row2[0], etc.
    for r in range(len(rows) - 1):
        for col in range(min(len(rows[r]), len(rows[r + 1]))):
            group.dot.edge(rows[r][col], rows[r + 1][col], style="invis")


# Cluster captions are deliberately smaller than resource labels
CLUSTER_LABEL_FONTSIZE = 20

MAX_NODES_PER_ROW = 3
# Groups are far wider than single icons, so wrap them sooner
MAX_GROUPS_PER_ROW = 2


def draw_objects(
    node_type_list: List[Any],
    all_drawn_resources_list: List[str],
    tfdata: Dict[str, Any],
    diagramCanvas: Canvas,
    cloudGroup: Cluster,
) -> List[str]:
    """Iterate through resources and draw groups or nodes based on type.

    Main loop that processes resources in the specified order, delegating
    to handle_group for cluster resources or handle_nodes for regular nodes.

    Args:
        node_type_list: List of node types to process in this iteration
        all_drawn_resources_list: List of already drawn resource names
        tfdata: Terraform data dictionary with graphdict
        diagramCanvas: Root canvas object for the diagram
        cloudGroup: Main cloud provider cluster

    Returns:
        Updated list of drawn resource names
    """
    if not tfdata.get("hidden"):
        tfdata["hidden"] = list()
    for node_type in node_type_list:
        # Extract node type string from dict or use directly
        if isinstance(node_type, dict):
            node_check = str(list(node_type.keys())[0])
        else:
            node_check = node_type

        # Process each resource in the graph
        for resource in tfdata["graphdict"]:
            resource_type = helpers.get_no_module_name(resource).split(".")[0]
            targetGroup = diagramCanvas if resource_type in OUTER_NODES else cloudGroup

            # Groups need a real Cluster class, but a plain node with no icon
            # class still gets drawn via the generic fallback in handle_nodes()
            is_group_type = resource_type in GROUP_NODES
            if resource_type in avl_classes or not is_group_type:
                # Draw group/cluster resources
                if (
                    resource_type.startswith(node_check)
                    and is_group_type
                    and resource not in all_drawn_resources_list
                ):
                    node_groups, all_drawn_resources_list = handle_group(
                        targetGroup,
                        cloudGroup,
                        diagramCanvas,
                        resource,
                        tfdata,
                        all_drawn_resources_list,
                    )
                    if node_groups is not None:
                        targetGroup.subgraph(node_groups.dot)

                # Draw standalone node resources
                elif (
                    resource_type.startswith(node_check)
                    and not is_group_type
                    and resource not in all_drawn_resources_list
                ):
                    _, all_drawn_resources_list = handle_nodes(
                        resource,
                        targetGroup,
                        cloudGroup,
                        diagramCanvas,
                        tfdata,
                        all_drawn_resources_list,
                    )

    return all_drawn_resources_list


def _build_diagram(
    tfdata: Dict[str, Any],
    outfile: str,
    source: str,
    outformat: str,
    show: bool,
    announce_render: bool = False,
):
    """Build the complete Graphviz diagram and run gvpr post-processing.

    Shared by generate_dot() (DOT/SVG/HTML path) and render_diagram()
    (image/draw.io path): loads provider constants, draws all nodes, groups
    and deferred connections, adds title/footer/legend, pre-renders the DOT
    file and applies the shiftLabel.gvpr positioning script.

    Returns:
        Tuple of (canvas, path_to_predot, path_to_postdot). The canvas is left
        set as the active diagram — callers must call setdiagram(None) when
        they are finished with it.
    """
    # Load provider-specific configuration constants and set module globals
    global CONSOLIDATED_NODES, GROUP_NODES, DRAW_ORDER, NODE_VARIANTS
    global OUTER_NODES, AUTO_ANNOTATIONS, EDGE_NODES, SHARED_SERVICES
    global ALWAYS_DRAW_LINE, NEVER_DRAW_LINE, GROUP_LINKS

    provider = get_primary_provider_or_default(tfdata)

    # Dynamically load resource classes for the detected provider
    _load_provider_resources(provider)

    constants = _load_provider_constants(tfdata)
    CONSOLIDATED_NODES = constants["CONSOLIDATED_NODES"]
    GROUP_NODES = constants["GROUP_NODES"]
    DRAW_ORDER = constants["DRAW_ORDER"]
    NODE_VARIANTS = constants["NODE_VARIANTS"]
    OUTER_NODES = constants["OUTER_NODES"]
    AUTO_ANNOTATIONS = constants["AUTO_ANNOTATIONS"]
    EDGE_NODES = constants["EDGE_NODES"]
    SHARED_SERVICES = constants["SHARED_SERVICES"]
    ALWAYS_DRAW_LINE = constants["ALWAYS_DRAW_LINE"]
    NEVER_DRAW_LINE = constants["NEVER_DRAW_LINE"]
    GROUP_LINKS = constants["GROUP_LINKS"]

    # Refresh the hide list from the provider config rather than trusting what
    # a replay file captured. A tfdata.json written before a hide rule existed
    # would otherwise keep drawing nodes the config now says to leave out.
    hide_nodes = getattr(
        _get_provider_config(tfdata), f"{provider.upper()}_HIDE_NODES", []
    )
    tfdata["hidden"] = sorted(set(tfdata.get("hidden") or []) | set(hide_nodes))

    # Only one provider's icon set is loaded, and clusters/grouping rules are
    # all that provider's, so resources from another cloud cannot be placed
    # meaningfully. Skip them rather than scatter them loose, but say so - a
    # missing resource should never be a silent surprise.
    foreign = set()
    for resource in tfdata["graphdict"]:
        resource_type = helpers.get_no_module_name(resource).split(".")[0]
        other = get_provider_for_resource(resource)
        if other in SUPPORTED_PROVIDERS and other != provider:
            foreign.add(resource_type)
    if foreign:
        tfdata["hidden"] = sorted(set(tfdata["hidden"]) | foreign)
        click.echo(
            click.style(
                f"\nSkipping {len(foreign)} resource type(s) from other clouds "
                f"({', '.join(sorted(foreign))}) - diagrams render one provider "
                "at a time.",
                fg="yellow",
            )
        )

    _apply_size_overrides(tfdata)

    # Snapshot meta_data before drawing (drawing overwrites entries with {"node": ...})
    # Used by HTML renderer to show metadata for drawn resources
    import copy as _copy

    tfdata["pre_draw_metadata"] = _copy.deepcopy(tfdata.get("meta_data", {}))

    # Track already drawn resources to prevent duplicates
    all_drawn_resources_list = list()
    tfdata["deferred_connections"] = list()

    # Pre-compute flow badges (US5) before drawing starts
    from modules.annotations import compute_flow_step_numbers

    _flows = (tfdata.get("annotations") or {}).get("flows") or {}
    _node_badges, _edge_badges, _legend_entries = compute_flow_step_numbers(_flows)
    tfdata["flow_badges"] = {
        res: generate_badge_xlabel(sorted(nums)) for res, nums in _node_badges.items()
    }
    tfdata["flow_edge_badges"] = {
        key: generate_badge_xlabel(sorted(nums)) for key, nums in _edge_badges.items()
    }
    tfdata["flow_legend_entries"] = _legend_entries

    # Initialize diagram canvas
    title = (
        "Cloud Architecture Diagram"
        if not tfdata["annotations"].get("title")
        else tfdata["annotations"]["title"]
    )
    # Use 'neato' engine for all providers with neato_no_op=2
    # GCP diagrams use black connectors per Google reference architecture style
    edge_attr = {"color": "#000000"} if provider == "gcp" else {}
    myDiagram = Canvas(
        "",
        filename=outfile,
        outformat=outformat,
        show=show,
        direction="TB",
        engine="neato",
        edge_attr=edge_attr,
    )
    setdiagram(myDiagram)

    # Create main cloud provider boundary
    provider_group_name = provider.upper() + "Group"
    cloud_group_class = globals().get(provider_group_name)
    if cloud_group_class is None:
        click.echo(
            click.style(
                f"\nERROR: No group class '{provider_group_name}' found for provider '{provider}'. Exiting.",
                fg="red",
                bold=True,
            )
        )
        exit()

    # Add title as a node at the top (positioned by gvpr for all providers)
    setcluster(myDiagram)
    title_style = {
        "_titlenode": "1",
        "shape": "plaintext",
        "fontsize": "56",
        "fontname": "Sans-Serif",
        "fontcolor": "#2D3436",
        "label": title,
    }
    getattr(sys.modules[__name__], "Node")(**title_style)

    cloudGroup = cloud_group_class()
    setcluster(cloudGroup)
    tfdata["connected_nodes"] = dict()

    # Draw resources in predefined order for optimal layout
    for node_type_list in DRAW_ORDER:
        # Outer nodes go directly on canvas, others in cloud group
        targetGroup = cloudGroup
        if node_type_list == OUTER_NODES:
            targetGroup = myDiagram
        setcluster(targetGroup)
        all_drawn_resources_list = draw_objects(
            node_type_list, all_drawn_resources_list, tfdata, myDiagram, cloudGroup
        )

    # Process deferred connections after all nodes are drawn
    if tfdata.get("deferred_connections"):
        for origin_resource, dest_resource in tfdata["deferred_connections"]:
            if (
                dest_resource in tfdata["meta_data"]
                and "node" in tfdata["meta_data"][dest_resource]
            ):
                if (
                    origin_resource in tfdata["meta_data"]
                    and "node" in tfdata["meta_data"][origin_resource]
                ):
                    originNode = tfdata["meta_data"][origin_resource]["node"]
                    connectedNode = tfdata["meta_data"][dest_resource]["node"]
                    origin_type = helpers.get_no_module_name(origin_resource).split(
                        "."
                    )[0]
                    dest_type = helpers.get_no_module_name(dest_resource).split(".")[0]

                    if originNode != connectedNode and ok_to_connect(
                        origin_type, dest_type
                    ):
                        label = get_edge_labels(originNode, connectedNode, tfdata)
                        line_style = (
                            "solid"
                            if always_draw_edge(origin_type, dest_type, tfdata)
                            else "invis"
                        )
                        # Check if this is a bidirectional link
                        is_bidir = frozenset(
                            (origin_resource, dest_resource)
                        ) in tfdata.get("bidirectional_edges", set())
                        originNode.connect(
                            connectedNode,
                            _make_edge_with_badge(
                                tfdata,
                                origin_resource,
                                dest_resource,
                                forward=True,
                                reverse=is_bidir,
                                label=label,
                                style=line_style,
                            ),
                        )
                        if not tfdata["connected_nodes"].get(originNode._id):
                            tfdata["connected_nodes"][originNode._id] = list()
                        tfdata["connected_nodes"][originNode._id] = (
                            helpers.append_dictlist(
                                tfdata["connected_nodes"][originNode._id],
                                connectedNode._id,
                            )
                        )
                        # For bidirectional edges, also track the reverse
                        if is_bidir:
                            if not tfdata["connected_nodes"].get(connectedNode._id):
                                tfdata["connected_nodes"][connectedNode._id] = list()
                            tfdata["connected_nodes"][connectedNode._id] = (
                                helpers.append_dictlist(
                                    tfdata["connected_nodes"][connectedNode._id],
                                    originNode._id,
                                )
                            )

    # Apply flow badge xlabels to drawn nodes (US5 T034)
    _apply_flow_badges(tfdata, myDiagram, cloudGroup)

    # Add footer with metadata
    if source == ".":
        source = os.getcwd()

    # Group-to-group links need every cluster to exist first
    _draw_group_links(tfdata, myDiagram)

    # Set context to main diagram so footer is outside all clusters
    setcluster(myDiagram)

    # Add footer node (positioned by gvpr for all providers).
    # Width kept moderate so the legend node (when present) fits
    # alongside it on the same row instead of stacking below.
    footer_style = {
        "_footernode": "1",
        "shape": "record",
        "width": "14",
        "height": "2.0",
        "fontsize": "20",
        "margin": "0.4,0.3",
        "label": f"Machine generated using TerraVision v{_TERRAVISION_VERSION}|{{ Timestamp:|Source: }}|{{ {datetime.datetime.now()}|{source} }}",
    }
    getattr(sys.modules[__name__], "Node")(**footer_style)

    # Add flow legend node if any flows were defined (US5 T036)
    _add_legend_node(tfdata, myDiagram)

    # Create label node for cloud group if it has label metadata
    create_cluster_label_node(cloudGroup)

    # Add cloud group to main canvas
    myDiagram.subgraph(cloudGroup.dot)

    # Generate initial DOT file
    path_to_predot = myDiagram.pre_render()

    if announce_render:
        # Post-process with Graphviz
        click.echo(
            click.style(f"\nRendering Architecture Image...", fg="white", bold=True)
        )

    # Apply label positioning script
    path_to_postdot = _run_gvpr_label_shift(path_to_predot, outfile)

    return myDiagram, path_to_predot, path_to_postdot


def generate_dot(
    tfdata: Dict[str, Any],
    outfile: str,
    source: str,
) -> Tuple[str, Set[str], Dict[str, str], Dict[str, str]]:
    """Generate a post-processed DOT string from tfdata.

    Builds the complete Graphviz DOT graph (nodes, clusters, edges, footer),
    runs the gvpr label positioning script, and returns the DOT string along
    with the set of icon file paths referenced in the graph.

    Args:
        tfdata: Terraform data dictionary with graphdict, meta_data, annotations
        outfile: Output filename stem (used for temp DOT files)
        source: Source path or URL for footer attribution

    Returns:
        Tuple of (dot_string, icon_paths, node_id_map, cluster_id_map) where
        dot_string is the post-processed DOT source, icon_paths is a set of
        absolute paths to icon files used, node_id_map maps Graphviz node IDs
        to Terraform addresses and cluster_id_map maps cluster IDs.
    """
    myDiagram, path_to_predot, path_to_postdot = _build_diagram(
        tfdata, outfile, source, outformat="dot", show=False
    )

    # Read the post-processed DOT string
    with open(path_to_postdot, "r", encoding="utf-8") as f:
        dot_string = f.read()

    # Extract icon file paths from DOT string (both image="..." and <img src="..."/>)
    icon_paths = set(re.findall(r'image="([^"]+)"', dot_string))
    icon_paths.update(re.findall(r'<img src="([^"]+)"', dot_string))

    # Build mapping from Graphviz node ID to Terraform resource address
    # After drawing, meta_data[resource] = {"node": newNode} where resource is
    # the Terraform address and newNode._id is the Graphviz UUID
    node_id_map = {}
    for tf_address, meta_val in tfdata.get("meta_data", {}).items():
        if isinstance(meta_val, dict) and "node" in meta_val:
            node_obj = meta_val["node"]
            if hasattr(node_obj, "_id"):
                node_id_map[node_obj._id] = tf_address

    # Clean up the pre-gvpr temporary DOT file (the post-processed
    # <outfile>.dot is the deliverable and is kept)
    os.remove(path_to_predot)

    # Include cluster ID mapping
    cluster_id_map = tfdata.get("cluster_id_map", {})

    setdiagram(None)
    return dot_string, icon_paths, node_id_map, cluster_id_map


def _embed_icons_as_data_uris(text: str, icon_paths: Set[str]) -> str:
    """Replace local icon file paths in text with base64 data URIs.

    Paths that don't exist on disk are left untouched.
    """
    for icon_path in icon_paths:
        if os.path.isfile(icon_path):
            with open(icon_path, "rb") as f:
                icon_data = f.read()
            ext = os.path.splitext(icon_path)[1].lower()
            mime = {
                ".png": "image/png",
                ".svg": "image/svg+xml",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
            }.get(ext, "image/png")
            b64 = base64.b64encode(icon_data).decode("ascii")
            data_uri = f"data:{mime};base64,{b64}"
            text = text.replace(icon_path, data_uri)
    return text


def make_svg_portable(svg_path: str) -> None:
    """Rewrite local image references in a rendered SVG file to data URIs.

    Graphviz emits <image xlink:href="/abs/path/icon.png"> entries pointing at
    icon files inside the TerraVision installation, which break when the SVG
    is opened on another machine or served from a docs site. Embedding the
    icons as base64 data URIs makes the SVG self-contained.
    """
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_string = f.read()
    referenced = set(re.findall(r'(?:xlink:href|href)="([^"]+)"', svg_string))
    icon_paths = {p for p in referenced if not p.startswith("data:")}
    svg_string = _embed_icons_as_data_uris(svg_string, icon_paths)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_string)


def generate_svg(
    tfdata: Dict[str, Any],
    outfile: str,
    source: str,
) -> Tuple[str, Set[str]]:
    """Generate an SVG string from tfdata using the local Graphviz installation.

    Calls generate_dot() to build the DOT, renders to SVG via Graphviz neato,
    then replaces icon file paths with base64 data URIs in the SVG output.

    Returns:
        Tuple of (svg_string, icon_paths) where svg_string is the rendered SVG
        with all icons embedded as base64 data URIs.
    """
    from graphviz import Source

    dot_string, icon_paths, node_id_map, cluster_id_map = generate_dot(
        tfdata, outfile, source
    )

    # Write DOT (with original file paths) to a temp file, render to SVG
    temp_dot_path = Path.cwd() / f"{outfile}_html_temp.dot"
    with open(temp_dot_path, "w", encoding="utf-8") as f:
        f.write(dot_string)

    dotsource = Source.from_file(
        str(temp_dot_path), engine="neato", directory=Path.cwd()
    )
    svg_path = dotsource.render(
        format="svg", quiet=True, engine="neato", neato_no_op=2, directory=Path.cwd()
    )

    with open(svg_path, "r", encoding="utf-8") as f:
        svg_string = f.read()

    # Clean up temp files
    os.remove(temp_dot_path)
    os.remove(svg_path)

    # Now replace icon file paths with base64 data URIs in the SVG output
    svg_string = _embed_icons_as_data_uris(svg_string, icon_paths)

    return svg_string, icon_paths, node_id_map, cluster_id_map


def render_diagram(
    tfdata: Dict[str, Any],
    picshow: bool,
    outfile: str,
    format: str,
    source: str,
) -> None:
    """Main control function for rendering the architecture diagram.

    Orchestrates the entire diagram generation process: creates canvas,
    draws nodes and groups in order, adds footer, and renders final output.

    Args:
        tfdata: Terraform data dictionary with graphdict, meta_data, annotations
        picshow: Whether to automatically open the diagram after generation
        outfile: Output filename without extension
        format: Output format (png, svg, pdf, bmp, drawio)
        source: Source path or URL for footer attribution

    Returns:
        None (generates diagram file as side effect)
    """
    myDiagram, path_to_predot, path_to_postdot = _build_diagram(
        tfdata, outfile, source, outformat=format, show=picshow, announce_render=True
    )

    # Handle draw.io format conversion
    if format == "drawio":
        from modules.xdot_parser import run_xdot, parse_xdot
        from modules.drawio_emitter import emit_drawio, load_shape_map

        # Run Graphviz to get layout coordinates from post-processed DOT
        try:
            json_output = run_xdot(str(path_to_postdot))
            xdot_graph = parse_xdot(json_output)
        except Exception as e:
            click.echo(
                click.style(
                    f"Error: Failed to parse layout data from Graphviz: {e}\n"
                    "Check that Graphviz is installed and supports JSON output.",
                    fg="red",
                )
            )
            sys.exit(1)

        # Load provider-specific shape mapping
        provider = get_primary_provider_or_default(tfdata)
        shape_map = load_shape_map(provider)

        # Emit mxGraph XML
        xml_content = emit_drawio(
            xdot_graph,
            shape_map,
            set(),
            tfdata.get("node_id_map", {}),
            tfdata.get("cluster_id_map", {}),
            provider=provider,
        )

        # Write output
        drawio_output = Path.cwd() / f"{outfile}.drawio"
        with open(drawio_output, "w", encoding="utf-8") as f:
            f.write(xml_content)
        click.echo(f"  Output file: {drawio_output}")

        # Auto-open if --show flag is set. On WSL, click.launch's
        # xdg-open fallback is broken, so route through wslview;
        # everywhere else keep the original click.launch path.
        if picshow:
            if helpers.is_wsl():
                opened = helpers.wsl_open(str(drawio_output))
            else:
                opened = bool(click.launch(str(drawio_output)))
            if not opened:
                # No app associated with .drawio (or wslview missing).
                click.echo(
                    "  No draw.io desktop app found. "
                    "Open https://app.diagrams.net and use File > Open "
                    f"to load {drawio_output}"
                )

        # Clean up temporary files
        os.remove(path_to_predot)
        os.remove(path_to_postdot)
    else:
        # Generate final output file using graphviz
        rendered_file = myDiagram.render()
        if format == "svg":
            # Embed icons as data URIs so the SVG is portable (issue #207)
            make_svg_portable(rendered_file)
        click.echo(f"  Output file: {rendered_file}")
        # Clean up temporary files
        os.remove(path_to_predot)
        os.remove(path_to_postdot)

    click.echo(f"  Completed!")
    setdiagram(None)
