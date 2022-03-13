from distutils.command.check import check
import modules.helpers as helpers
import click
import importlib
import json
import os
import sys
import time
from pathlib import Path
from modules.helpers import *
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
consolidated_nodes = {
    'aws_route53': {
        'resource_name': 'aws_route53_record.route_53',
        'import_location': 'resource_classes.aws.network',
        'vpc': False,
        'edge_service': True
    },
    'aws_cloudwatch': {
        'resource_name': 'aws_cloudwatch_log_group.cloudwatch',
        'import_location': 'resource_classes.aws.management',
        'vpc': False,
    },
    'aws_api_gateway': {
        'resource_name': 'aws_api_gateway_integration.gateway',
        'import_location': 'resource_classes.aws.network',
        'vpc': False,
    },
    'aws_acm': {
        'resource_name': 'aws_acm_certificate.acm',
        'import_location': 'resource_classes.aws.security',
        'vpc': False,
    },
    'aws_ssm_parameter': {
        'resource_name': 'aws_ssm_parameter.ssmparam',
        'import_location': 'resource_classes.aws.management',
        'vpc': False,
    },
    'aws_dx': {
        'resource_name': 'aws_dx_connection.directconnect',
        'import_location': 'resource_classes.aws.network',
        'vpc': False,
        'edge_service': True
    },
    'aws_lb': {
        'resource_name': 'aws_lb.elb',
        'import_location': 'resource_classes.aws.network',
        'vpc': True,
    },
    'aws_ecs': {
        'resource_name': 'aws_ecs_service.ecs',
        'import_location': 'resource_classes.aws.compute',
        'vpc': True,
    },
    'aws_rds': {
        'resource_name': 'aws_rds_cluster.rds',
        'import_location': 'resource_classes.aws.database',
        'vpc': True,
    },
    'aws_internet_gateway': {
        'resource_name': 'aws_internet_gateway.*',
        'import_location': 'resource_classes.aws.network',
        'vpc': True,
    },
}

group_nodes = [
    'aws_appautoscaling_target',
    'aws_vpc',
    'aws_subnet',
    'aws_security_group'
    'aws_generic_group'  # terravision custom resource
]


# Variant icons for the same service - matches keyword in meta data to suffix
node_variants = {
    'aws_ecs_service': {
        'FARGATE': '_fargate',
        'EC2': '_ec2'
    }
}

# Master Cluster
aws_group = Cluster


# Internal tracking dict for nodes and their connections (for future use)
connected_nodes = dict()


def check_variant(resource: str, metadata: dict) -> str:
    for variant_service in node_variants:
        if resource.startswith(variant_service):
            for keyword in node_variants[variant_service]:
                if keyword in str(metadata):
                    return node_variants[variant_service][keyword]
    return ''

def connect_up(origin: Node, destination: Node, metadata: dict) :
    # Check if there any edge labels
    label=''
    origin_resource = origin._attrs['tf_resource_name']
    dest_resource = destination._attrs['tf_resource_name']
    consolidated_dest_prefix = [k for k in consolidated_nodes if dest_resource.startswith(k)]
    consolidated_origin_prefix = [k for k in consolidated_nodes if origin_resource.startswith(k)]
    if consolidated_origin_prefix :
        candidate_resources = list_of_dictkeys_containing(metadata,consolidated_origin_prefix[0])
        for resource in candidate_resources:
            edge_labels_list = metadata[resource].get('edge_labels')
            if edge_labels_list:
                break
    else :
        edge_labels_list = metadata[origin_resource].get('edge_labels')
    if edge_labels_list:
        for labeldict in edge_labels_list:
            key = [k for k in labeldict][0]
            if key == dest_resource or (consolidated_dest_prefix and key.startswith(consolidated_dest_prefix[0])):
                label = labeldict[key]
                break
    origin.connect(destination,Edge(forward=True, label=label))

