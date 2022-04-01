#!/usr/bin/env python
import click
import sys
import json
import shutil
import os
import modules.fileparser as fileparser
import modules.helpers as helpers
import modules.drawing as drawing
from pprint import pprint
from pathlib import Path

# Process source files and return dictionaries with relevant data


def make_graph(source: list, varfile: list, annotate='') -> dict:
    # Read relevant data from Terraforms
    tfdata = fileparser.parse_tf_files(source, varfile, annotate)

    # Create Graph Data Structure in the format {node: [connected_node1,connected_node2]}
    relationship_dict = helpers.make_graph_dict(
        tfdata['node_list'],
        tfdata['all_resource'],
        tfdata.get('all_locals'),
        tfdata.get('all_output'),
        tfdata['hidden'],
    )
    return {'graphdict': relationship_dict, 'tfdata': tfdata}


def preflight_check():
    click.echo(click.style('\nPreflight check..', fg='white', bold=True))
    dependencies = ['dot', 'gvpr', 'git']
    bundle_dir = Path(__file__).parent
    sys.path.append(bundle_dir)
    for exe in dependencies:
        binary = Path.cwd() / bundle_dir / exe
        location = shutil.which(exe) or os.path.isfile(exe)
        if location:
            click.echo(f'  {exe} command detected: {location}')
        else:
            click.echo(
                click.style(
                    f'\n  ERROR: {exe} command executable not detected in path. Please ensure you have installed all required dependencies first',
                    fg='red',
                    bold=True))
            sys.exit()


def unique_services(nodelist: list) -> list:
    service_list = []
    for item in nodelist:
        service = str(item.split('.')[0]).strip()
        service_list.append(service)
    return sorted(set(service_list))

# Default help banner


@click.version_option(version=0.2, prog_name='terravision')
@click.group()
def cli():
    '''
    Terravision 0.2 Alpha

    Copyright 2022 Patrick Chugh. All rights reserved.

    Terravision generates professional cloud architecture diagrams from Terraform scripts

    For help with a specific command type:

    terravision [COMMAND] --help

    '''
    pass


# Draw Diagram Command
@cli.command()
@click.option('--source', multiple=True, default=["."], help='Source files location (Git URL or folder)')
@click.option('--varfile', multiple=True, default=[], help='Path to .tfvars variables file')
@click.option('--outfile', default='architecture', help='Filename for output diagram (default architecture.dot.png)')
@click.option('--format', default='png', help='File format (png/pdf/svg/json/bmp)')
@click.option('--show', is_flag=True, default=False, help='Show diagram after generation')
@click.option('--simplified', is_flag=True, default=False, help='Simplified high level services shown only')
@click.option('--annotate', default='', help='Path to custom annotations file (YAML)')
@click.option('--avl_classes', hidden=True)
def draw(source, varfile, outfile, format, show, simplified, annotate, avl_classes):
    '''Draws Architecture Diagram'''
    preflight_check()
    parsed_data = make_graph(source, varfile, annotate)
    drawing.render_diagram(parsed_data['tfdata'], parsed_data['graphdict'], show, simplified, outfile, format, source)


# List Resources Command
@cli.command()
@click.option('--source', multiple=True, default=["."], help='Source files location (Git URL or folder)')
@click.option('--varfile', multiple=True, default=[], help='Path to .tfvars variables file')
@click.option('--show_services', is_flag=True, default=False, help='Only show unique list of cloud services actually used')
@click.option('--outfile', default='architecture', help='Filename for output list (default architecture.json)')
@click.option('--avl_classes', hidden=True)
def list(source, varfile, show_services, outfile, avl_classes):
    '''List Cloud Resources and Relations'''
    preflight_check()
    parsed_data = make_graph(source, varfile)
    click.echo(click.style('\nJSON Dictionary :', fg='white', bold=True))
    unique = unique_services(parsed_data['tfdata']['node_list'])
    click.echo(json.dumps(parsed_data['graphdict'] if not show_services else unique, indent=4, sort_keys=True))


if __name__ == '__main__':
    cli(default_map={
        'draw': {
            'avl_classes': dir()
        },
        'list': {
            'avl_classes': dir()
        }
    })
