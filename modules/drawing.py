from distutils.command.check import check
import modules.helpers as helpers
import click
import os
import sys
from pathlib import Path
import modules.helpers as helpers
import modules.cloud_config as cloud_config

import datetime

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
from resource_classes.generic.blank import Blank

avl_classes = dir()

CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
GROUP_NODES = cloud_config.AWS_GROUP_NODES
DRAW_ORDER = cloud_config.AWS_DRAW_ORDER
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS
OUTER_NODES = cloud_config.AWS_OUTER_NODES


def get_edge_labels(origin: Node, destination: Node, tfdata: dict):
    # Check if there are any custom edge 
    label = ""
    origin_resource = origin._attrs["tf_resource_name"]
    dest_resource = destination._attrs["tf_resource_name"]
    consolidated_dest_prefix = [
        k
        for k in list(CONSOLIDATED_NODES)
        if dest_resource.startswith(list(k.keys())[0])
    ]
    consolidated_origin_prefix = [
        k
        for k in CONSOLIDATED_NODES
        if origin_resource.startswith(list(k.keys())[0])
    ]
    if consolidated_origin_prefix:
        candidate_resources = helpers.list_of_dictkeys_containing(
            tfdata["meta_data"],
            list(consolidated_origin_prefix[0].keys())[0],
        )
        for resource in candidate_resources:
            edge_labels_list = tfdata["meta_data"][resource].get(
                "edge_labels"
            )
            if edge_labels_list:
                break
    else:
        edge_labels_list = tfdata["meta_data"][origin_resource].get(
            "edge_labels"
        )
    if edge_labels_list:
        for labeldict in edge_labels_list:
            key = [k for k in labeldict][0]
            if key == dest_resource or (
                consolidated_dest_prefix
                and key.startswith(list(consolidated_dest_prefix[0].keys())[0])
            ):
                label = labeldict[key]
                break
    return label


# Recursive function to draw out nodes along with any nodes connected to them
def handle_nodes(
    new_resource: str,
    inGroup: Cluster,
    cloudGroup: Cluster,
    tfdata: dict,
    drawn_resources: list,
    outer_node: False,
):
    # For consolidated nodes, get the standardised resource name which doesn't exist in Terraform
    consolidated_resource = consolidated_node_check(new_resource)
    if consolidated_resource:
        resource = consolidated_resource
    else:
        resource = new_resource
    resource_type = resource.split(".")[0]
    if not resource_type in avl_classes:
        return
    # If we have already drawn this node as part of a previous loop of other connections just get node ID
    if resource in drawn_resources:
        newNode = tfdata["meta_data"][resource]["node"]
    else:
        # Draw the node if applicable and record node ID
        node_label = helpers.pretty_name(resource)
        nodeClass = getattr(sys.modules[__name__], resource_type)
        newNode = nodeClass(label=node_label, tf_resource_name=resource)
        drawn_resources.append(resource)
        tfdata["meta_data"].update({resource: {"node": newNode}})
    # Now draw and connect any nodes listed as a connection in graphdict
    for node_connection in tfdata["graphdict"][new_resource]:
        connectedNode = None
        node_type = str(node_connection).split(".")[0]
        # Ensure any connections from outside nodes to inside cloud nodes appear correctly
        if outer_node == True and node_type not in OUTER_NODES:
            connectedGroup = cloudGroup
        else:
            connectedGroup = inGroup
        if node_type not in GROUP_NODES:
            if node_type in avl_classes:
                connectedNode, drawn_resources = handle_nodes(
                    node_connection,
                    connectedGroup,
                    cloudGroup,
                    tfdata,
                    drawn_resources,
                    outer_node,
                )
            if connectedNode:
                # We have found a connection linked to newNode we just created
                label = get_edge_labels(newNode, connectedNode, tfdata) 
                # Log connections in tfdata and don't duplicate existing connections
                # Use consolidated_node when appropriate
                if not tfdata["connected_nodes"].get(newNode._id) and tfdata["meta_data"][resource]["node"]:
                    originNode = tfdata["meta_data"][resource]["node"]
                else:
                    originNode = newNode
                if not tfdata["connected_nodes"].get(
                    originNode._id
                ) or not connectedNode._id in tfdata["connected_nodes"].get(
                    originNode._id
                ):
                    originNode.connect(connectedNode, Edge(forward=True, label=label))
                    if not tfdata["connected_nodes"].get(originNode._id):
                        tfdata["connected_nodes"][originNode._id] = list()
                    tfdata["connected_nodes"][originNode._id] = helpers.append_dictlist(tfdata["connected_nodes"][originNode._id],connectedNode._id ) #[connectedNode._id]
    return newNode, drawn_resources


# Takes a resource and returns a standardised consolidated node if matched with the static definitions
def consolidated_node_check(resource_type: str):
    for checknode in CONSOLIDATED_NODES:
        prefix = str(list(checknode.keys())[0])
        if resource_type.startswith(prefix):
            return checknode[prefix]["resource_name"]
    return False