def handle_special_resources(tfdata: dict, graphdict: dict, resource: str):
    # Check if the resource is part of a LB target group and connect to LB
    referencers = find_resource_references(graphdict, resource)
    lb_found = list_of_dictkeys_containing(referencers, 'aws_lb')
    if lb_found:
        lb_nodes = list_of_dictkeys_containing(tfdata['meta_data'], 'aws_lb.')
        for nodename in lb_nodes:
            origin_node = tfdata['meta_data'][nodename]['node']
            dest_node = tfdata['meta_data'][resource]['node']
            # TODO: Make new function that logs connected
            # _nodes dict and then returns if already connected make+log connectors
            if not connected_nodes.get(origin_node._id) or not dest_node._id in connected_nodes.get(origin_node._id):
                origin_node >> dest_node
            if connected_nodes.get(origin_node._id):
                connected_nodes[origin_node._id].append(dest_node._id)
            else:
                connected_nodes[origin_node._id] = [dest_node._id]

    # Check if any NAT Gateways present and connect to IGW
    if resource.startswith('aws_nat_gateway.'):
        igw_found = list_of_dictkeys_containing(graphdict, 'aws_internet_gateway')
        dest_node = tfdata['meta_data'][igw_found[0]].get('node')
        origin_node = tfdata['meta_data'][resource]['node']
        origin_node >> dest_node


def draw_vpc_subnets(tfdata, graphdict, resource, connections_list):
    global aws_group
    # Function that draws n number of subnets in a VPC based on the count variable

    def draw_subnets():
        # Check if count option in Terraform is used in TF and create appropriate number of resources
        if tfdata['meta_data'][connected_item].get('count'):
            count = int(tfdata['meta_data'][connected_item]['count'])
        else:
            count = 1
        for i in range(count):
            has_elements = False
            if count > 1:
                subnet_identifier = connected_label + ' Subnet ' + str(i+1)
            else:
                subnet_identifier = connected_label
            subnet_identifier = cleanup(subnet_identifier + ' ' + tfdata['meta_data'][connected_item]['cidr_block'])
            if '[' in subnet_identifier and 'count.index' in subnet_identifier or 'each.value' in subnet_identifier:
                array = find_between(subnet_identifier, '[', ']').split(',')
                subnet_identifier = connected_label + ' ' + array[i]
            for item in graphdict[connected_item]:
                if item.startswith('aws_nat_gateway') and 'public' not in subnet_identifier:
                    subnet_identifier = subnet_identifier + '(public) '
            with SubnetGroup(subnet_identifier):
                for subnet_item in graphdict[connected_item]:
                    variant = check_variant(subnet_item, tfdata['meta_data'][subnet_item])
                    splitarray = subnet_item.split('.')
                    subnet_service_name = splitarray[0]
                    subnet_label = pretty_name(subnet_item)
                    # Check we recognise this resource type in our drawing library
                    # Ignore LBs as they should only be drawn once as a consolidated node
                    if subnet_item in graphdict.keys() and subnet_service_name in avl_classes and not subnet_service_name.startswith('aws_lb'):
                        node = getattr(sys.modules[__name__], subnet_service_name + variant)(subnet_label + variant, tf_resource_name=subnet_item)
                        tfdata['meta_data'][subnet_item]['node'] = node
                        has_elements = True
                        # Handle Additional connections/nodes needed for special resource types
                        handle_special_resources(tfdata, graphdict, subnet_item)
                if not has_elements:
                    # Include invisible node so that cluster shows up when empty
                    invisible_style = {'style': 'invis', 'height': '0', 'width': '0'}
                    blank_node = getattr(sys.modules[__name__], 'Node')(**invisible_style)
                    
                # tfdata['meta_data'][connected_label + str(i+1)] = {'node': blank_node}
                # tfdata['meta_data'][connected_item] = {'node': blank_node, 'cidr_block': 'Uknown'}
    # Entry point
    variant = ''
    splitarray = resource.split('.')
    resource_service_name = splitarray[0]
    resource_label = splitarray[1]
    if tfdata['meta_data'][resource].get('count'):
        count = int(tfdata['meta_data'][resource]['count'])
    else:
        count = 1

    for i in range(count):
        with VPCgroup(resource_label + ' VPC ' + cleanup(tfdata['meta_data'][resource]['cidr_block'])) as VPC_Group:
            # First draw consolidated nodes that are part of a VPC
            for node in graphdict:
                draw_if_consolidated(node, tfdata, graphdict, VPC_Group, True, True)
            # Now draw all items in VPC connection list
            for connected_item in connections_list:
                splitarray = connected_item.split('.')
                connected_service_name = splitarray[0]
                connected_label = pretty_name(connected_item)
                # Draw all subnets and link nodes under those
                if connected_service_name == 'aws_subnet':
                    autoscaling = False
                    try:
                        # Check if any nodes in connection list are referenced by an autoscaling group
                        scaler_links = next(v for k, v in graphdict.items() if 'aws_appautoscaling_target' in k)
                        for check_service in scaler_links:
                            if check_service in graphdict[connected_item]:
                                autoscaling = True
                    except:
                        autoscaling = False
                    if autoscaling:
                        with GenericAutoScalingGroup() as ASG:
                            draw_subnets()
                    else:
                        draw_subnets()
                elif connected_service_name in avl_classes:
                    # Check for node icon variants
                    variant = check_variant(connected_item, tfdata['meta_data'][connected_item])
                    node = getattr(sys.modules[__name__], connected_service_name + variant)(label=connected_label, tf_resource_name=connected_item)
                    tfdata['meta_data'][connected_item]['node'] = node
    return VPC_Group


