"""Drawing module for TerraVision.

This module handles the rendering of Terraform infrastructure as architecture diagrams.
It processes the graph data structure and creates visual representations using Graphviz,
including nodes, clusters, connections, and edge labels.
"""

import datetime
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import click

import modules.cloud_config as cloud_config
import modules.helpers as helpers

# pylint: disable=unused-wildcard-import
from resource_classes import *
from resource_classes.aws.analytics import *
from resource_classes.aws.ar import *
from resource_classes.aws.blockchain import *
from resource_classes.aws.business import *
from resource_classes.aws.compute import *
from resource_classes.aws.cost import *
from resource_classes.aws.database import *
from resource_classes.aws.devtools import *
from resource_classes.aws.enablement import *
from resource_classes.aws.enduser import *
from resource_classes.aws.engagement import *
from resource_classes.aws.game import *
from resource_classes.aws.general import *
from resource_classes.aws.groups import *
from resource_classes.aws.integration import *
from resource_classes.aws.iot import *
from resource_classes.aws.management import *
from resource_classes.aws.media import *
from resource_classes.aws.migration import *
from resource_classes.aws.ml import *
from resource_classes.aws.mobile import *
from resource_classes.aws.network import *
from resource_classes.aws.quantum import *
from resource_classes.aws.robotics import *
from resource_classes.aws.satellite import *
from resource_classes.aws.security import *
from resource_classes.aws.storage import *
# Azure resource classes
from resource_classes.azure.aimachinelearning import *
from resource_classes.azure.analytics import *
from resource_classes.azure.appservices import *
from resource_classes.azure.azureecosystem import *
from resource_classes.azure.azurestack import *
from resource_classes.azure.blockchain import *
from resource_classes.azure.compute import *
from resource_classes.azure.containers import *
from resource_classes.azure.database import *
from resource_classes.azure.databases import *
from resource_classes.azure.devops import *
from resource_classes.azure.general import *
from resource_classes.azure.hybridmulticloud import *
from resource_classes.azure.identity import *
from resource_classes.azure.integration import *
from resource_classes.azure.intune import *
from resource_classes.azure.iot import *
from resource_classes.azure.managementgovernance import *
from resource_classes.azure.migrate import *
from resource_classes.azure.migration import *
from resource_classes.azure.mixedreality import *
from resource_classes.azure.ml import *
from resource_classes.azure.mobile import *
from resource_classes.azure.monitor import *
from resource_classes.azure.network import *
from resource_classes.azure.networking import *
from resource_classes.azure.newicons import *
from resource_classes.azure.other import *
from resource_classes.azure.security import *
from resource_classes.azure.storage import *
from resource_classes.azure.web import *
from resource_classes.generic.blank import Blank
# Import group classes (must come after resource class imports to override)
from resource_classes.aws.groups import AWSgroup
from resource_classes.azure.groups import (
    Azuregroup,
    azurerm_resource_group,
    azurerm_virtual_network,
    azurerm_subnet,
    azurerm_network_security_group,
)

avl_classes = dir()

# Default to AWS configuration (will be overridden based on provider detection)
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
GROUP_NODES = cloud_config.AWS_GROUP_NODES
DRAW_ORDER = cloud_config.AWS_DRAW_ORDER
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
OUTER_NODES = cloud_config.AWS_OUTER_NODES
AUTO_ANNOTATIONS = cloud_config.AWS_AUTO_ANNOTATIONS
OUTER_NODES = cloud_config.AWS_OUTER_NODES
EDGE_NODES = cloud_config.AWS_EDGE_NODES
SHARED_SERVICES = cloud_config.AWS_SHARED_SERVICES
ALWAYS_DRAW_LINE = cloud_config.AWS_ALWAYS_DRAW_LINE
NEVER_DRAW_LINE = cloud_config.AWS_NEVER_DRAW_LINE


def set_provider_config(provider: str) -> None:
    """Set global configuration based on detected cloud provider.

    Args:
        provider: Cloud provider name ('aws', 'azure', or 'gcp')
    """
    global CONSOLIDATED_NODES, GROUP_NODES, DRAW_ORDER, NODE_VARIANTS
    global OUTER_NODES, AUTO_ANNOTATIONS, EDGE_NODES, SHARED_SERVICES
    global ALWAYS_DRAW_LINE, NEVER_DRAW_LINE

    if provider == "azure":
        CONSOLIDATED_NODES = cloud_config.AZURE_CONSOLIDATED_NODES
        GROUP_NODES = cloud_config.AZURE_GROUP_NODES
        DRAW_ORDER = cloud_config.AZURE_DRAW_ORDER
        NODE_VARIANTS = cloud_config.AZURE_NODE_VARIANTS
        OUTER_NODES = cloud_config.AZURE_OUTER_NODES
        AUTO_ANNOTATIONS = cloud_config.AZURE_AUTO_ANNOTATIONS
        EDGE_NODES = cloud_config.AZURE_EDGE_NODES
        SHARED_SERVICES = cloud_config.AZURE_SHARED_SERVICES
        ALWAYS_DRAW_LINE = cloud_config.AZURE_ALWAYS_DRAW_LINE
        NEVER_DRAW_LINE = cloud_config.AZURE_NEVER_DRAW_LINE
    else:  # Default to AWS
        CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
        GROUP_NODES = cloud_config.AWS_GROUP_NODES
        DRAW_ORDER = cloud_config.AWS_DRAW_ORDER
        NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
        OUTER_NODES = cloud_config.AWS_OUTER_NODES
        AUTO_ANNOTATIONS = cloud_config.AWS_AUTO_ANNOTATIONS
        EDGE_NODES = cloud_config.AWS_EDGE_NODES
        SHARED_SERVICES = cloud_config.AWS_SHARED_SERVICES
        ALWAYS_DRAW_LINE = cloud_config.AWS_ALWAYS_DRAW_LINE
        NEVER_DRAW_LINE = cloud_config.AWS_NEVER_DRAW_LINE