# Recursive function to draw out groups and subgroups along with their nodes
def handle_group(
    cloudGroup: object,
    resource: str,
    tfdata: dict,
    drawn_resources: list,
    outer_node: False,
):
    resource_type = resource.split(".")[0]
    if not resource_type in avl_classes:
        return
    newGroup = getattr(sys.modules[__name__], resource_type)(label=helpers.pretty_name(resource))
    cloudGroup.subgraph(newGroup.dot)
    drawn_resources.append(resource)
    # Now add in any nodes contained within this group
    for node_connection in tfdata["graphdict"][resource]:
        node_type = str(node_connection).split(".")[0]
        if node_type in GROUP_NODES and node_type in avl_classes:
            subGroup, drawn_resources = handle_group(
                newGroup, node_connection, tfdata, drawn_resources, outer_node
            )
            newGroup.subgraph(subGroup.dot)
            drawn_resources.append(node_connection)
        elif (
            node_type not in GROUP_NODES
            and node_type in avl_classes
            and not consolidated_node_check(node_type)
        ):
            newNode, drawn_resources = handle_nodes(
                node_connection,
                newGroup,
                cloudGroup,
                tfdata,
                drawn_resources,
                outer_node,
            )
            newGroup.add_node(newNode._id, label=helpers.pretty_name(node_connection))
    return newGroup, drawn_resources


# Loop routine that calls handle_group or handle_node for each resource in graphdict
def draw_objects(
    node_type_list: list,
    all_drawn_resources_list: list,
    tfdata: dict,
    targetGroup: object,
    cloudGroup: object,
    outer_node: bool,
):
   
    for node_type in node_type_list:
        if isinstance(node_type, dict):
            node_check = str(list(node_type.keys())[0])
        else:
            node_check = node_type
        for resource in tfdata["graphdict"]:
            resource_type = resource.split(".")[0]
            if resource_type in avl_classes:
                if (
                    resource_type.startswith(node_check)
                    and resource_type in GROUP_NODES
                    and resource not in all_drawn_resources_list
                ):
                    # Create new subgroups and their nodes and add it to the supplied cluster
                    node_groups, all_drawn_resources_list = handle_group(
                        targetGroup,
                        resource,
                        tfdata,
                        all_drawn_resources_list,
                        outer_node,
                    )
                    targetGroup.subgraph(node_groups.dot)
                elif (
                    resource_type.startswith(node_check)
                    and not resource_type in GROUP_NODES
                    and resource not in all_drawn_resources_list
                ):
                    # Create standalone nodes and add them to the supplied cluster
                    newNode, all_drawn_resources_list = handle_nodes(
                        resource,
                        targetGroup,
                        cloudGroup,
                        tfdata,
                        all_drawn_resources_list,
                        outer_node,
                    )
    return all_drawn_resources_list


# Main control body for drawing
def render_diagram(
    tfdata: dict,
    picshow: bool,
    simplified: bool,
    outfile,
    format,
    source,
):
    # Dict to hold already drawn nodes
    all_drawn_resources_list = list()
    # Setup Canvas
    title = (
        "Untitled"
        if not tfdata["annotations"].get("title")
        else tfdata["annotations"]["title"]
    )
    myDiagram = Canvas(
        title, filename=outfile, outformat=format, show=picshow, direction="TB"
    )
    setdiagram(myDiagram)
    # Setup footer
    footer_style = {
        "_footernode": "1",
        "height": "0",
        "width": "0",
        "fontsize": "20",
        "label": f"Machine generated at {datetime.datetime.now()} using Terravision (https://terra-vision.net)\tSource: {str(source)}",
    }
    getattr(sys.modules[__name__], "Node")(**footer_style)
    # Setup Outer cloud boundary
    cloudGroup = AWSgroup()
    tfdata["connected_nodes"] = dict()
    # Draw Nodes and Groups in order of static definitions
    for node_type_list in DRAW_ORDER:
        targetGroup = myDiagram if node_type_list == OUTER_NODES else cloudGroup
        setcluster(targetGroup)
        all_drawn_resources_list = draw_objects(
            node_type_list,
            all_drawn_resources_list,
            tfdata,
            targetGroup,
            cloudGroup,
            node_type_list == OUTER_NODES,
        )
    # Add main outer cloud group to canvas
    myDiagram.subgraph(cloudGroup.dot)
    # Render completed DOT
    path_to_predot = myDiagram.pre_render()
    # Post Processing
    click.echo(click.style(f"\nRendering Architecture Image...", fg="white", bold=True))
    bundle_dir = Path(__file__).parent.parent
    path_to_script = Path.cwd() / bundle_dir / "shiftLabel.gvpr"
    path_to_postdot = Path.cwd() / f"{outfile}.dot"
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        os.system(
            f"gvpr -c -q -f {path_to_script} {path_to_predot} -o {path_to_postdot}"
        )
    else:
        os.system(f"gvpr -c -q -f {path_to_script} {outfile}.gv.dot -o {outfile}.dot")
    # Generate Final Output file
    click.echo(f"  Output file: {myDiagram.render()}")
    click.echo(f"  Completed!")
    setdiagram(None)