def draw_child_nodes(parentnode: Node, connections_list: list, tfdata: dict, graphdict: dict):
    # Loop through each node in the connections list
    for connected_item in connections_list:
        # Over-ride any node names for consolidated services so they are all the same node
        for grouped_node in consolidated_nodes.keys():
            if connected_item.startswith(grouped_node):
                connected_item = consolidated_nodes[grouped_node]['resource_name']
                break
        # Check for variants in icons for certain resource types
        variant = check_variant(connected_item, tfdata['meta_data'][connected_item])
        # Seperate service name and resource name
        connected_service_name = connected_item.split('.')[0]
        connected_label = pretty_name(connected_item)
        if tfdata['meta_data'][connected_item].get('label'):
            connected_label = pretty_name(tfdata['meta_data'][connected_item]['label'])
        # Check if we have a service we can draw
        if connected_service_name in avl_classes:
            if 'node' in tfdata['meta_data'][connected_item]:
                # We have already drawn this resource, so get the node id and link to that
                childnode = tfdata['meta_data'][connected_item]['node']
            else:
                # First time this resource is encountered, so create a new node
                childnode = getattr(sys.modules[__name__], connected_service_name + variant)(label=connected_label,tf_resource_name=connected_item)
                # Check for Lambda@Edge and draw all Lambda nodes connected to Cloudfront in one group
                if connected_service_name == 'aws_cloudfront_distribution' and 'lambda_function_association' in str(tfdata['meta_data'][connected_item]):
                    with GenericGroup('Lambda@Edge'):
                        draw_child_nodes(childnode, graphdict[connected_item], tfdata, graphdict)
                tfdata['meta_data'][connected_item]['node'] = childnode

            # Draw node connections and record entry in connected_nodes list for reference
            if not parentnode._id in connected_nodes.keys():
                nodelist = []
                if isinstance(childnode, set):
                    childnode = list(childnode)[0]
                nodelist.append(childnode._id)
                connected_nodes[parentnode._id] = nodelist
                if childnode != parentnode:
                    connect_up(parentnode,childnode, tfdata['meta_data'])
            else:
                if not childnode._id in connected_nodes[parentnode._id]:
                    if childnode != parentnode:
                        #parentnode >> childnode
                        connect_up(parentnode, childnode, tfdata['meta_data'])
                    connected_nodes[parentnode._id].append(childnode._id)


