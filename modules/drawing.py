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
    "tv_aws_availability_zone",  # terravision custom resource
    "aws_appautoscaling_target",
    "aws_subnet",
    "aws_security_group",
    "aws_generic_group",
    "tv_aws_onprem",
]

AWS_DRAW_ORDER = [
    GROUP_NODES,
    CONSOLIDATED_NODES,
]

AWS_AUTO_ANNOTATION = [
    {"aws_route53": {"create": "Users", "link": "forward"}},
    {"aws_route53": {"create": "Users", "link": "forward"}},
]


# Variant icons for the same service - matches keyword in meta data to suffix after underscore
NODE_VARIANTS = {"aws_ecs_service": {"FARGATE": "_fargate", "EC2": "_ec2"}}

# Master Cluster
aws_group = Cluster

# Internal tracking dict for nodes and their connections (for future use)
connected_nodes = dict()

# Main control body for drawing
def render_diagram(
    tfdata: dict,
    picshow: bool,
    simplified: bool,
    outfile,
    format,
    source,
):
    global aws_group
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
    aws_group = AWSgroup()
    setcluster(aws_group)
    vpc_exists = False
    # Draw Nodes and Groups in order of static definitions
    for nodeTypeList in AWS_DRAW_ORDER:
        for nodeType in nodeTypeList:
            for resource, connections_list in tfdata['graphdict'].items():
                if resource.startswith("aws_vpc."):
                    vpc_exists = True
                if isinstance(nodeType,dict) :
                    nodeType = str(list(nodeType.keys())[0])
                if resource.startswith(nodeType) :
                    getattr(sys.modules[__name__], "Node")(label = helpers.pretty_name(nodeType))
        
         
 
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
