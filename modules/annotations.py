"""Annotations module for TerraVision.

This module handles automatic and user-defined annotations for Terraform architecture diagrams.
It processes annotation rules to add, remove, connect, and modify nodes in the graph.
"""

import sys
from typing import Dict, List, Any
import click
import modules.config_loader as config_loader
import modules.helpers as helpers


def _get_provider_auto_annotations(tfdata: Dict[str, Any]) -> List[Dict]:
    """
    Get provider-specific AUTO_ANNOTATIONS from the appropriate cloud config.

    Extracts provider from tfdata, loads the correct config, and returns
    the provider-specific AUTO_ANNOTATIONS constant.

    Args:
        tfdata: Dictionary containing provider_detection with primary_provider

    Returns:
        List of auto-annotation rules for the detected provider

    Raises:
        ValueError: If provider detection not found in tfdata
        config_loader.ConfigurationError: If provider config cannot be loaded

    Note:
        This function NO LONGER falls back to AWS. Provider detection must
        be run before calling this function.
    """
    # Extract provider from tfdata (set by provider_detector)
    if not tfdata.get("provider_detection"):
        raise ValueError(
            "provider_detection not found in tfdata. "
            "Ensure detect_providers(tfdata) is called before add_annotations()."
        )

    provider = tfdata["provider_detection"]["primary_provider"]

    # Load provider-specific config
    config = config_loader.load_config(provider)

    # Get the provider-specific AUTO_ANNOTATIONS constant
    # Convention: {PROVIDER}_AUTO_ANNOTATIONS (e.g., AWS_AUTO_ANNOTATIONS)
    provider_upper = provider.upper()
    annotations_attr = f"{provider_upper}_AUTO_ANNOTATIONS"

    if hasattr(config, annotations_attr):
        return getattr(config, annotations_attr)
    else:
        raise config_loader.ConfigurationError(
            f"Provider config for '{provider}' does not define {annotations_attr}. "
            f"Please add {annotations_attr} to cloud_config_{provider}.py"
        )