def draw_parent_children(group: Cluster,  tfdata: dict, graphdict: dict):
    variant = ''
    with group:
        # Loop over every resource in the graphdict structure
        for resource, connections_list in graphdict.items():
            # Over-ride the resource names of any consolidated services so they are all the same node
            for grouped_node in consolidated_nodes.keys():
                if resource.startswith(grouped_node):
                    if '.*' in consolidated_nodes[grouped_node]['resource_name']:
                        for actual_name in graphdict:
                            if grouped_node in actual_name:
                                resource = actual_name
                                break
                    else:
                        resource = consolidated_nodes[grouped_node]['resource_name']
                        break
            # Check for variants in icons for certain resource types
            if not '.*' in resource:
                variant = check_variant(resource, tfdata['meta_data'].get(resource))
            else:
                variant = ''
            splitarray = resource.split('.')
            resource_service_name = splitarray[0]
            resource_label = pretty_name(resource)
            if tfdata['meta_data'][resource].get('label'):
                resource_label = pretty_name(tfdata['meta_data'][resource]['label'])
            if resource_service_name in avl_classes and resource_service_name not in group_nodes:
                # Just draw one node if there are no connections
                if len(connections_list) == 0:
                    if not 'node' in tfdata['meta_data'][resource]:
                        parentnode = getattr(sys.modules[__name__], resource_service_name + variant)(label=resource_label, tf_resource_name=resource)
                        tfdata['meta_data'][resource]['node'] = parentnode
                else:
                    # Draw parent node or use existing one if already drawn
                    if not 'node' in tfdata['meta_data'][resource]:
                        parentnode = getattr(sys.modules[__name__], resource_service_name + variant)(label=resource_label, tf_resource_name=resource)
                        tfdata['meta_data'][resource]['node'] = parentnode
                    else:
                        parentnode = tfdata['meta_data'][resource]['node']
                    # Get first object of parent node which is of type set
                    if isinstance(parentnode, set):
                        parentnode = list(parentnode)[0]
                    # Now draw all the children of this parent node
                    draw_child_nodes(parentnode, connections_list, tfdata, graphdict)


def draw_if_consolidated(nodetype: str, tfdata: dict, graphdict: dict, sub_cluster: Cluster, vpcflag: bool, vpc_exists: bool):
    global aws_group
    for check_consolidate in consolidated_nodes.keys():
        # Check if name starts with a known consolidated node and create a generic node/icon class
        check_resource_name = consolidated_nodes[check_consolidate]['resource_name']
        if '.*' in check_resource_name and check_consolidate in nodetype:
            for actual_name in graphdict:
                if check_consolidate in actual_name:
                    check_resource_name = actual_name
        check_if_resource_exists = tfdata['meta_data'].get(check_resource_name) != None
        already_drawn_node = check_if_resource_exists and tfdata['meta_data'].get(
            check_resource_name).get('node') != None
        undrawn_consolidated_service = nodetype.startswith(check_consolidate) and not already_drawn_node
        # Don't draw if encountered within a VPC as determined by parameter
        ok_to_draw = consolidated_nodes[check_consolidate]['vpc'] == vpcflag
        shared_service = consolidated_nodes[check_consolidate]['vpc'] == False and not consolidated_nodes[check_consolidate].get(
            'edge_service')
        if undrawn_consolidated_service:
            # Check if VPC is missing but the vpcflag is set
            if consolidated_nodes[check_consolidate]['vpc'] == True and not vpc_exists:
                click.echo('WARNING: VPC expected in this architecture but has not been defined in the Terraform source specified')
                ok_to_draw = True
            # Only draw resource if vpcflag is set to specified value
            if ok_to_draw:
                label = pretty_name(check_resource_name, False)
                if nodetype.startswith(check_consolidate):
                    if tfdata['meta_data'][nodetype].get('label'):
                        label = pretty_name(tfdata['meta_data'][nodetype]['label'])
                MyClass = getattr(importlib.import_module(consolidated_nodes[check_consolidate]['import_location']), check_consolidate)
                node_icon = MyClass(label=label, tf_resource_name=check_resource_name)
                # Add nodes to the Cluster Group passed to this function
                if shared_service:
                    sub_cluster.add_node(node_icon._id, label)
                else:
                    aws_group.add_node(node_icon._id, label)
                tfdata['meta_data'].update({check_resource_name: {'node': node_icon}})
        elif nodetype.startswith(check_consolidate):
            # Store the node object reference in meta_data and point it to consolidated_node
            old_node = tfdata['meta_data'][check_resource_name]['node']
            tfdata['meta_data'][nodetype]['node'] = old_node
    aws_group.subgraph(sub_cluster.dot)


