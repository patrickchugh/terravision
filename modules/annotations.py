"""Annotations module for TerraVision.

This module handles automatic and user-defined annotations for Terraform architecture diagrams.
It processes annotation rules to add, remove, connect, and modify nodes in the graph.
"""

import copy
import sys
from typing import Dict, List, Any, Optional
import click
import modules.config_loader as config_loader
import modules.helpers as helpers

# Annotation schema versions accepted by the merger.
# 0.1 is the legacy single-file format. 0.2 adds the `flows` section
# and the two-file (terravision.yml + terravision.ai.yml) model.
# 0.3 adds top-level `fontsize` and `iconsize` keys.
SUPPORTED_ANNOTATION_FORMATS = {"0.1", "0.2", "0.3"}


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


# Keys a flow and each of its steps may have (see docs/annotations.md).
_FLOW_KEYS = {"description", "color", "steps"}
_STEP_KEYS = {"resource", "detail", "xlabel"}


def check_flows(flows: Any) -> Dict[str, Any]:
    """Check the shape of a ``flows`` section and return it.

    Flows arrive from agents as well as YAML files, so a malformed one gets
    a message naming the problem rather than a traceback while drawing.

    Raises:
        helpers.TerravisionError: When the shape is wrong.
    """

    def fail(problem: str) -> None:
        raise helpers.TerravisionError(
            f'Invalid flows: {problem}. Expected {{<flow name>: {{"description": '
            f'..., "steps": [{{"resource": "<node>" or "<node> -> <node>", '
            f'"detail": ...}}]}}}}.'
        )

    if not isinstance(flows, dict) or not flows:
        fail("flows must be a non-empty object keyed by flow name")
    for name, flow in flows.items():
        if not isinstance(flow, dict):
            fail(f"flow {name!r} must be an object")
        extra = sorted(set(flow) - _FLOW_KEYS)
        if extra:
            fail(f"flow {name!r} has unknown keys {extra}")
        for key in ("description", "color"):
            if key in flow and not isinstance(flow[key], str):
                fail(f"{key} of flow {name!r} must be a string")
        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            fail(f"flow {name!r} needs a non-empty list of steps")
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                fail(f"step {i} of flow {name!r} must be an object")
            extra = sorted(set(step) - _STEP_KEYS)
            if extra:
                fail(f"step {i} of flow {name!r} has unknown keys {extra}")
            if not isinstance(step.get("resource"), str) or not step["resource"]:
                fail(f"step {i} of flow {name!r} needs a resource")
            for key in ("detail", "xlabel"):
                if key in step and not isinstance(step[key], str):
                    fail(f"{key} of step {i} in flow {name!r} must be a string")
    return flows


def _container_types() -> set:
    """Types drawn as boxes, which carry no step badge."""
    from modules.config import cloud_config_aws, cloud_config_azure, cloud_config_gcp

    return {
        *cloud_config_aws.AWS_GROUP_NODES,
        *cloud_config_azure.AZURE_GROUP_NODES,
        *cloud_config_gcp.GCP_GROUP_NODES,
    }


def flow_warnings(flows: Dict[str, Any], graph: Dict[str, List[str]]) -> List[str]:
    """Steps whose badge will not be drawn on this graph.

    A step names a node, or an arrow as ``<node> -> <node>`` in either
    direction. Anything else draws no badge, silently, while the legend
    still lists the step.
    """
    nodes = set(graph) | {t for targets in graph.values() for t in targets}
    containers = _container_types()

    def type_of(address: str) -> str:
        return address.split(".", 1)[0]

    def missing(address: str) -> str:
        copies = sorted(n for n in nodes if n.startswith(address + "~"))
        if copies:
            return f"{address} has numbered copies; name one, such as {copies[0]}"
        return f"{address} is not in the graph"

    found = []
    number = 0
    for name, flow in flows.items():
        for step in flow.get("steps") or []:
            number += 1
            where = f"Step {number} of flow {name!r} draws no badge:"
            ref = step["resource"]
            if " -> " in ref:
                src, dst = (part.strip() for part in ref.split(" -> ", 1))
                absent = [n for n in (src, dst) if n not in nodes]
                if absent:
                    found.append(f"{where} {missing(absent[0])}.")
                elif dst not in graph.get(src, []) and src not in graph.get(dst, []):
                    found.append(f"{where} there is no arrow between {src} and {dst}.")
                elif {type_of(src), type_of(dst)} & containers:
                    found.append(
                        f"{where} arrows to and from containers are not drawn."
                    )
            elif ref not in nodes:
                found.append(f"{where} {missing(ref)}.")
            elif type_of(ref) in containers:
                found.append(f"{where} {ref} is a container; name a node inside it.")
    return found


