from distutils.command.check import check
import modules.helpers as helpers
import click
import importlib
import json
import os
import sys
import time
from pathlib import Path
import modules.helpers as helpers
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
cloudGroup = Cluster

# Any resource names with certain prefixes are consolidated into one node
CONSOLIDATED_NODES = [
    {
        "aws_route53": {
            "resource_name": "aws_route53_record.route_53",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_cloudwatch": {
            "resource_name": "aws_cloudwatch_log_group.cloudwatch",
            "import_location": "resource_classes.aws.management",
            "vpc": False,
        }
    },
    {
        "aws_api_gateway": {
            "resource_name": "aws_api_gateway_integration.gateway",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
        }
    },
    {
        "aws_acm": {
            "resource_name": "aws_acm_certificate.acm",
            "import_location": "resource_classes.aws.security",
            "vpc": False,
        }
    },
    {
        "aws_ssm_parameter": {
            "resource_name": "aws_ssm_parameter.ssmparam",
            "import_location": "resource_classes.aws.management",
            "vpc": False,
        }
    },
    {
        "aws_dx": {
            "resource_name": "aws_dx_connection.directconnect",
            "import_location": "resource_classes.aws.network",
            "vpc": False,
            "edge_service": True,
        }
    },
    {
        "aws_lb": {
            "resource_name": "aws_lb.elb",
            "import_location": "resource_classes.aws.network",
            "vpc": True,
        }
    },
    {
        "aws_ecs": {
            "resource_name": "aws_ecs_service.ecs",
            "import_location": "resource_classes.aws.compute",
            "vpc": True,
        }
    },
    {
        "aws_rds": {
            "resource_name": "aws_rds_cluster.rds",
            "import_location": "resource_classes.aws.database",
            "vpc": True,
        }
    },
    {
        "aws_internet_gateway": {
            "resource_name": "aws_internet_gateway.*",
            "import_location": "resource_classes.aws.network",
            "vpc": True,
        },
    },
]

# List of Group type nodes and order to draw them in
GROUP_NODES = [
    "aws_vpc",
    "aws_appautoscaling_target",
    "aws_subnet",
    "aws_security_group"
]

AWS_DRAW_ORDER = [GROUP_NODES, CONSOLIDATED_NODES]

AWS_AUTO_ANNOTATION = [
    {"aws_route53": {"create": "Users", "link": "forward"}},
    {"aws_route53": {"create": "Users", "link": "forward"}},
]

# Variant icons for the same service - matches keyword in meta data to suffix after underscore
NODE_VARIANTS = {"aws_ecs_service": {"FARGATE": "_fargate", "EC2": "_ec2"}}


# Recursive function to draw out nodes along with any nodes connected to them
def handle_nodes(resource: str, inGroup: Cluster, tfdata: dict, drawn_resources: list) :
    resource_type = resource.split(".")[0]
    if not resource_type in avl_classes:
        return
    # Draw the node if applicable and record node ID
    newNode = getattr(sys.modules[__name__], resource_type)(label=resource, tf_resource_name=resource)
    inGroup.add_node(newNode._id, label=helpers.pretty_name(resource))
    drawn_resources.append(resource)
    tfdata["meta_data"].update({resource: {"node": newNode}})
    # Now draw and connect any nodes listed as a connection in graphdict
    for node_connection in tfdata['graphdict'][resource]:
        node_type = str(node_connection).split('.')[0]
        if node_type not in GROUP_NODES and node_type in avl_classes :
            connectedNode, drawn_resources, tfdata = handle_nodes(node_connection, inGroup, tfdata, drawn_resources)
            #connectedNode = getattr(sys.modules[__name__], node_type)(label=node_connection, tf_resource_name=node_connection)
            # tfdata["meta_data"].update({node_connection: {"node": newNode}})
            # drawn_resources.append(node_connection)
            newNode.connect(connectedNode, Edge(forward=True))
    return newNode, drawn_resources, tfdata


