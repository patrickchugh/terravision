import modules.cloud_config as cloud_config
import click
import modules.helpers as helpers
 
AUTO_ANNOTATIONS = cloud_config.AWS_AUTO_ANNOTATIONS

def handle_annotations(tfdata: dict):
    graphdict = tfdata['graphdict']
    for node in list(graphdict):
        for auto_node in AUTO_ANNOTATIONS:
            node_prefix = str(list(auto_node.keys())[0])
            if node.startswith(node_prefix):
                new_nodes = auto_node[node_prefix]['create']
                for new_node in new_nodes:
                    if auto_node[node_prefix]['link'] == 'forward' :
                       new_connections = list(graphdict[node])
                       new_connections.append(new_node)
                       graphdict[node] = new_connections
                       graphdict[new_node] = dict()
                    else :
                        if graphdict.get(new_node) :
                            new_connections = list(graphdict[new_node])
                            new_connections.append(node)
                            graphdict[new_node] = new_connections
                        else :
                            graphdict[new_node] = [node]
    tfdata['graphdict'] = graphdict
    # Check if user has supplied annotations file
    if tfdata.get('annotations') :
        tfdata['graphdict'] = modify_nodes(tfdata['graphdict'], tfdata['annotations'])
        tfdata['meta_data'] = modify_metadata(tfdata['annotations'], tfdata['graphdict'], tfdata['meta_data']) 
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
                        if node.startswith(prefix):
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
                        if node.startswith(prefix) and connection in graphdict[node]:
                            graphdict[node].remove(connection)
                else:
                    graphdict[startnode].delete(connection)
    if annotate.get("remove"):
        for node in annotate["remove"]:
            if node in graphdict or "*" in node:
                click.echo(f"- {node}")
                prefix = node.split("*")[0]
                if "*" in node and node.startswith(prefix):
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

