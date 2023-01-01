from ast import literal_eval
from contextlib import suppress
import click
import json
from modules.tf_function_handlers import tf_function_handlers
from sys import exit
import modules.helpers as helpers
import modules.annotations as annotations
import modules.cloud_config as cloud_config

REVERSE_ARROW_LIST = cloud_config.AWS_REVERSE_ARROW_LIST
IMPLIED_CONNECTIONS = cloud_config.AWS_IMPLIED_CONNECTIONS


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
    tfdata['graphdict'] = graphdict
     # Handle automatic and user annotations 
    tfdata = annotations.handle_annotations(tfdata)
    # Dump graphdict
    click.echo(click.style(f'\nFinal Graphviz dictionary:', fg='white', bold=True))
    print(json.dumps( tfdata['graphdict'], indent=4, sort_keys=True))
    return tfdata


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
            s for s in IMPLIED_CONNECTIONS.keys() if s in resource_name
        ]
        if found_connection:
            for n in nodes:
                if n.startswith(IMPLIED_CONNECTIONS[found_connection[0]]):
                    matching = [n]
    if (matching):
        reverse = False
        for matched_resource in matching:
            if matched_resource not in hidden and resource_associated_with not in hidden:
                reverse_origin_match = [
                    s for s in REVERSE_ARROW_LIST if s in resource_name
                ]
                if len(reverse_origin_match) > 0:
                    reverse = True
                    reverse_dest_match = [
                        s for s in REVERSE_ARROW_LIST
                        if s in resource_associated_with
                    ]
                    if len(reverse_dest_match) > 0:
                        if REVERSE_ARROW_LIST.index(
                                reverse_dest_match[0]
                        ) < REVERSE_ARROW_LIST.index(reverse_origin_match[0]):
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