# Recursive function to draw out groups and subgroups along with their nodes
def handle_group(resource: str, tfdata: dict, drawn_resources: list) :
    resource_type = resource.split(".")[0]
    if not resource_type in avl_classes:
        return
    newGroup =  getattr(sys.modules[__name__], resource_type)(label=resource)
    # Now add in any nodes contained within this group
    for node_connection in tfdata['graphdict'][resource]:
        node_type = str(node_connection).split('.')[0]
        if node_type in GROUP_NODES and node_type in avl_classes:
            subGroup, drawn_resources, tfdata = handle_group(node_connection, tfdata, drawn_resources)
            newGroup.subgraph(subGroup.dot)
            drawn_resources.append(node_connection)
        elif node_type not in GROUP_NODES and node_type in avl_classes :
            newNode, drawn_resources, tfdata = handle_nodes(node_connection, newGroup, tfdata, drawn_resources)
            newGroup.add_node(newNode._id, label = node_connection)
    return newGroup, drawn_resources, tfdata

# Main control body for drawing
def render_diagram(
    tfdata: dict,
    picshow: bool,
    simplified: bool,
    outfile,
    format,
    source,
):
    global cloudGroup
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
    setcluster(cloudGroup)

    # Add all nodes to the list after specified node order
    AWS_DRAW_ORDER.append(tfdata['graphdict'].keys())
    # Draw Nodes and Groups in order of static definitions
    all_drawn_resources_list = list()
    for node_type_list in AWS_DRAW_ORDER:
        for node_type in node_type_list:
            if isinstance(node_type, dict) :
                node_check = str(list(node_type.keys())[0])
            else :
                node_check = node_type
            for resource in tfdata["graphdict"]:
                resource_type = resource.split(".")[0]
                if resource_type in avl_classes and node_check.startswith(resource_type) and node_check in GROUP_NODES and resource not in all_drawn_resources_list:
                    # Create new subgroups and their nodes and add it to the master cluster
                    node_groups, all_drawn_resources_list, tfdata = handle_group(resource, tfdata, all_drawn_resources_list)
                    cloudGroup.subgraph(node_groups.dot)
                elif resource_type in avl_classes and not resource_type in GROUP_NODES and resource not in all_drawn_resources_list:
                    # We have a higher level node outside known groups so add it to the master cluster
                    newNode, all_drawn_resources_list, tfdata = handle_nodes(resource, cloudGroup, tfdata, all_drawn_resources_list)
                    cloudGroup.add_node(newNode._id, label=resource)
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






                    # newGroup = getattr(sys.modules[__name__], resource_type)()
                    # cloudGroup.subgraph(newGroup._cluster.dot)
                    # for connectingNode in connections_list :
                    #     connectionType = connectingNode.split(".")[0]
                    #     if connectionType in avl_classes:
                    #         newNode = getattr(sys.modules[__name__], connectingNode.split('.')[0])( tf_resource_name=connectingNode)
                    #         newGroup.add_node(newNode)


                    
                    






                #     if not tfdata['meta_data'][resource].get('node') :
                #         newGroup = getattr(sys.modules[__name__], resource_type)()
                #         cloudGroup.subgraph(newGroup._diagram.dot)
                #         tfdata["meta_data"][resource]["node"] = newGroup
                #         for connected_node in connections_list :
                #             if connected_node in avl_classes:
                #                 newNode = getattr(sys.modules[__name__], connected_node)( label=helpers.pretty_name(connected_node),tf_resource_name=resource)
                #                 newGroup.add_node(newNode._id, label=helpers.pretty_name(connected_node))
                #                 tfdata["meta_data"][connected_node]["node"] = newNode
                # if resource_type in avl_classes and nodeCheck.startswith(resource_type) and nodeTypeList != GROUP_NODES:
                #     newNode = getattr(sys.modules[__name__], resource_type)( tf_resource_name=resource)
                #     cloudGroup.add_node(newNode._id, label=helpers.pretty_name(resource))




