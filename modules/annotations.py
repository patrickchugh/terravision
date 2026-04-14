"""Annotations module for TerraVision.

This module handles automatic and user-defined annotations for Terraform architecture diagrams.
It processes annotation rules to add, remove, connect, and modify nodes in the graph.
"""

import sys
from typing import Dict, List, Any, Optional
import click
import modules.config_loader as config_loader
import modules.helpers as helpers

# Annotation schema versions accepted by the merger.
# 0.1 is the legacy single-file format. 0.2 adds the `flows` section
# and the two-file (terravision.yml + terravision.ai.yml) model.
SUPPORTED_ANNOTATION_FORMATS = {"0.1", "0.2"}


def _validate_format(annotations: Optional[Dict[str, Any]], source_label: str) -> None:
    """Reject annotation files declaring an unsupported `format` value.

    Files without a `format` field are accepted (legacy 0.1 behaviour).
    """
    if not annotations:
        return
    fmt = annotations.get("format")
    if fmt is None:
        return
    if str(fmt) not in SUPPORTED_ANNOTATION_FORMATS:
        click.echo(
            click.style(
                f"  WARNING: {source_label} declares unsupported format "
                f"'{fmt}'. Accepted: {sorted(SUPPORTED_ANNOTATION_FORMATS)}. "
                f"Annotations from this file will be ignored.",
                fg="yellow",
            )
        )