def edge_labels_to_connect(labels: Any) -> Dict[str, List[Dict[str, str]]]:
    """Turn ``{"<node> -> <node>": "label"}`` into the ``connect`` format.

    Raises:
        helpers.TerravisionError: When the shape is wrong.
    """
    if not isinstance(labels, dict) or not labels:
        raise helpers.TerravisionError(
            "Invalid edge_labels: expected a non-empty object such as "
            '{"aws_lambda_function.api -> aws_rds_postgres.db": "Reads records"}.'
        )
    connect: Dict[str, List[Dict[str, str]]] = {}
    for arrow, label in labels.items():
        if not isinstance(arrow, str) or " -> " not in arrow:
            raise helpers.TerravisionError(
                f"Invalid edge_labels key {arrow!r}: write the arrow as "
                '"<node> -> <node>".'
            )
        if not isinstance(label, str):
            raise helpers.TerravisionError(
                f"The label for {arrow!r} in edge_labels must be a string."
            )
        src, dst = (part.strip() for part in arrow.split(" -> ", 1))
        connect.setdefault(src, []).append({dst: label})
    return connect


def apply_edge_labels(
    tfdata: Dict[str, Any], connect: Optional[Dict[str, Any]]
) -> List[str]:
    """Label arrows the graph already has, from a ``connect`` section.

    For a graph, ``connect`` only labels: an entry names an arrow in either
    direction and never adds one. Labels given here win over earlier ones
    for the same arrow. Returns a warning for each label that is not drawn.
    """
    if not connect:
        return []
    if not isinstance(connect, dict):
        raise helpers.TerravisionError(
            "connect must map each source node to a list of {target: label}."
        )
    graph = tfdata.get("graphdict", {})
    containers = _container_types()
    metadata = tfdata.setdefault("meta_data", {})
    found = []
    for src, entries in connect.items():
        if not isinstance(entries, list):
            entries = [entries]
        for entry in entries:
            pairs = entry.items() if isinstance(entry, dict) else [(entry, "")]
            for dst, label in pairs:
                where = f"The label {label!r} on {src} -> {dst} is not drawn:"
                if dst in graph.get(src, []):
                    origin, target = src, dst
                elif src in graph.get(dst, []):
                    origin, target = dst, src
                else:
                    found.append(
                        f"{where} there is no arrow between them. A label never "
                        "adds an arrow; add it to the graph first."
                    )
                    continue
                if {origin.split(".")[0], target.split(".")[0]} & containers:
                    found.append(f"{where} arrows to containers are not drawn.")
                    continue
                if label:
                    labels = metadata.setdefault(origin, {}).setdefault(
                        "edge_labels", []
                    )
                    labels.insert(0, {target: str(label)})
    return found


def check_attribute_updates(update: Any, what: str = "update") -> Dict[str, Any]:
    """Check the shape of an ``update`` section (or MCP ``attributes``).

    Raises:
        helpers.TerravisionError: When it is not an object mapping each node
            to an object of attributes.
    """
    example = '{"aws_subnet.public~1": {"cidr_block": "10.0.1.0/24"}}'
    if not isinstance(update, dict) or not update:
        raise helpers.TerravisionError(
            f"Invalid {what}: expected a non-empty object mapping each node to "
            f"its attributes, such as {example}."
        )
    for node, attrs in update.items():
        if not isinstance(node, str) or not node:
            raise helpers.TerravisionError(
                f"Invalid {what} key {node!r}: name a node, such as "
                "aws_subnet.public~1."
            )
        if not isinstance(attrs, dict) or not attrs:
            raise helpers.TerravisionError(
                f"The {what} for {node!r} must be a non-empty object of "
                f'attributes, such as {{"cidr_block": "10.0.1.0/24"}}.'
            )
    return update


def _nodes_named(name: str, nodes: set) -> List[str]:
    """Nodes an ``update`` key names, as ``modify_metadata`` matches them.

    A key with ``*`` matches every node containing the text before the
    ``*``. Otherwise the key names a node, or every numbered copy of it
    (``aws_subnet.public`` names ``aws_subnet.public~1`` and ``~2``), as a
    Terraform resource with count does.
    """
    if "*" in name:
        prefix = name.split("*")[0]
        return sorted(n for n in nodes if prefix in n)
    if name in nodes:
        return [name]
    return sorted(n for n in nodes if n.split("~")[0] == name)