#TODO: Integrate this function with user annotations
def auto_annotate(tfdata, graphdict):
    already_drawn = []
    # Automatically inferred annotations
    for node in tfdata['node_list']:
        splitarray = node.split('.')
        resource_service_name = splitarray[0]
        if resource_service_name in avl_classes:
            # Handle grouped nodes
            for check_consolidate in consolidated_nodes.keys():
                if node.startswith(check_consolidate):
                    grouped_name = consolidated_nodes[check_consolidate]['resource_name']
                    if '.*' in grouped_name:
                        for actual_name in graphdict:
                            if check_consolidate in actual_name:
                                grouped_name = actual_name
                                break
                    linkednode = tfdata['meta_data'][grouped_name]['node']
                    if node.startswith('aws_route53') and grouped_name not in already_drawn:
                        users_node = Users('Users')
                        users_node.connect(linkednode,Edge(forward=True))
                        already_drawn.append(grouped_name)
                    if node.startswith('aws_dx_gateway') and grouped_name not in already_drawn:
                        with OnPrem():
                            cgw = VPCCustomerGateway('Customer Gateway')
                            cgw << linkednode
                            cgw >> linkednode
                        already_drawn.append(grouped_name)
            # Handle regular nodes
            if 'node' in tfdata['meta_data'][node]:
                linkednode = tfdata['meta_data'][node]['node']
            if node.startswith('aws_internet'):
                InternetAlt1('Internet').connect(linkednode, Edge(reverse=True))


#TODO: Make this function DRY
def modify_nodes(graphdict: dict, annotate: dict) -> dict:
    click.echo('\nUser Defined Modifications :\n')
    if annotate.get('add'):
        for node in annotate['add']:
            click.echo(f'+ {node}')
            graphdict[node] = []
    if annotate.get('connect'):
        for startnode in annotate['connect']:
            for node in annotate['connect'][startnode]:
                if isinstance(node,dict) :
                    connection = [k for k in node][0]
                else :
                    connection = node
                estring = f'{startnode} --> {connection}'
                click.echo(estring)
                if '*' in startnode:
                    prefix = startnode.split('*')[0]
                    for node in graphdict:
                        if node.startswith(prefix):
                            graphdict[node].append(connection)
                else:
                    graphdict[startnode].append(connection)
    if annotate.get('disconnect'):
        for startnode in annotate['disconnect']:
            for connection in annotate['disconnect'][startnode]:
                estring = f'{startnode} -/-> {connection}'
                click.echo(estring)
                if '*' in startnode:
                    prefix = startnode.split('*')[0]
                    for node in graphdict:
                        if node.startswith(prefix) and connection in graphdict[node]:
                            graphdict[node].remove(connection)
                else:
                    graphdict[startnode].delete(connection)
    if annotate.get('remove'):
        for node in annotate['remove']:
            if node in graphdict or '*' in node:
                click.echo(f'- {node}')
                prefix = node.split('*')[0]
                if '*' in node and node.startswith(prefix):
                    del graphdict[node]
                else:
                    del graphdict[node]
    return graphdict