def add_annotations(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Apply automatic and user-defined annotations to the Terraform graph.

    Processes both automatic cloud provider annotations and custom user annotations
    to modify the graph structure, add connections, and update metadata.

    This function is provider-aware and will use the correct AUTO_ANNOTATIONS
    based on the cloud provider detected in tfdata["provider_detection"].

    Args:
        tfdata: Dictionary containing graph data with keys:
            - graphdict: Node connections dictionary
            - meta_data: Resource metadata dictionary
            - annotations: Optional user-defined annotations
            - provider_detection: Provider detection result (optional)

    Returns:
        Modified tfdata dictionary with updated graphdict and meta_data
    """
    graphdict = tfdata["graphdict"]

    # Get provider-specific auto annotations
    auto_annotations = _get_provider_auto_annotations(tfdata)

    # Apply automatic cloud provider annotations
    for node in list(graphdict):
        for auto_node in auto_annotations:
            node_prefix = str(list(auto_node.keys())[0])
            # Check if current node matches annotation pattern
            if helpers.get_no_module_name(node).startswith(node_prefix):
                new_nodes = auto_node[node_prefix]["link"]
                delete_nodes = auto_node[node_prefix].get("delete")

                # Process each new node to be linked
                for new_node in new_nodes:
                    # Handle wildcard nodes (e.g., "aws_service.*")
                    if new_node.endswith(".*"):
                        annotation_node = helpers.find_resource_containing(
                            tfdata["graphdict"].keys(), new_node.split(".")[0]
                        )
                        # Default to ".this" suffix if no matching resource found
                        if not annotation_node:
                            annotation_node = new_node.split(".")[0] + ".this"
                    else:
                        # Use literal node name, don't overwrite if exists
                        annotation_node = new_node
                        # Only create node if it doesn't exist
                        if annotation_node not in tfdata["graphdict"]:
                            tfdata["graphdict"][annotation_node] = list()

                    # Determine connection direction
                    if auto_node[node_prefix]["arrow"] == "forward":
                        # Forward arrow: current node -> annotation node
                        graphdict[node] = helpers.append_dictlist(
                            graphdict[node], annotation_node
                        )
                        # Remove specified connections if delete_nodes defined
                        if delete_nodes:
                            for delnode in delete_nodes:
                                for conn in graphdict[node]:
                                    if helpers.get_no_module_name(conn).startswith(
                                        delnode
                                    ):
                                        graphdict[node].remove(conn)
                        # Ensure annotation node exists in graph
                        if not graphdict.get(annotation_node):
                            graphdict[annotation_node] = list()
                    else:
                        # Reverse arrow: annotation node -> current node
                        if graphdict.get(annotation_node):
                            new_connections = list(graphdict[annotation_node])
                            new_connections.append(annotation_node)
                            graphdict[annotation_node] = list(new_connections)
                        else:
                            graphdict[annotation_node] = [node]

                    # Initialize metadata for annotation node only if it doesn't exist
                    if annotation_node not in tfdata["meta_data"]:
                        tfdata["meta_data"][annotation_node] = dict()

    tfdata["graphdict"] = graphdict

    # Apply user-defined annotations from YAML file if provided
    if tfdata.get("annotations"):
        tfdata["graphdict"] = modify_nodes(tfdata["graphdict"], tfdata["annotations"])
        tfdata["meta_data"] = modify_metadata(
            tfdata["annotations"], tfdata["graphdict"], tfdata["meta_data"]
        )

    return tfdata


# TODO: Make this function DRY
def modify_nodes(
    graphdict: Dict[str, List[str]], annotate: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Modify graph nodes based on user-defined annotations.

    Processes user annotations to add nodes, create connections, remove connections,
    and delete nodes from the graph. Supports wildcard patterns for bulk operations.

    Args:
        graphdict: Dictionary mapping node names to lists of connected nodes
        annotate: User annotation dictionary with optional keys:
            - add: Nodes to add
            - connect: Connections to create
            - disconnect: Connections to remove
            - remove: Nodes to delete

    Returns:
        Modified graphdict with user annotations applied
    """
    click.echo("\nUser Defined Modifications :\n")

    if annotate.get("title"):
        click.echo(f"Title: {annotate['title']}\n")

    # Add new nodes to the graph
    if annotate.get("add"):
        for node in annotate["add"]:
            click.echo(f"+ {node}")
            graphdict[node] = []

    # Create new connections between nodes
    if annotate.get("connect"):
        for startnode in annotate["connect"]:
            for node in annotate["connect"][startnode]:
                # Extract connection name (handle dict format for labeled edges)
                if isinstance(node, dict):
                    connection = [k for k in node][0]
                else:
                    connection = node

                estring = f"{startnode} --> {connection}"
                click.echo(estring)

                # Handle wildcard patterns (e.g., "aws_lambda*")
                if "*" in startnode:
                    prefix = startnode.split("*")[0]
                    for node in graphdict:
                        if helpers.get_no_module_name(node).startswith(prefix):
                            if connection not in graphdict[node]:
                                graphdict[node].append(connection)
                else:
                    if connection not in graphdict[startnode]:
                        graphdict[startnode].append(connection)

    # Remove existing connections between nodes
    if annotate.get("disconnect"):
        for startnode in annotate["disconnect"]:
            for connection in annotate["disconnect"][startnode]:
                estring = f"{startnode} -/-> {connection}"
                click.echo(estring)

                # Handle wildcard patterns for disconnection
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

    # Delete nodes from the graph
    if annotate.get("remove"):
        for node in annotate["remove"]:
            if node in graphdict or "*" in node:
                click.echo(f"~ {node}")
                prefix = node.split("*")[0]
                # Handle wildcard deletion
                if "*" in node and helpers.get_no_module_name(node).startswith(prefix):
                    del graphdict[node]
                else:
                    del graphdict[node]

    return graphdict


# TODO: Make this function DRY
def modify_metadata(
    annotations: Dict[str, Any],
    graphdict: Dict[str, List[str]],
    metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Modify resource metadata based on user-defined annotations.

    Updates metadata for nodes including edge labels, custom attributes, and
    resource properties. Supports wildcard patterns for bulk updates.

    Args:
        annotations: User annotation dictionary with optional keys:
            - connect: Edge labels for connections
            - add: New nodes with attributes
            - update: Attribute updates for existing nodes
        graphdict: Dictionary mapping node names to connected nodes
        metadata: Dictionary mapping node names to their metadata attributes

    Returns:
        Modified metadata dictionary with user annotations applied
    """
    # Add edge labels from connect annotations
    if annotations.get("connect"):
        for node in annotations["connect"]:
            # Handle wildcard patterns for edge labels
            if "*" in node:
                found_matching = helpers.list_of_dictkeys_containing(metadata, node)
                for key in found_matching:
                    metadata[key]["edge_labels"] = annotations["connect"][node]
            else:
                metadata[node]["edge_labels"] = annotations["connect"][node]

    # Add metadata for newly added nodes
    if annotations.get("add"):
        for node in annotations["add"]:
            metadata[node] = {}
            # Copy all attributes from annotation to metadata
            for param in annotations["add"][node]:
                if not metadata[node]:
                    metadata[node] = {}
                metadata[node][param] = annotations["add"][node][param]

    # Update metadata for existing nodes
    if annotations.get("update"):
        for node in annotations["update"]:
            for param in annotations["update"][node]:
                prefix = node.split("*")[0]
                # Handle wildcard patterns for bulk updates
                if "*" in node:
                    found_matching = helpers.list_of_dictkeys_containing(
                        metadata, prefix
                    )
                    for key in found_matching:
                        metadata[key][param] = annotations["update"][node][param]
                else:
                    metadata[node][param] = annotations["update"][node][param]

    return metadata