def apply_attribute_updates(
    tfdata: Dict[str, Any], update: Optional[Dict[str, Any]]
) -> List[str]:
    """Set attributes on nodes the graph already has, from an ``update`` section.

    Used for graph (.tvg.json) sources, which are drawn as written: an update
    never adds a node. Values go to ``tfdata["meta_data"]``, where the drawing
    reads them (``cidr_block`` on aws_subnet, for instance, puts the range in
    the box's label). ``edge_labels`` label existing arrows, as ``connect``
    does. Returns a warning for each name that matches no node, and for each
    label that is not drawn.

    Raises:
        helpers.TerravisionError: When the section has the wrong shape.
    """
    if not update:
        return []
    check_attribute_updates(update)
    graph = tfdata.get("graphdict", {})
    nodes = set(graph) | {t for targets in graph.values() for t in targets}
    metadata = tfdata.setdefault("meta_data", {})
    found = []
    for name, attrs in update.items():
        targets = _nodes_named(name, nodes)
        if not targets:
            found.append(
                f"The update for {name} is not applied: {name} is not in the "
                "graph. Name a node the graph has, such as aws_subnet.public~1."
            )
            continue
        for node in targets:
            for attr, value in attrs.items():
                if attr == "edge_labels":
                    found += apply_edge_labels(tfdata, {node: value})
                else:
                    metadata.setdefault(node, {})[attr] = copy.deepcopy(value)
    return found


# Annotation sections a graph file can take. A graph is drawn exactly as
# written, so a graph file may use every section except those that change
# its structure (GRAPH_STRUCTURAL_KEYS), which belong in the graph itself.
# connect only labels arrows the graph already has; update only sets
# attributes on nodes it already has.
GRAPH_ANNOTATION_KEYS = (
    "format",
    "title",
    "flows",
    "connect",
    "update",
    "fontsize",
    "iconsize",
    "generated_by",
)

# Sections that add, remove or disconnect nodes, refused for a graph.
GRAPH_STRUCTURAL_KEYS = ("add", "remove", "disconnect")


def load_graph_annotations(path: str, graph: Dict[str, List[str]]) -> Dict[str, Any]:
    """Load an ``--annotate`` file for a graph (.tvg.json) source.

    Prints a warning for each flow step that will draw no badge. Edge labels
    in ``connect`` are applied by :func:`apply_edge_labels`, and attributes
    in ``update`` by :func:`apply_attribute_updates`.

    Raises:
        helpers.TerravisionError: For an unreadable file, a section that
            changes the graph (GRAPH_STRUCTURAL_KEYS) or is unknown, or
            malformed flows or updates.
    """
    import yaml

    try:
        with open(path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as e:
        raise helpers.TerravisionError(f"Cannot read annotation file {path}: {e}")
    if not isinstance(loaded, dict):
        raise helpers.TerravisionError(
            f"Annotation file {path} must be a YAML mapping."
        )
    structural = sorted(k for k in GRAPH_STRUCTURAL_KEYS if k in loaded)
    if structural:
        raise helpers.TerravisionError(
            f"{path} has {', '.join(structural)}, which a graph file does not "
            "take: adding, removing or disconnecting nodes changes the graph, "
            "so change the graph itself instead (connect is allowed, to label "
            "arrows the graph already has, and update, to set attributes on "
            f"its nodes). Allowed here: {', '.join(GRAPH_ANNOTATION_KEYS)}."
        )
    other = sorted(str(k) for k in set(loaded) - set(GRAPH_ANNOTATION_KEYS))
    if other:
        raise helpers.TerravisionError(
            f"{path} has {', '.join(other)}, which is not an annotation "
            f"section. Allowed here: {', '.join(GRAPH_ANNOTATION_KEYS)}."
        )
    if "update" in loaded:
        check_attribute_updates(loaded["update"])
    fmt = loaded.get("format")
    if fmt is not None and str(fmt) not in SUPPORTED_ANNOTATION_FORMATS:
        raise helpers.TerravisionError(
            f"{path} declares unsupported format {fmt!r}. Accepted: "
            f"{', '.join(sorted(SUPPORTED_ANNOTATION_FORMATS))}."
        )
    if "flows" in loaded:
        check_flows(loaded["flows"])
        for warning in flow_warnings(loaded["flows"], graph):
            click.echo(click.style(f"  WARNING: {warning}", fg="yellow"))
    return loaded
