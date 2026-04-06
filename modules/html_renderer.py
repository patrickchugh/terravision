"""
HTML Renderer for TerraVision interactive diagrams.

Generates self-contained HTML files with interactive architecture diagrams
using d3-graphviz (Graphviz compiled to WebAssembly) for in-browser rendering.
"""

import ast
import base64
import binascii
import copy
import gzip
import json
import os
import re
import webbrowser
from pathlib import Path
from typing import Any, Dict, Set, Tuple


def render_html(
    tfdata: Dict[str, Any],
    show: bool,
    outfile: str,
    source: str,
) -> None:
    """Main entry point for HTML diagram generation.

    Orchestrates DOT generation, icon embedding, metadata serialization,
    and HTML assembly into a single self-contained output file.
    """
    import click
    import modules.drawing as drawing

    click.echo(
        click.style("\nGenerating Interactive HTML Diagram...", fg="white", bold=True)
    )

    # Generate SVG with embedded icons using local Graphviz
    svg_string, icon_paths, node_id_map, cluster_id_map = drawing.generate_svg(
        tfdata, outfile, source
    )

    # Serialize metadata for embedding
    metadata = _serialize_metadata(tfdata)
    metadata["node_id_map"] = node_id_map
    metadata["cluster_id_map"] = cluster_id_map
    metadata_json = json.dumps(metadata, indent=None, default=str)

    # Extract diagram title from annotations
    title = tfdata.get("annotations", {}).get(
        "title", "TerraVision Architecture Diagram"
    )

    # Ensure .html extension
    if not outfile.endswith(".html"):
        outfile = outfile + ".html"

    # Assemble and write the HTML file
    output_path = _assemble_html(svg_string, metadata_json, outfile, title)
    click.echo(f"  Output file: {output_path}")
    click.echo("  Completed!")

    # Auto-open in browser if requested
    if show:
        abs_path = os.path.abspath(output_path)
        webbrowser.open(f"file://{abs_path}")


def _embed_icons_as_base64(
    dot_string: str, icon_paths: Set[str]
) -> Tuple[str, Dict[str, str]]:
    """Replace absolute icon file paths in DOT with base64 data URIs.

    Returns the modified DOT string and a dict of failed paths (empty on success).
    """
    failed = {}
    for icon_path in icon_paths:
        if not os.path.isfile(icon_path):
            failed[icon_path] = "File not found"
            continue
        try:
            with open(icon_path, "rb") as f:
                icon_data = f.read()
            # Determine MIME type from extension
            ext = os.path.splitext(icon_path)[1].lower()
            mime = {
                ".png": "image/png",
                ".svg": "image/svg+xml",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
            }.get(ext, "image/png")
            b64 = base64.b64encode(icon_data).decode("ascii")
            data_uri = f"data:{mime};base64,{b64}"
            dot_string = dot_string.replace(icon_path, data_uri)
        except Exception as e:
            failed[icon_path] = str(e)
    return dot_string, failed