def get_cloud_group(provider: str):
    """Get the appropriate cloud group class based on provider.

    Args:
        provider: Cloud provider name ('aws', 'azure', or 'gcp')

    Returns:
        Cloud group instance (AWSgroup or Azuregroup)
    """
    if provider == "azure":
        return Azuregroup()
    else:  # Default to AWS
        return AWSgroup()


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
    if resource_type not in avl_classes:
        return

    # Reuse existing node if already drawn
    if resource in drawn_resources:
        newNode = tfdata["meta_data"][resource]["node"]
    else:
        # Create new node and add to appropriate group
        targetGroup = diagramCanvas if resource_type in OUTER_NODES else inGroup
        node_label = helpers.pretty_name(resource)
        setcluster(targetGroup)
        nodeClass = getattr(sys.modules[__name__], resource_type)
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
                if (
                    node_type in avl_classes
                    and resource != node_connection
                    and node_connection in tfdata["graphdict"].keys()
                ):
                    # Detect circular references to prevent infinite recursion
                    circular_reference = (
                        resource in tfdata["graphdict"][node_connection]
                    )

                    if not circular_reference:
                        # Recursively handle connected node
                        connectedNode, drawn_resources = handle_nodes(
                            node_connection,
                            connectedGroup,
                            cloudGroup,
                            diagramCanvas,
                            tfdata,
                            drawn_resources,
                        )
                    elif node_connection not in drawn_resources:
                        # Draw circular reference node without recursion
                        nodeClass = getattr(sys.modules[__name__], node_type)
                        connectedNode = nodeClass(
                            label=helpers.pretty_name(node_connection),
                            tf_resource_name=node_connection,
                        )
                        drawn_resources.append(node_connection)
                        tfdata["meta_data"].update(
                            {node_connection: {"node": connectedNode}}
                        )

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
    if resource_type not in avl_classes:
        return

    # Create new group/cluster
    newGroup = getattr(sys.modules[__name__], resource_type)(
        label=helpers.pretty_name(resource)
    )
    targetGroup = diagramCanvas if resource_type in OUTER_NODES else inGroup
    targetGroup.subgraph(newGroup.dot)
    drawn_resources.append(resource)

    # Add child nodes and subgroups
    if tfdata["graphdict"].get(resource):
        for node_connection in tfdata["graphdict"][resource]:
            node_type = str(helpers.get_no_module_name(node_connection).split(".")[0])

            # Handle nested subgroups
            if node_type in GROUP_NODES and node_type in avl_classes:
                subGroup, drawn_resources = handle_group(
                    newGroup,
                    cloudGroup,
                    diagramCanvas,
                    node_connection,
                    tfdata,
                    drawn_resources,
                )
                newGroup.subgraph(subGroup.dot)
                drawn_resources.append(node_connection)

            # Handle regular nodes within the group
            elif (
                node_type not in GROUP_NODES
                and node_type in avl_classes
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
                newGroup.add_node(
                    newNode._id, label=helpers.pretty_name(node_connection)
                )

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
    # Get provider from tfdata and configure accordingly
    provider = tfdata.get("provider", "aws")
    set_provider_config(provider)
    click.echo(f"Using {provider.upper()} configuration for diagram rendering")

    # Track already drawn resources to prevent duplicates
    all_drawn_resources_list = list()

    # Initialize diagram canvas
    title = (
        "Untitled"
        if not tfdata["annotations"].get("title")
        else tfdata["annotations"]["title"]
    )
    myDiagram = Canvas(
        title, filename=outfile, outformat=format, show=picshow, direction="TB"
    )
    setdiagram(myDiagram)

    # Create main cloud provider boundary with correct provider group
    cloudGroup = get_cloud_group(provider)
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

    # Add footer with metadata
    if str(source) == "('.',)":
        source = os.getcwd()

    footer_style = {
        "_footernode": "1",
        "shape": "record",
        "width": "25",
        "height": "2",
        "fontsize": "18",
        "label": f"Machine generated using terravision|{{ Timestamp:|Source: }}|{{ {datetime.datetime.now()}|{str(source)} }}",
    }
    getattr(sys.modules[__name__], "Node")(**footer_style)

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