def merge_annotations(
    ai_annotations: Optional[Dict[str, Any]] = None,
    user_annotations: Optional[Dict[str, Any]] = None,
    cli_annotations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge AI / user / CLI annotation sources into a single dict.

    Precedence (lowest to highest): AI file -> user file -> --annotate
    CLI file. Later sources override earlier ones, with these rules:

      * ``title``: scalar; highest-precedence source wins.
      * ``add``: dict keyed by node name; per-attribute later wins.
        List-of-strings shape is also tolerated.
      * ``connect``: dict by source node; target lists are unioned;
        when the same source+target appears in two files, the higher
        precedence label wins (a bare-string entry in a higher source
        does NOT erase a label set by a lower source — user labels
        never disappear silently).
      * ``disconnect`` / ``remove``: list union. The renderer applies
        these AFTER add/connect, so a removal always beats an addition
        for the same node.
      * ``update``: dict by resource; per-attribute later wins.
      * ``flows``: dict by flow name. If both files define a flow with
        the same name, the higher-precedence flow REPLACES the entire
        lower-precedence flow — there is no per-step merging because
        that would be too confusing to debug.

    The AI file is never trusted to overwrite a user-authored value:
    any conflict resolves to the user (or CLI) value. The merged dict
    has the same shape as a single annotation file and can be passed
    straight to ``add_annotations()`` / ``modify_nodes()`` /
    ``modify_metadata()``.

    Args:
        ai_annotations: Parsed terravision.ai.yml content (lowest precedence).
        user_annotations: Parsed terravision.yml content.
        cli_annotations: Parsed --annotate file content (highest precedence).

    Returns:
        Merged annotation dict. Empty dict when all sources are None/empty.
    """
    _validate_format(ai_annotations, "terravision.ai.yml")
    _validate_format(user_annotations, "terravision.yml")
    _validate_format(cli_annotations, "--annotate file")

    sources: List[Dict[str, Any]] = [
        s for s in (ai_annotations, user_annotations, cli_annotations) if s
    ]
    if not sources:
        return {}

    merged: Dict[str, Any] = {}

    # `format`: highest precedence wins (informational only).
    for src in sources:
        if src.get("format") is not None:
            merged["format"] = src["format"]

    # `title`: scalar, highest precedence wins.
    for src in sources:
        if src.get("title"):
            merged["title"] = src["title"]

    # `add`: dict keyed by node name. Per-attribute, later sources win.
    # Tolerates the list-of-strings shape documented in data-model.md.
    add_merged: Dict[str, Dict[str, Any]] = {}
    for src in sources:
        src_add = src.get("add")
        if not src_add:
            continue
        if isinstance(src_add, list):
            for node in src_add:
                if isinstance(node, str):
                    add_merged.setdefault(node, {})
        elif isinstance(src_add, dict):
            for node, attrs in src_add.items():
                add_merged.setdefault(node, {})
                if isinstance(attrs, dict):
                    add_merged[node].update(attrs)
    if add_merged:
        merged["add"] = add_merged

    # `connect`: dict by source node, list of targets. Targets may be bare
    # strings or {target: label} dicts. Same target from a higher-precedence
    # source replaces the lower-precedence entry (so user labels win).
    connect_merged: Dict[str, List[Any]] = {}
    for src in sources:
        for source_node, targets in (src.get("connect") or {}).items():
            existing = connect_merged.setdefault(source_node, [])
            for target in targets or []:
                if isinstance(target, dict):
                    target_name = next(iter(target))
                    target_label = target[target_name]
                else:
                    target_name = target
                    target_label = None

                existing_idx = None
                for i, entry in enumerate(existing):
                    if isinstance(entry, dict):
                        if next(iter(entry)) == target_name:
                            existing_idx = i
                            break
                    elif entry == target_name:
                        existing_idx = i
                        break

                if existing_idx is None:
                    existing.append(
                        {target_name: target_label}
                        if target_label is not None
                        else target_name
                    )
                else:
                    if target_label is not None:
                        existing[existing_idx] = {target_name: target_label}
                    # If higher source has bare string and lower had a label,
                    # the lower-source label is preserved (user labels never
                    # disappear silently).
    if connect_merged:
        merged["connect"] = connect_merged

    # `disconnect`: dict by source node, list union. Applied after connect
    # at render time so disconnect always wins.
    disconnect_merged: Dict[str, List[str]] = {}
    for src in sources:
        for source_node, targets in (src.get("disconnect") or {}).items():
            existing = disconnect_merged.setdefault(source_node, [])
            for target in targets or []:
                if target not in existing:
                    existing.append(target)
    if disconnect_merged:
        merged["disconnect"] = disconnect_merged

    # `remove`: list union. Applied after add at render time so remove
    # always beats add.
    remove_merged: List[str] = []
    for src in sources:
        for node in src.get("remove") or []:
            if node not in remove_merged:
                remove_merged.append(node)
    if remove_merged:
        merged["remove"] = remove_merged

    # `update`: dict by resource, per-attribute later wins.
    update_merged: Dict[str, Dict[str, Any]] = {}
    for src in sources:
        for node, attrs in (src.get("update") or {}).items():
            update_merged.setdefault(node, {})
            if isinstance(attrs, dict):
                update_merged[node].update(attrs)
    if update_merged:
        merged["update"] = update_merged

    # `flows`: dict by flow name. Higher precedence flow REPLACES the
    # lower-precedence flow with the same name (no per-step merging).
    flows_merged: Dict[str, Any] = {}
    for src in sources:
        for flow_name, flow_def in (src.get("flows") or {}).items():
            flows_merged[flow_name] = flow_def
    if flows_merged:
        merged["flows"] = flows_merged

    # `generated_by` is informational metadata that lives only in the AI
    # file. We surface it on the merged dict for downstream logging but
    # add_annotations() must NOT apply it to the graph.
    if ai_annotations and ai_annotations.get("generated_by"):
        merged["generated_by"] = ai_annotations["generated_by"]

    return merged


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
                                conns_to_remove = [
                                    conn
                                    for conn in graphdict.get(node, [])
                                    if helpers.get_no_module_name(conn).startswith(
                                        delnode
                                    )
                                ]
                                for conn in conns_to_remove:
                                    graphdict[node].remove(conn)
                        # Ensure annotation node exists in graph
                        if not graphdict.get(annotation_node):
                            graphdict[annotation_node] = list()
                    else:
                        # Reverse arrow: annotation node -> current node
                        if graphdict.get(annotation_node):
                            new_connections = list(graphdict[annotation_node])
                            new_connections.append(node)
                            graphdict[annotation_node] = list(new_connections)
                        else:
                            graphdict[annotation_node] = [node]

                    # Initialize metadata for annotation node only if it doesn't exist
                    if annotation_node not in tfdata["meta_data"]:
                        tfdata["meta_data"][annotation_node] = dict()

    tfdata["graphdict"] = graphdict

    # Apply user-defined annotations from terravision.yml if present.
    # AI-generated annotations are handled SEPARATELY by
    # apply_ai_annotations() in a later pipeline step — the AI must
    # see the fully enriched graphdict (after handle_special_resources,
    # create_multiple_resources, match_resources, etc.) to label
    # nodes by their final renderer-visible names.
    if tfdata.get("annotations"):
        tfdata["graphdict"] = modify_nodes(tfdata["graphdict"], tfdata["annotations"])
        tfdata["meta_data"] = modify_metadata(
            tfdata["annotations"], tfdata["graphdict"], tfdata["meta_data"]
        )

    return tfdata


def _fan_out_edge_labels_to_numbered_siblings(
    tfdata: Dict[str, Any],
) -> None:
    """Copy edge_labels from a numbered resource to its siblings.

    The AI typically labels ``aws_fargate.ecs~1 -> target`` but not the
    identical edges from ``~2`` and ``~3``. This helper detects the
    ``~N`` suffix, finds all siblings with the same base name, and
    copies the ``edge_labels`` to each sibling — remapping target names
    so they match the sibling's actual connections in graphdict.

    For example, if ``~1`` has a label for target
    ``aws_efs_mount_target.this[0]~1`` and ``~2`` connects to
    ``aws_efs_mount_target.this[1]~2``, the label is remapped to the
    ``~2`` target name so ``get_edge_labels`` can find it at render
    time.
    """
    graphdict = tfdata["graphdict"]
    meta = tfdata["meta_data"]

    # Collect base names and their numbered instances. We use
    # remove_numbered_suffix (strips both [N] and ~M) so that
    # aws_efs_mount_target.this[0]~1 and aws_efs_mount_target.this[1]~2
    # land in the same sibling group.
    base_to_siblings: Dict[str, List[str]] = {}
    for key in graphdict:
        if "~" in key or "[" in key:
            base = helpers.remove_numbered_suffix(key)
            base_to_siblings.setdefault(base, []).append(key)

    for base, siblings in base_to_siblings.items():
        if len(siblings) < 2:
            continue
        # Find the first sibling that has edge_labels.
        source_labels = None
        for sib in siblings:
            labels = (meta.get(sib) or {}).get("edge_labels")
            if labels:
                source_labels = labels
                break
        if not source_labels:
            continue
        # Fan out to every sibling that doesn't already have labels.
        for sib in siblings:
            sib_meta = meta.get(sib)
            if sib_meta is None:
                continue
            if sib_meta.get("edge_labels"):
                continue
            # Build a mapping from base-target-name → actual-target-name
            # for this sibling's connections so we can remap labels whose
            # targets are also numbered instances.
            sib_targets = graphdict.get(sib, [])
            base_to_actual: Dict[str, str] = {}
            for tgt in sib_targets:
                base_to_actual[helpers.remove_numbered_suffix(tgt)] = tgt

            remapped: List[Any] = []
            for label_entry in source_labels:
                if isinstance(label_entry, dict):
                    orig_target = next(iter(label_entry))
                    label_text = label_entry[orig_target]
                    orig_base = helpers.remove_numbered_suffix(orig_target)
                    actual = base_to_actual.get(orig_base, orig_target)
                    remapped.append({actual: label_text})
                else:
                    remapped.append(label_entry)
            sib_meta["edge_labels"] = remapped


def apply_ai_annotations(
    tfdata: Dict[str, Any], ai_annotations: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply AI-generated annotations to fully-enriched tfdata.

    Called from compile_tfdata AFTER _enrich_graph_data has finished,
    so the AI's references resolve against the final graphdict the
    renderer iterates. The AI annotations are merged with any
    user-authored annotations already present in tfdata['annotations']
    using the standard precedence rules (user wins on conflict).

    The deterministic graph (the topology) is left intact — only edge
    labels, the title, and external-actor connections are added on top.
    """
    if not ai_annotations:
        return tfdata

    user_ann = tfdata.get("annotations") or None
    merged = merge_annotations(
        ai_annotations=ai_annotations,
        user_annotations=user_ann,
        cli_annotations=None,
    )
    if not merged:
        return tfdata

    if merged.get("generated_by"):
        gb = merged["generated_by"]
        click.echo(
            click.style(
                f"\n  AI annotations from {gb.get('backend', '?')}/"
                f"{gb.get('model', '?')} ({gb.get('timestamp', '?')})\n",
                fg="cyan",
            )
        )

    tfdata["graphdict"] = modify_nodes(tfdata["graphdict"], merged)
    tfdata["meta_data"] = modify_metadata(
        merged, tfdata["graphdict"], tfdata["meta_data"]
    )
    # Fan out edge labels from ~1 instances to ~2, ~3, etc. so all
    # numbered instances of the same resource show the same labels.
    _fan_out_edge_labels_to_numbered_siblings(tfdata)
    # Remember the merged dict for downstream consumers (the renderer
    # reads tfdata['annotations'] when fetching titles, etc.).
    tfdata["annotations"] = merged
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
    click.echo("\nApplying Annotations:\n")

    if annotate.get("title"):
        click.echo(f"Title: {annotate['title']}\n")

    # Add new nodes to the graph. Use setdefault so we don't clobber
    # edges that an earlier pipeline step (e.g. auto-annotations)
    # already attached to this node.
    if annotate.get("add"):
        for node in annotate["add"]:
            click.echo(f"+ {node}")
            graphdict.setdefault(node, [])

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
                    # Defensive: a connect entry whose source node does
                    # not exist in graphdict cannot be processed. This
                    # would normally be caught by the annotation file
                    # validator, but if a malformed file ever reaches
                    # here we drop the entry with a warning rather
                    # than crashing the whole render with a KeyError.
                    if startnode not in graphdict:
                        click.echo(
                            click.style(
                                f"  WARNING: connect source '{startnode}' not in "
                                f"graphdict; skipping",
                                fg="yellow",
                            )
                        )
                        continue
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
                        if helpers.get_no_module_name(node).startswith(
                            prefix
                        ) and connection in graphdict.get(node, []):
                            graphdict[node].remove(connection)
                else:
                    if connection in graphdict.get(startnode, []):
                        graphdict[startnode].remove(connection)

    # Delete nodes from the graph
    if annotate.get("remove"):
        for node in annotate["remove"]:
            if node in graphdict or "*" in node:
                click.echo(f"~ {node}")
                prefix = node.split("*")[0]
                # Handle wildcard deletion
                if "*" in node:
                    # Delete all nodes matching prefix
                    matching = [
                        k
                        for k in list(graphdict.keys())
                        if helpers.get_no_module_name(k).startswith(prefix)
                    ]
                    for m in matching:
                        graphdict.pop(m, None)
                else:
                    graphdict.pop(node, None)

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
    # IMPORTANT ORDERING NOTE:
    # `add` MUST be processed before `connect` because `add` initialises
    # metadata[node] = {} which would otherwise wipe any edge_labels that
    # `connect` had just written for the same node. Previously the order
    # was reversed and edge labels for nodes that appeared in both
    # sections (e.g. an external actor in `add` that also has labelled
    # outbound connections in `connect`) were silently destroyed.

    # Add metadata for newly added nodes (must run BEFORE connect).
    if annotations.get("add"):
        for node in annotations["add"]:
            if node not in metadata:
                metadata[node] = {}
            # Copy all attributes from annotation to metadata. The shape
            # of an `add` entry can be a dict (preferred) or — when the
            # caller passes a list-of-strings — None; treat None as no
            # attributes to apply.
            attrs = annotations["add"][node]
            if isinstance(attrs, dict):
                for param, value in attrs.items():
                    metadata[node][param] = value

    # Add edge labels from connect annotations.
    if annotations.get("connect"):
        for node in annotations["connect"]:
            # Handle wildcard patterns for edge labels.
            if "*" in node:
                found_matching = helpers.list_of_dictkeys_containing(metadata, node)
                for key in found_matching:
                    metadata[key]["edge_labels"] = annotations["connect"][node]
            else:
                # Defensively initialise metadata for the source node if
                # it does not yet exist (can happen when modify_nodes
                # has just appended a brand-new connect source that did
                # not have a metadata entry, e.g. an AI-suggested
                # external actor that did not get an explicit `add`).
                if node not in metadata:
                    metadata[node] = {}
                metadata[node]["edge_labels"] = annotations["connect"][node]

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


# ---------------------------------------------------------------------------
# Flow badge computation (US5)
# ---------------------------------------------------------------------------

DEFAULT_FLOW_COLOR = "#E74C3C"


def compute_flow_step_numbers(
    flows: Dict[str, Any],
) -> tuple:
    """Compute continuous step numbers across all flows.

    Takes the ``flows`` dict from merged annotations and returns a
    triple of:

    * ``node_badges``  – ``{resource_name: [step_numbers]}``
    * ``edge_badges``  – ``{(src, tgt): [step_numbers]}``
    * ``legend_entries`` – ordered list of dicts with keys:
      ``step_number``, ``flow_name``, ``description``, ``xlabel``,
      ``detail``, ``color``

    Steps are numbered continuously across flows in iteration (merge)
    order.  A flow with zero steps is silently skipped.  When a
    resource string contains `` -> `` it is treated as an edge badge
    rather than a node badge.

    Args:
        flows: The ``flows`` section from the merged annotation dict.

    Returns:
        Tuple of (node_badges, edge_badges, legend_entries).
    """
    if not flows:
        return {}, {}, []

    node_badges: Dict[str, List[int]] = {}
    edge_badges: Dict[tuple, List[int]] = {}
    legend_entries: List[Dict[str, Any]] = []

    step_counter = 0

    for flow_name, flow_def in flows.items():
        if not flow_def:
            continue
        steps = flow_def.get("steps") or []
        if not steps:
            continue

        flow_color = flow_def.get("color", DEFAULT_FLOW_COLOR)
        flow_description = flow_def.get("description", "")

        for step in steps:
            step_counter += 1
            resource_ref = step.get("resource", "")
            detail = step.get("detail", "")
            xlabel = step.get("xlabel", "")

            # Edge badge: "src -> tgt"
            if " -> " in resource_ref:
                parts = resource_ref.split(" -> ", 1)
                src = parts[0].strip()
                tgt = parts[1].strip()
                edge_key = (src, tgt)
                edge_badges.setdefault(edge_key, []).append(step_counter)
            else:
                node_badges.setdefault(resource_ref, []).append(step_counter)

            legend_entries.append(
                {
                    "step_number": step_counter,
                    "flow_name": flow_name,
                    "description": flow_description,
                    "xlabel": xlabel,
                    "detail": detail,
                    "color": flow_color,
                }
            )

    return node_badges, edge_badges, legend_entries