def _serialize_metadata(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize tfdata metadata, original_metadata, and graphdict for HTML embedding.

    Deep copies the data, removes non-serializable keys, normalizes
    known-after-apply values, and adds synthetic instance info.
    """
    result = {}

    # Serialize pre_draw_metadata (snapshot taken before drawing overwrites entries)
    # Falls back to meta_data if pre_draw_metadata not available
    meta = {}
    source_meta = tfdata.get("pre_draw_metadata", tfdata.get("meta_data", {}))
    for node_name, attrs in copy.deepcopy(source_meta).items():
        if isinstance(attrs, dict):
            cleaned = _clean_metadata_dict(attrs)
            # Add instance info for numbered resources
            instance_info = _get_instance_info(node_name, tfdata)
            if instance_info:
                cleaned["_instance_info"] = instance_info
            meta[node_name] = cleaned
    result["metadata"] = meta

    # Serialize original_metadata with its original keys
    orig_meta = {}
    for node_name, attrs in copy.deepcopy(tfdata.get("original_metadata", {})).items():
        if isinstance(attrs, dict):
            orig_meta[node_name] = _clean_metadata_dict(attrs)
    result["original_metadata"] = orig_meta

    # Build a comprehensive mapping from current meta_data keys to
    # original_metadata keys, covering all renames/consolidations/variants.
    # Strategy: for each current key not in original, find the original key
    # whose metadata content matches (was copied during consolidation).
    reverse_map = {}
    orig_keys = set(orig_meta.keys())
    name_map = tfdata.get("resource_name_map", {})
    raw_orig = tfdata.get("original_metadata", {})

    for current_name in tfdata.get("meta_data", {}).keys():
        if current_name in orig_keys:
            continue
        # 1. Check explicit resource_name_map from consolidation
        if current_name in name_map and name_map[current_name] in orig_keys:
            reverse_map[current_name] = name_map[current_name]
            continue
        # 2. Strip ~N suffix
        base = current_name.rsplit("~", 1)[0] if "~" in current_name else None
        if base and base in orig_keys:
            reverse_map[current_name] = base
            continue
        # 3. Match by resource type: current "aws_rds_aurora_mysql.this" -> original "aws_rds_cluster.this"
        #    Use the actual metadata content — if meta_data[current] was copied from original[X],
        #    they'll share distinctive attribute values
        current_meta = tfdata.get("meta_data", {}).get(current_name, {})
        if isinstance(current_meta, dict):
            # Get a distinctive attribute to match on (name, arn, id patterns)
            for match_key in ("name", "cluster_identifier", "function_name", "bucket"):
                match_val = current_meta.get(match_key)
                if match_val and isinstance(match_val, str) and match_val != "unknown":
                    for ok, ov in raw_orig.items():
                        if isinstance(ov, dict) and ov.get(match_key) == match_val:
                            reverse_map[current_name] = ok
                            break
                if current_name in reverse_map:
                    break
    result["original_name_map"] = reverse_map

    # Serialize graphdict (already JSON-serializable)
    result["graphdict"] = copy.deepcopy(tfdata.get("graphdict", {}))

    # Build sibling_resources from CONSOLIDATED_NODES config.
    # CONSOLIDATED_NODES maps a prefix (e.g. "aws_ecs") to a single diagram node.
    # All original resources sharing that prefix are siblings of the consolidated node.
    # This lets users click a consolidated node and navigate to the individual resources.
    from modules.config_loader import load_config
    from modules.provider_detector import get_primary_provider_or_default

    consolidated_prefixes = []
    try:
        provider = get_primary_provider_or_default(tfdata)
        config = load_config(provider)
        consolidated_nodes_config = getattr(
            config, f"{provider.upper()}_CONSOLIDATED_NODES", []
        )
        for entry in consolidated_nodes_config:
            for prefix, details in entry.items():
                consolidated_prefixes.append((prefix, details.get("resource_name", "")))
    except Exception:
        pass

    # Group original_metadata keys by consolidated prefix and module scope
    sibling_map = {}
    for orig_key in raw_orig:
        # Extract module prefix
        parts = orig_key.split(".")
        if parts[0] == "module":
            mod_prefix = ".".join(parts[:2])
            res_part = ".".join(parts[2:])
        else:
            mod_prefix = ""
            res_part = orig_key

        # Check which consolidated prefix this resource matches
        for prefix, consolidated_name in consolidated_prefixes:
            if res_part.startswith(prefix):
                group_key = mod_prefix + "|" + prefix
                if group_key not in sibling_map:
                    sibling_map[group_key] = {
                        "consolidated_name": consolidated_name,
                        "members": [],
                    }
                sibling_map[group_key]["members"].append(orig_key)
                break

    # Also group resources by shared type prefix within the same module scope.
    # e.g. aws_route_table, aws_route_table_association both start with "aws_route_table"
    # This automatically captures related resources without maintaining explicit lists.
    # First, bucket resources by module prefix for efficient comparison.
    by_module = {}
    for orig_key in raw_orig:
        parts = orig_key.split(".")
        if parts[0] == "module":
            mod_prefix = ".".join(parts[:2])
            res_type = parts[2] if len(parts) > 2 else ""
        else:
            mod_prefix = ""
            res_type = parts[0] if parts else ""
        by_module.setdefault(mod_prefix, []).append((orig_key, res_type))

    # Within each module, group resources whose types share a prefix
    for mod_prefix, resources in by_module.items():
        # Sort by type so prefix matches are adjacent
        resources.sort(key=lambda x: x[1])
        for i, (key_a, type_a) in enumerate(resources):
            for j, (key_b, type_b) in enumerate(resources):
                if i == j:
                    continue
                if type_a.startswith(type_b) or type_b.startswith(type_a):
                    group_key = key_a + "|prefix"
                    if group_key not in sibling_map:
                        sibling_map[group_key] = {
                            "consolidated_name": "",
                            "members": [key_a],
                        }
                    if key_b not in sibling_map[group_key]["members"]:
                        sibling_map[group_key]["members"].append(key_b)

    # Build the final map: consolidated node name -> list of original resources
    # AND each original resource -> its siblings
    resource_siblings = {}
    for group_key, group_data in sibling_map.items():
        members = group_data["members"]
        cname = group_data["consolidated_name"]
        mod_prefix = group_key.split("|")[0]

        # The consolidated node's full name (with module prefix)
        if cname:
            full_cname = (mod_prefix + "." + cname) if mod_prefix else cname
            if len(members) > 0:
                resource_siblings[full_cname] = members

        # Map each member to its siblings
        if len(members) > 1:
            for member in members:
                existing = resource_siblings.get(member, [])
                new_siblings = [m for m in members if m != member and m not in existing]
                resource_siblings[member] = existing + new_siblings

    result["resource_siblings"] = resource_siblings

    return result


def _clean_metadata_dict(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Remove non-serializable keys and normalize known-after-apply values."""
    cleaned = {}
    for key, value in attrs.items():
        # Skip non-serializable node objects
        if key == "node":
            continue
        # Skip internal markers except _synthetic and _data_source
        if key.startswith("_") and key not in ("_synthetic", "_data_source"):
            continue
        # Replace boolean True for known-after-apply attributes
        if value is True and key not in (
            "_synthetic",
            "_data_source",
            "force_destroy",
            "get_password_data",
            "source_dest_check",
            "associate_public_ip_address",
            "user_data_replace_on_change",
            "enable_dns_support",
            "enable_dns_hostnames",
            "map_public_ip_on_launch",
        ):
            cleaned[key] = "Computed (known after apply)"
        else:
            cleaned[key] = _normalize_value(key, value)
    return cleaned


def _normalize_value(key: str, value: Any) -> Any:
    """Convert Python repr strings back to dicts/lists, decode base64 user_data,
    and clean up interpreter artifacts (extra quotes/whitespace)."""
    # If string, try to parse Python repr back into a real object
    if isinstance(value, str):
        stripped = value.strip()
        # Detect Python list/dict repr
        if (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("{") and stripped.endswith("}")
        ):
            try:
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, (list, dict)):
                    # Recursively normalize nested values
                    return _deep_normalize(parsed)
            except (ValueError, SyntaxError):
                pass

        # Detect base64-encoded user_data fields and decode them
        if key in ("user_data", "user_data_base64") and len(stripped) > 16:
            decoded_text = _try_decode_base64(stripped)
            if decoded_text is not None:
                return decoded_text

        # Clean up interpreter artifacts: trailing whitespace and surrounding quotes
        cleaned = _clean_string_value(stripped)
        if cleaned != value:
            return cleaned

    # Ensure the value is JSON-serializable
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _clean_string_value(s: str) -> str:
    """Clean up interpreter artifacts in a string value.

    - Strip leading/trailing whitespace
    - Strip surrounding double quotes if the entire value is wrapped in them
    - Strip ${...} Terraform expression wrappers, keeping inner reference
    - Replace literal "UNKNOWN" markers with <unknown>
    """
    import modules.helpers as helpers

    s = s.strip()
    # Strip ${...} Terraform expression wrappers using existing helper
    if "${" in s:
        s = helpers.remove_terraform_functions(s)
        # Also strip standalone ${...} that just wraps a reference
        s = re.sub(r"\$\{([^}]+)\}", r"\1", s)
    # If the whole string is wrapped in matching double quotes, unwrap once
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        inner = s[1:-1]
        if '"' not in inner:
            s = inner
    # Replace UNKNOWN markers (left by interpreter when value can't be resolved)
    s = s.replace('"UNKNOWN"', "<unknown>")
    return s.strip()


