from ast import literal_eval
from contextlib import suppress
import click
import re
import os
from modules.tf_function_handlers import tf_function_handlers
from sys import exit

reverse_arrow_list = [
    'aws_route53',
    'aws_cloudfront',
    'aws_vpc.',
    'aws_subnet.',
    'aws_iam_role.',
    'aws_lb',
]

implied_connections = {'certificate_arn': 'aws_acm_certificate'}

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
def check_relationship(listitem: str, plist: list, nodes: list,
                       replacements: list, hidden: list) -> list:
    connection_list = []
    resource_name = listitem.strip('${}')
    if resource_name in replacements.keys():
        resource_associated_with = replacements[resource_name]
        resource_name = plist[1] + '.' + plist[2]
    else:
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
                elif not 'aws_acm' in resource_associated_with:  # Exception Ignore outgoing connections from ACM certificates and resources mentioned in depends on
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