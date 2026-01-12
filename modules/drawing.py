"""Drawing module for TerraVision.

This module handles the rendering of Terraform infrastructure as architecture diagrams.
It processes the graph data structure and creates visual representations using Graphviz,
including nodes, clusters, connections, and edge labels.
"""

import datetime
import importlib
import os
import pkgutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import click

import modules.config_loader as config_loader
import modules.helpers as helpers
from modules.provider_detector import get_primary_provider_or_default

# Import base resource classes
# pylint: disable=unused-wildcard-import
from resource_classes import *

# Generic resources (always needed)
from resource_classes.generic.blank import Blank

# Track available classes - will be populated dynamically per provider
avl_classes = []
_loaded_provider = None


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
ALWAYS_DRAW_LINE = []
NEVER_DRAW_LINE = []


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
    if resource_type not in avl_classes or resource_type in tfdata["hidden"]:
        return None, drawn_resources

    # Reuse existing node if already drawn
    if resource in drawn_resources:
        newNode = tfdata["meta_data"][resource]["node"]
    else:
        # Create new node and add to appropriate group
        is_outer = resource_type in OUTER_NODES
        targetGroup = diagramCanvas if is_outer else inGroup
        node_label = helpers.pretty_name(resource)
        setcluster(targetGroup)
        nodeClass = getattr(sys.modules[__name__], resource_type)
        # Only pass outer_node for GCP nodes (they use it for border styling)
        provider = get_primary_provider_or_default(tfdata)
        if provider == "gcp":
            newNode = nodeClass(
                label=node_label, tf_resource_name=resource, outer_node=is_outer
            )
        else:
            newNode = nodeClass(label=node_label, tf_resource_name=resource)
        drawn_resources.append(resource)
        tfdata["meta_data"].update({resource: {"node": newNode}})

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
                            nodeClass = getattr(sys.modules[__name__], node_type)
                            connectedNode = nodeClass(
                                label=helpers.pretty_name(node_connection),
                                tf_resource_name=node_connection,
                            )
                            drawn_resources.append(node_connection)
                            tfdata["meta_data"].update(
                                {node_connection: {"node": connectedNode}}
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
                            originNode.connect(
                                connectedNode,
                                Edge(forward=True, label=label, style=line_style),
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

    # Build HTML table label with icon and text (or just text if no icon)
    if hasattr(cluster_obj, "label_icon") and cluster_obj.label_icon is not None:
        icon_first = getattr(cluster_obj, "label_icon_first", True)
        if icon_first:
            label_html = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{cluster_obj.label_icon}"/></TD><TD>{cluster_obj.label_text}</TD></TR></TABLE>>'
        else:
            label_html = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD>{cluster_obj.label_text}</TD><TD><img src="{cluster_obj.label_icon}"/></TD></TR></TABLE>>'
    else:
        label_html = cluster_obj.label_text

    # Create label node with special attributes for gvpr positioning
    label_node_id = f"_label_{cluster_obj.dot.name}"
    cluster_type = cluster_obj.__class__.__name__
    cluster_obj.dot.node(
        label_node_id,
        label=label_html,
        shape="plaintext",
        pin="true",
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

    # Create new group/cluster
    newGroup = getattr(sys.modules[__name__], resource_type)(
        label=helpers.pretty_name(resource, is_group=True)
    )
    targetGroup = diagramCanvas if resource_type in OUTER_NODES else inGroup
    targetGroup.subgraph(newGroup.dot)
    drawn_resources.append(resource)

    # Create separate label node for clusters that have label metadata
    create_cluster_label_node(newGroup)

    # Add child nodes and subgroups
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

    return newGroup, drawn_resources


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

            if resource_type in avl_classes:
                # Draw group/cluster resources
                if (
                    resource_type.startswith(node_check)
                    and resource_type in GROUP_NODES
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
                    and resource_type not in GROUP_NODES
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


def render_diagram(
    tfdata: Dict[str, Any],
    picshow: bool,
    simplified: bool,
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
        simplified: Whether to generate a simplified high-level diagram
        outfile: Output filename without extension
        format: Output format (png, svg, pdf, bmp)
        source: Source path or URL for footer attribution

    Returns:
        None (generates diagram file as side effect)
    """
    # Load provider-specific configuration constants and set module globals
    global CONSOLIDATED_NODES, GROUP_NODES, DRAW_ORDER, NODE_VARIANTS
    global OUTER_NODES, AUTO_ANNOTATIONS, EDGE_NODES, SHARED_SERVICES
    global ALWAYS_DRAW_LINE, NEVER_DRAW_LINE

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

    # Track already drawn resources to prevent duplicates
    all_drawn_resources_list = list()
    tfdata["deferred_connections"] = list()

    # Initialize diagram canvas
    title = (
        "Cloud Architecture Diagram"
        if not tfdata["annotations"].get("title")
        else tfdata["annotations"]["title"]
    )
    # Use 'neato' engine for all providers with neato_no_op=2
    myDiagram = Canvas(
        "",
        filename=outfile,
        outformat=format,
        show=picshow,
        direction="TB",
        engine="neato",
    )
    setdiagram(myDiagram)

    # Create main cloud provider boundary
    # Dynamically select cloud group class based on provider (e.g., 'aws' -> 'AWSGroup', 'azure' -> 'AZUREGroup')
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
        "fontsize": "30",
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
                        originNode.connect(
                            connectedNode,
                            Edge(forward=True, label=label, style=line_style),
                        )
                        if not tfdata["connected_nodes"].get(originNode._id):
                            tfdata["connected_nodes"][originNode._id] = list()
                        tfdata["connected_nodes"][originNode._id] = (
                            helpers.append_dictlist(
                                tfdata["connected_nodes"][originNode._id],
                                connectedNode._id,
                            )
                        )

    # Add footer with metadata
    if str(source) == "('.',)":
        source = os.getcwd()

    # Set context to main diagram so footer is outside all clusters
    setcluster(myDiagram)

    # Add footer node (positioned by gvpr for all providers)
    footer_style = {
        "_footernode": "1",
        "shape": "record",
        "width": "25",
        "height": "2",
        "fontsize": "18",
        "label": f"Machine generated using TerraVision|{{ Timestamp:|Source: }}|{{ {datetime.datetime.now()}|{str(source)} }}",
    }
    getattr(sys.modules[__name__], "Node")(**footer_style)

    # Create label node for cloud group if it has label metadata
    create_cluster_label_node(cloudGroup)

    # Add cloud group to main canvas
    myDiagram.subgraph(cloudGroup.dot)

    # Generate initial DOT file
    path_to_predot = myDiagram.pre_render()

    # Post-process with Graphviz
    click.echo(click.style(f"\nRendering Architecture Image...", fg="white", bold=True))

    # Apply label positioning script
    bundle_dir = Path(__file__).parent.parent
    path_to_script = Path.cwd() / bundle_dir / "shiftLabel.gvpr"
    path_to_postdot = Path.cwd() / f"{outfile}.dot"
    os.system(f"gvpr -c -q -f {path_to_script} {path_to_predot} -o {path_to_postdot}")

    # Generate final output file
    click.echo(f"  Output file: {myDiagram.render()}")

    # Clean up temporary files
    os.remove(path_to_predot)
    os.remove(path_to_postdot)

    click.echo(f"  Completed!")
    setdiagram(None)