def _try_decode_base64(s: str) -> str | None:
    """Decode a base64 string, optionally gzip-decompressing it.

    Returns the decoded text if successful and looks like printable text,
    or None if decoding failed or result is binary.
    """
    # Strip surrounding quotes/whitespace
    candidate = s.strip().strip("\"'").strip()
    # Add missing base64 padding
    padding = (-len(candidate)) % 4
    candidate_padded = candidate + ("=" * padding)

    try:
        raw = base64.b64decode(candidate_padded, validate=True)
    except (binascii.Error, ValueError):
        return None

    # If it starts with gzip magic bytes (1f 8b 08), decompress
    if len(raw) >= 3 and raw[0] == 0x1F and raw[1] == 0x8B and raw[2] == 0x08:
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            return None

    # Try to decode as UTF-8 text
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None

    # Only return if it looks like text (mostly printable chars)
    if not text:
        return None
    printable = sum(1 for c in text if c.isprintable() or c in "\n\t\r")
    if printable / len(text) < 0.95:
        return None
    return text


def _deep_normalize(obj: Any) -> Any:
    """Recursively normalize nested dicts/lists, ensuring JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _deep_normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_normalize(v) for v in obj]
    if isinstance(obj, str):
        return _clean_string_value(obj)
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _get_instance_info(node_name: str, tfdata: Dict[str, Any]) -> Dict[str, Any] | None:
    """Extract instance numbering info for numbered resources (e.g., web~2)."""
    if "~" not in node_name:
        return None

    base_name, instance_str = node_name.rsplit("~", 1)
    try:
        instance_number = int(instance_str)
    except ValueError:
        return None

    # Strip [N] index from base_name for counting
    # e.g. "aws_efs_mount_target.this[1]" -> "aws_efs_mount_target.this"
    count_base = re.sub(r"\[\d+\]$", "", base_name)

    # Count total instances with the same base name (with or without [N] index)
    total = sum(
        1
        for name in tfdata.get("pre_draw_metadata", tfdata.get("meta_data", {}))
        if "~" in name and re.sub(r"\[\d+\]$", "", name.rsplit("~", 1)[0]) == count_base
    )

    # Determine if synthetic (from detect_and_set_counts) or real (from TF count/for_each)
    is_synthetic = False
    meta = tfdata.get("meta_data", {}).get(node_name, {})
    if isinstance(meta, dict):
        is_synthetic = meta.get("_synthetic", False)

    return {
        "instance_number": instance_number,
        "total_instances": total,
        "base_name": base_name,
        "is_synthetic": is_synthetic,
    }


def _assemble_html(
    svg_string: str,
    metadata_json: str,
    outfile: str,
    title: str = "TerraVision Architecture Diagram",
) -> str:
    """Assemble the final self-contained HTML file.

    Reads the HTML template and vendored d3.js, embeds the pre-rendered SVG
    and metadata JSON, and writes the output file.

    Returns the path to the written file.
    """
    vendor_dir = Path(__file__).parent / "vendor"
    template_path = Path(__file__).parent / "templates" / "interactive.html"

    # Read template
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Read vendored d3.js (still needed for interactivity: zoom, click, animation)
    with open(vendor_dir / "d3.min.js", "r", encoding="utf-8") as f:
        d3_js = f.read()

    # Replace placeholders
    html = html.replace("{{TITLE}}", title)
    html = html.replace("{{D3_JS}}", d3_js)
    html = html.replace("{{SVG_CONTENT}}", svg_string)
    html = html.replace("{{METADATA_JSON}}", metadata_json)

    # Write output file
    output_path = str(Path.cwd() / outfile)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
