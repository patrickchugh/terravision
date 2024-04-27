import sys

import click

import modules.cloud_config as cloud_config
import modules.helpers as helpers

AUTO_ANNOTATIONS = cloud_config.AWS_AUTO_ANNOTATIONS


def add_annotations(tfdata: dict):
    graphdict = tfdata["graphdict"]
    for node in list(graphdict):
        # node = helpers.get_no_module_name(n)
        for auto_node in AUTO_ANNOTATIONS:
            node_prefix = str(list(auto_node.keys())[0])
            if helpers.get_no_module_name(node).startswith(node_prefix):
                new_nodes = auto_node[node_prefix]["link"]
                delete_nodes = auto_node[node_prefix].get("delete")
                for new_node in new_nodes:
                    if new_node.endswith(".*"):
                        annotation_node = helpers.find_resource_containing(
                            tfdata["graphdict"].keys(), new_node.split(".")[0]
                        )

                        if not annotation_node:
                            annotation_node = new_node.split(".")[0] + ".this"
                    else:
                        tfdata["graphdict"][new_node] = list()
                        annotation_node = new_node
                    if auto_node[node_prefix]["arrow"] == "forward":
                        graphdict[node] = helpers.append_dictlist(
                            graphdict[node], annotation_node
                        )
                        if delete_nodes:
                            for delnode in delete_nodes:
                                for conn in graphdict[node]:
                                    if helpers.get_no_module_name(conn).startswith(
                                        delnode
                                    ):
                                        graphdict[node].remove(conn)
                        if not graphdict.get(annotation_node):
                            graphdict[annotation_node] = list()
                    else:
                        if graphdict.get(annotation_node):
                            new_connections = list(graphdict[annotation_node])
                            new_connections.append(annotation_node)
                            graphdict[annotation_node] = list(new_connections)
                        else:
                            graphdict[annotation_node] = [node]
                    tfdata["meta_data"][annotation_node] = dict()
    tfdata["graphdict"] = graphdict
    # Check if user has supplied annotations file
    if tfdata.get("annotations"):
        tfdata["graphdict"] = modify_nodes(tfdata["graphdict"], tfdata["annotations"])
        tfdata["meta_data"] = modify_metadata(
            tfdata["annotations"], tfdata["graphdict"], tfdata["meta_data"]
        )
    return tfdata


# TODO: Make this function DRY
def modify_nodes(graphdict: dict, annotate: dict) -> dict:
    click.echo("\nUser Defined Modifications :\n")
    if annotate.get("add"):
        for node in annotate["add"]:
            click.echo(f"+ {node}")
            graphdict[node] = []
    if annotate.get("connect"):
        for startnode in annotate["connect"]:
            for node in annotate["connect"][startnode]:
                if isinstance(node, dict):
                    connection = [k for k in node][0]
                else:
                    connection = node
                estring = f"{startnode} --> {connection}"
                click.echo(estring)
                if "*" in startnode:
                    prefix = startnode.split("*")[0]
                    for node in graphdict:
                        if helpers.get_no_module_name(node).startswith(prefix):
                            graphdict[node].append(connection)
                else:
                    graphdict[startnode].append(connection)
    if annotate.get("disconnect"):
        for startnode in annotate["disconnect"]:
            for connection in annotate["disconnect"][startnode]:
                estring = f"{startnode} -/-> {connection}"
                click.echo(estring)
                if "*" in startnode:
                    prefix = startnode.split("*")[0]
                    for node in graphdict:
                        if (
                            helpers.get_no_module_name(node).startswith(prefix)
                            and connection in graphdict[node]
                        ):
                            graphdict[node].remove(connection)
                else:
                    graphdict[startnode].delete(connection)
    if annotate.get("remove"):
        for node in annotate["remove"]:
            if node in graphdict or "*" in node:
                click.echo(f"~ {node}")
                prefix = node.split("*")[0]
                if "*" in node and helpers.get_no_module_name(node).startswith(prefix):
                    del graphdict[node]
                else:
                    del graphdict[node]
    return graphdict


# TODO: Make this function DRY
def modify_metadata(annotations, graphdict: dict, metadata: dict) -> dict:
    if annotations.get("connect"):
        for node in annotations["connect"]:
            if "*" in node:
                found_matching = helpers.list_of_dictkeys_containing(metadata, node)
                for key in found_matching:
                    metadata[key]["edge_labels"] = annotations["connect"][node]
            else:
                metadata[node]["edge_labels"] = annotations["connect"][node]
    if annotations.get("add"):
        for node in annotations["add"]:
            metadata[node] = {}
            for param in annotations["add"][node]:
                if not metadata[node]:
                    metadata[node] = {}
                metadata[node][param] = annotations["add"][node][param]
    if annotations.get("update"):
        for node in annotations["update"]:
            for param in annotations["update"][node]:
                prefix = node.split("*")[0]
                if "*" in node:
                    found_matching = helpers.list_of_dictkeys_containing(
                        metadata, prefix
                    )
                    for key in found_matching:
                        metadata[key][param] = annotations["update"][node][param]
                else:
                    metadata[node][param] = annotations["update"][node][param]
    return metadata
