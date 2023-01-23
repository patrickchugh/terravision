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
GROUP_NODES = cloud_config.AWS_GROUP_NODES
CONSOLIDATED_NODES = cloud_config.AWS_CONSOLIDATED_NODES
NODE_VARIANTS = cloud_config.AWS_NODE_VARIANTS

# Make final graph structure to be used for drawing
def make_graph_dict(tfdata: dict):
    # Start with an empty connections list for all nodes/resources we know about
    graphdict = dict.fromkeys( tfdata['node_list'], [])
    num_resources = len( tfdata['node_list'])
    click.echo(
        click.style(
            f"\nComputing Relations between {num_resources - len(tfdata['hidden'])} out of {num_resources} resources...",
            fg="white",
            bold=True,
        )
    )
    # Handle special relationships that require deduction to link up
    tfdata = handle_special_resources(tfdata)
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
                    matching_result = check_relationship(i, param_list, tfdata['node_list'], tfdata['hidden'])
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
    # Handle multiple resources created by count attribute
    tfdata = handle_multiple_resources(tfdata)
    # # Handle special node variants 
    #tfdata = handle_variants(tfdata)
    # Dump graphdict
    click.echo(click.style(f'\nFinal Graphviz dictionary:', fg='white', bold=True))
    print(json.dumps( tfdata['graphdict'], indent=4, sort_keys=True))
    return tfdata


def handle_variants(tfdata: dict) :
    for node, connections in tfdata['graphdict'].items() :
        for resource in connections :
            variant_suffix = check_variant(resource, tfdata['meta_data']) 
            if variant_suffix :
                if variant_suffix not in resource :
                    tfdata['graphdict'][node].remove(resource)
                    tfdata['graphdict'][node].append(resource.replace(f'{resource.split(".")[0]}.', f'{variant_suffix}.'))
                    parents_list = helpers.list_of_parents(tfdata['graphdict'], resource)
                    for parent in parents_list:
                        tfdata['graphdict'][parent].append(resource.replace(f'{resource.split(".")[0]}.', f'{variant_suffix}.'))
                        tfdata['graphdict'][parent].remove(resource)
    return tfdata

def check_variant(resource: str, metadata: dict) -> str:
    for variant_service in NODE_VARIANTS:
        if resource.startswith(variant_service):
            for keyword in NODE_VARIANTS[variant_service]:
                if keyword in str(metadata):
                    return NODE_VARIANTS[variant_service][keyword]
    return ""


# Loop through every connected node that has a count >0 and add suffix -i where i is the source node prefix
def add_number_suffix(i: int, target_resource:str, tfdata: dict) :
    new_list = list()
    for resource in tfdata['graphdict'][target_resource]:
        if tfdata['meta_data'].get(resource) :
            parents_list = helpers.list_of_parents(tfdata['graphdict'], target_resource)
            parent_has_count = False
            for parent in parents_list:
                if tfdata['meta_data'][parent].get('count') :
                    parent_has_count = True
            if (tfdata['meta_data'][resource].get('count') or parent_has_count) :
                if '-' not in resource :
                    new_name = resource + '-' + str(i)
                if new_name not in new_list:
                    new_list.append(new_name)
            else:
                new_list.append(resource)
        else :
            new_list.append(resource)
    return new_list


def handle_multiple_resources(tfdata) :
    # Get a list of all potential resources with a positive count attribute
    multi_resources = [k for k,v in tfdata['meta_data'].items() if "count" in v and isinstance(tfdata['meta_data'][k]['count'],int) and tfdata['meta_data'][k]['count'] >1]
    # Loop and for each one, create multiple nodes for the resource and any connections
    for resource in multi_resources:        
        for i in range(tfdata['meta_data'][resource]['count'] ) :
            resource_i = add_number_suffix(i+1, resource, tfdata)
            if resource_i :
                tfdata['graphdict'][resource+'-' + str(i+1)] = resource_i
                tfdata['meta_data'][resource+'-' + str(i+1)] = tfdata['meta_data'][resource]
                parents_list = helpers.list_of_parents(tfdata['graphdict'], resource)
                for parent in parents_list:
                    tfdata['graphdict'][parent].append(resource+'-' + str(i+1)) 
        del tfdata['graphdict'][resource]
    for resource in multi_resources:
        parents_list = helpers.list_of_parents(tfdata['graphdict'], resource)
        for parent in parents_list:
            tfdata['graphdict'][parent].remove(resource)
    return tfdata


def handle_special_resources(tfdata:dict) :
    cf_data = [s for s in tfdata['meta_data'].keys() if "aws_cloudfront" in s]
    if cf_data:
        for cf_resource in cf_data:
            if "origin" in tfdata['meta_data'][cf_resource]:
                origin_source = tfdata['meta_data'][cf_resource]["origin"]
                if isinstance(origin_source, str) and origin_source.startswith("{"):
                    origin_source = helpers.literal_eval(origin_source)
                origin_domain = helpers.cleanup(origin_source.get("domain_name")).strip()
                if origin_domain:
                    tfdata['meta_data'][cf_resource]["origin"] = handle_cloudfront_domains(
                        str(origin_source), origin_domain, tfdata['meta_data']
                    )
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


def handle_cloudfront_domains(origin_string: str, domain: str, mdata: dict) -> str:
    for key, value in mdata.items():
        for k, v in value.items():
            if domain in str(v) and not domain.startswith("aws_"):
                o = origin_string.replace(domain, key)
                return origin_string.replace(domain, key)
    return origin_string


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