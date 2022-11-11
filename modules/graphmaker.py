from ast import literal_eval
from contextlib import suppress
import click
import json
from modules.tf_function_handlers import tf_function_handlers
from sys import exit
import modules.helpers as helpers


reverse_arrow_list = [
    'aws_route53',
    'aws_cloudfront',
    'aws_vpc.',
    'aws_subnet.',
    'aws_iam_role.',
    'aws_lb',
]

implied_connections = {'certificate_arn': 'aws_acm_certificate'}


# Process source files and return dictionaries with relevant data
def make_graph_dict(tfdata: dict):
    # Start with a empty connections list for all nodes/resources we know about
    graphdict = dict.fromkeys( tfdata['node_list'], [])
    num_resources = len( tfdata['node_list'])
    click.echo(
        click.style(
            f"\nComputing Relations between {num_resources - len(tfdata['hidden'])} out of {num_resources} resources...",
            fg="white",
            bold=True,
        )
    )
    # Determine relationship between resources and append to graphdict when found
    for param_list in dict_generator(tfdata['all_resource']):
        for listitem in param_list:
            if isinstance(listitem, str):
                lisitem_tocheck = listitem
                matching_result = check_relationship(lisitem_tocheck, param_list, tfdata['node_list'], tfdata['hidden'])
                if matching_result:
                    for i in range(0, len(matching_result), 2):
                        a_list = list(graphdict[matching_result[i]])
                        if not matching_result[i + 1] in a_list:
                            a_list.append(matching_result[i + 1])
                        graphdict[matching_result[i]] = a_list
            if isinstance(listitem, list):
                for i in listitem:
                    matching_result =    check_relationship(i, param_list, tfdata['node_list'], tfdata['hidden'])
                    if matching_result:
                        a_list = list(graphdict[matching_result[0]])
                        if not matching_result[1] in a_list:
                            a_list.append(matching_result[1])
                        graphdict[matching_result[0]] = a_list
    # Hide nodes where count = 0
    for hidden_resource in tfdata['hidden']:
        del graphdict[hidden_resource]
    for resource in graphdict:
        for hidden_resource in  tfdata['hidden']:
            if hidden_resource in graphdict[resource]:
                graphdict[resource].remove(hidden_resource)
    # Add in node annotations from user
    if tfdata['annotations']:
        click.echo('\n  User Defined Modifications :\n')
        tfdata['graphdict'] = modify_nodes(graphdict, tfdata['annotations'])
        tfdata['meta_data'] = modify_metadata(tfdata['annotations'], graphdict, tfdata['meta_data'])
    # Dump graphdict
    click.echo(click.style(f'\nFinal Graphviz dictionary:', fg='white', bold=True))
    print(json.dumps( tfdata['graphdict'], indent=4, sort_keys=True))
    return tfdata


#TODO: Make this function DRY
def modify_metadata(annotations, graphdict: dict, metadata: dict) -> dict:
    if annotations.get('connect'):
        for node in annotations['connect']:
            if '*' in node:
                found_matching = helpers.list_of_dictkeys_containing(metadata, node)
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
                    found_matching = helpers.list_of_dictkeys_containing(metadata,prefix)
                    for key in found_matching:
                        metadata[key][param] = annotations['update'][node][param]
                else :
                    metadata[node][param] = annotations['update'][node][param]
    return metadata


# Generator function to crawl entire dict and load all dict and list values
def dict_generator(indict, pre=None):
    pre = pre[:] if pre else []
    if isinstance(indict, dict):
        for key, value in indict.items():
            if isinstance(value, dict):
                for d in dict_generator(value, pre + [key]):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in dict_generator(v, pre + [key]):
                        yield d
            else:
                yield pre + [key, value]
    else:
        yield pre + [indict]


#TODO: Make this function DRY
def modify_nodes(graphdict: dict, annotate: dict) -> dict:
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


# Function to check whether a particular resource mentions another known resource (relationship)
def check_relationship(listitem: str, plist: list, nodes: list, hidden: dict): # -> list
    connection_list = []
    resource_name = listitem.strip('${}')
    resource_associated_with = plist[1] + '.' + plist[2]
    # Check if an existing node name appears in parameters of current resource being checked
    matching = [s for s in nodes if s in resource_name]
    # Check if there are any implied connections based on keywords in the param list
    if not matching:
        found_connection = [
            s for s in implied_connections.keys() if s in resource_name
        ]
        if found_connection:
            for n in nodes:
                if n.startswith(implied_connections[found_connection[0]]):
                    matching = [n]
    if (matching):
        reverse = False
        for matched_resource in matching:
            if matched_resource not in hidden and resource_associated_with not in hidden:
                reverse_origin_match = [
                    s for s in reverse_arrow_list if s in resource_name
                ]
                if len(reverse_origin_match) > 0:
                    reverse = True
                    reverse_dest_match = [
                        s for s in reverse_arrow_list
                        if s in resource_associated_with
                    ]
                    if len(reverse_dest_match) > 0:
                        if reverse_arrow_list.index(
                                reverse_dest_match[0]
                        ) < reverse_arrow_list.index(reverse_origin_match[0]):
                            reverse = False
                if reverse:
                    connection_list.append(matched_resource)
                    connection_list.append(resource_associated_with)
                    # Output relationship to console log in reverse order for VPC related nodes
                    click.echo(
                        f'   {matched_resource} --> {resource_associated_with}'
                    )
                else :  # Exception Ignore outgoing connections from ACM certificates and resources mentioned in depends on
                    if listitem in plist:
                        i = plist.index(listitem)
                        if plist[3] == 'depends_on':
                            continue
                    connection_list.append(resource_associated_with)
                    connection_list.append(matched_resource)
                    click.echo(
                        f'   {resource_associated_with} --> {matched_resource}'
                    )
    return connection_list