#TODO: Make this function DRY
def modify_metadata(annotations, graphdict: dict, metadata: dict) -> dict:
    if annotations.get('connect'):
        for node in annotations['connect']:
            if '*' in node:
                found_matching = list_of_dictkeys_containing(metadata, node)
                for key in found_matching:
                    metadata[key]['edge_labels'] = annotations['connect'][node]
            else:
                metadata[node]['edge_labels'] = annotations['connect'][node]
    if annotations.get('add'):
        for node in annotations['add']:
            metadata[node] = {}
            for param in annotations['add'][node]:
                if not metadata[node]:
                    metadata[node] = {}
                metadata[node][param] = annotations['add'][node][param]
    if annotations.get('update'):
        for node in annotations['update']:
            for param in annotations['update'][node]:
                prefix = node.split('*')[0]
                if '*' in node :
                    found_matching = list_of_dictkeys_containing(metadata,prefix)
                    for key in found_matching:
                        metadata[key][param] = annotations['update'][node][param]
                else :
                    metadata[node][param] = annotations['update'][node][param]
    return metadata


def render_diagram(tfdata: dict, graphdict: dict, picshow: bool, detailed: bool, outfile, format, source):
    global aws_group
    # Apply custom user modifiers/annotations
    if tfdata['annotations']:
        graphdict = modify_nodes(graphdict, tfdata['annotations'])
        tfdata['meta_data'] = modify_metadata(tfdata['annotations'], graphdict, tfdata['meta_data'])
    # Hide nodes where count = 0
    for hidden_resource in tfdata['hidden']:
        del graphdict[hidden_resource]
        tfdata['node_list'].remove(hidden_resource)
    for resource in graphdict:
        for hidden_resource in tfdata['hidden']:
            if hidden_resource in graphdict[resource]:
                graphdict[resource].remove(hidden_resource)
    # Dump graphdict
    click.echo(click.style(f'\nFinal Graphviz dictionary:', fg='white', bold=True))
    print(json.dumps(graphdict, indent=4, sort_keys=True))
    click.echo(click.style(f'\nProcessing diagram...', fg='white', bold=True))
    # Setup Canvas
    title = 'Untitled' if not tfdata['annotations'].get('title') else tfdata['annotations']['title']
    myDiagram = Canvas(title, filename=outfile, outformat=format, show=picshow, direction='TB')
    setdiagram(myDiagram)
    # Setup footer
    footer_style = {'_footernode': '1', 'height': '0', 'width': '0','fontsize' : '20',
                    'label': f'Machine generated at {datetime.datetime.now()} using Terravision (https://terra-vision.net)\tSource: {str(source)}'}
    footer_node = getattr(sys.modules[__name__], 'Node')(**footer_style)
    # Setup Outer cloud boundary
    aws_group = AWSgroup()
    setcluster(aws_group)
    vpc_exists = False
    # Initial examination of all resources and their connections
    for resource, connections_list in graphdict.items():
        # Handle nodes within a VPC and Subnet first
        if resource.startswith('aws_vpc.'):
            draw_vpc_subnets(tfdata, graphdict, resource, connections_list)
            vpc_exists = True
    # Create initial consolidated nodes for specific resource types
    SharedServicesCluster = GenericGroup()
    for node in tfdata['node_list']:
        draw_if_consolidated(node, tfdata, graphdict, SharedServicesCluster,  False, vpc_exists)
    # Now draw the rest of the nodes and connect them
    draw_parent_children(aws_group, tfdata, graphdict)
    # Complete the diagram with automatic annotations
    auto_annotate(tfdata, graphdict)
    # Render completed DOT
    path_to_predot = myDiagram.pre_render()
    # Post Processing
    click.echo(click.style(f'\nRendering Architecture Image...', fg='white', bold=True))
    bundle_dir = Path(__file__).parent.parent
    path_to_script = Path.cwd() / bundle_dir / "shiftLabel.gvpr"
    path_to_postdot = Path.cwd() / f'{outfile}.dot'
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        os.system(f'gvpr -c -q -f {path_to_script} {path_to_predot} -o {path_to_postdot}')
    else:
        os.system(f'gvpr -c -q -f {path_to_script} {outfile}.gv.dot -o {outfile}.dot')
    # Generate Final Output file
    click.echo(f'  Output file: {myDiagram.render()}')
    click.echo(f'  Completed!')
    setdiagram(None)
