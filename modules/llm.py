"""LLM/AI backend integration for TerraVision.

Generates a separate ``terravision.ai.yml`` annotation file from the
deterministic graphdict without ever modifying the graphdict itself.
The deterministic graph (graphdict, tfdata) is the source of truth and
must remain byte-identical whether or not the AI is invoked; the AI
output is a *supplementary* artifact that the renderer merges in at
draw time, with the user's hand-authored ``terravision.yml`` always
winning on conflict.

The legacy ``refine_with_llm()`` flow — which sent graphdict to the LLM
and replaced it with the response — has been removed. The two backend
stream helpers and preflight reachability checks are retained because
they are reused for annotation generation.
"""

import datetime as _dt
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import ollama
import requests
import yaml

from modules.config_loader import load_config
from modules.provider_detector import get_primary_provider_or_default


# ---------------------------------------------------------------------------
# Backend reachability checks (preflight)
# ---------------------------------------------------------------------------


def check_ollama_server(ollama_host: str) -> None:
    """Check if Ollama server is reachable.

    Args:
        ollama_host: Ollama server host URL
    """
    click.echo("  checking Ollama server..")
    try:
        response = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            click.echo(f"  Ollama server reachable at: {ollama_host}")
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: Ollama server returned status {response.status_code}",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    except requests.exceptions.RequestException as e:
        click.echo(
            click.style(
                f"\n  ERROR: Cannot reach Ollama server at {ollama_host}: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def check_bedrock_endpoint(bedrock_endpoint: str) -> None:
    """Check if Bedrock API endpoint is reachable.

    Args:
        bedrock_endpoint: Bedrock API Gateway endpoint URL
    """
    click.echo("  checking Bedrock API Gateway endpoint..")
    try:
        response = requests.get(bedrock_endpoint, timeout=5, stream=True)
        if response.status_code in [200, 403, 404]:
            click.echo(f"  Bedrock API Gateway reachable at: {bedrock_endpoint}")
            if response.status_code == 200:
                response.close()
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: Bedrock API Gateway returned status {response.status_code}",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    except requests.exceptions.RequestException as e:
        click.echo(
            click.style(
                f"\n  ERROR: Cannot reach Bedrock API Gateway endpoint at {bedrock_endpoint}: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def create_ollama_client(ollama_host: str) -> ollama.Client:
    """Create and return Ollama LLM client."""
    return ollama.Client(host=ollama_host, headers={"x-some-header": "some-value"})


# ---------------------------------------------------------------------------
# Annotation prompt
#
# Single provider-agnostic prompt. The LLM identifies the cloud provider
# from resource name prefixes (aws_, azurerm_, google_) inside the
# graphdict — there is no per-provider prompt template.
# ---------------------------------------------------------------------------

ANNOTATION_PROMPT = """\
You annotate an existing cloud architecture diagram. You will be given
TWO allow-lists below: a list of resource names and a list of edges.
Your job is to produce a YAML annotation file that adds a TITLE,
short LABELS to existing edges, and optionally one or two external
ACTORS connected to entry-point resources. You MUST NOT redraw the
diagram or invent any name not in the allow-lists.

================================================================
ALLOW-LIST 1 — RESOURCE NAMES
Every resource identifier you write must be COPIED EXACTLY from
this list. Do not shorten. Do not invent prettier local names. Do
not strip "module." prefixes or "[0]~1" suffixes. The local part
".this" is correct even if it looks generic.
================================================================
{inventory}
================================================================

================================================================
ALLOW-LIST 2 — EXISTING EDGES (source -> target)
You may write a `connect: source: [target: "label"]` entry ONLY
if the (source, target) pair appears verbatim in this list, OR if
one endpoint is an external actor you put in the `add` section.
Anything else is silently dropped. Pick 5 to 15 of the most
meaningful edges to label — you do not need to label every one.
================================================================
{edges}
================================================================

CONTEXT (project intent — README / comments / tags, use only to
write meaningful labels, NOT to invent resource names):
{context}

================================================================
EXTERNAL ACTORS (the only place you may add a new node name)
================================================================
External actors implied by the architecture (end users, on-prem
datacentres, mobile clients) belong in the `add` section. They are
the ONE situation where you may write a node name that is not in
the allow-list above, AND the ONE situation where you may draw a
new edge (from the actor to an existing resource). You MUST use
one of these built-in identifiers — they are the only names with
registered icons:

{actors}

================================================================
OUTPUT FORMAT — the YAML you must produce
================================================================
Return ONLY a YAML document. No prose. No code fences. No JSON.
First line MUST be `format: "0.2"`. Do NOT output a `generated_by`
block (the caller adds that).

```yaml
format: "0.2"
title: "Concise architecture title (max 80 chars)"
add:
  tv_aws_users.users:
    label: "End Users / Web Browsers"
connect:
  <source name copied from ALLOW-LIST 1>:
    - <target name copied from ALLOW-LIST 1>: "Short verb-phrase label"
flows:                          # optional, omit if no clear request path
  user-request:
    description: "End-user request flow"
    steps:
      - resource: tv_aws_users.users
        xlabel: "Request"
        detail: "User issues HTTPS request"
      - resource: <name copied from ALLOW-LIST 1>
        xlabel: "Process"
        detail: "What happens here in plain language"
```

================================================================
FINAL CHECKLIST — re-read these rules before you start writing
================================================================
1. Every name in connect / flows is COPIED EXACTLY from ALLOW-LIST 1.
2. Every (source, target) pair in connect appears verbatim in
   ALLOW-LIST 2, unless one endpoint is a tv_*.* actor you added.
3. Labels are short verb-phrases ("Reads credentials"), never
   full sentences.
4. The title reflects the actual architecture pattern, not a
   generic placeholder.
5. You output 5–15 high-signal labels, not one for every edge.

Now produce the YAML:
"""


# ---------------------------------------------------------------------------
# Context extraction helper
#
# Builds the optional CONTEXT block that the LLM sees alongside the
# graphdict. We include HCL tags / resource metadata and (at most) one
# README from the source directory. The aim is project-specific signal
# (app name, env, team ownership, business purpose) the LLM can't infer
# from resource types alone — NOT a project knowledge base. Application
# code, dependency graphs, and multi-file documentation are deliberately
# out of scope.
# ---------------------------------------------------------------------------

# README filenames considered when assembling LLM context. Single-file
# only by design — see module docstring above.
_README_CANDIDATES = ("README.md", "README.MD", "Readme.md", "README", "README.txt")


def _build_actors_block(config: Any, provider: str) -> str:
    """Build the external-actor identifier list from the provider's
    AUTO_ANNOTATIONS config.

    Scans the ``*_AUTO_ANNOTATIONS`` list for ``tv_*`` link targets and
    returns them as a flat list the LLM can copy from. This is the
    single source of truth — adding or removing a ``tv_*`` entry in
    ``cloud_config_<provider>.py`` automatically updates the prompt.
    """
    provider_upper = provider.upper()
    auto_annotations = getattr(config, f"{provider_upper}_AUTO_ANNOTATIONS", [])

    actors: set = set()
    for entry in auto_annotations:
        for _, spec in entry.items():
            for link in spec.get("link", []):
                if link.startswith("tv_"):
                    actors.add(link)

    if not actors:
        return "(no external actor identifiers defined for this provider)"

    # Format as a readable list with a description derived from the name.
    lines: List[str] = []
    for actor in sorted(actors):
        # Derive a human-readable description from the node name:
        # tv_aws_users.users → "users", tv_aws_onprem.corporate_datacenter → "corporate datacenter"
        suffix = actor.split(".")[-1] if "." in actor else actor
        description = suffix.replace("_", " ")
        lines.append(f"  {actor:<45s} - {description}")
    return "\n".join(lines)


def _extract_context_block(
    tfdata: Dict[str, Any],
    source_dir: Optional[str],
    max_chars: int = 8000,
) -> str:
    """Build the context block sent to the LLM alongside graphdict.

    Includes:
      * project README (if discoverable; single file only by design)
      * per-resource HCL comments harvested from raw .tf files by the
        fileparser (e.g. "# this lambda processes incoming SQS orders"
        sitting directly above ``resource "aws_lambda_function" "api"``)
      * file-level / module-level HCL comments not bound to a specific
        resource (project intent, file headers, explanatory paragraphs)
      * resource tags from meta_data (compact signal of application
        name, environment, team ownership)

    Hard-capped at ``max_chars`` characters so a giant repo cannot blow
    up the prompt budget.
    """
    parts: List[str] = []

    # Single README from the source directory, if present.
    if source_dir and os.path.isdir(source_dir):
        for candidate in _README_CANDIDATES:
            candidate_path = Path(source_dir) / candidate
            if candidate_path.is_file():
                try:
                    text = candidate_path.read_text(
                        encoding="utf-8", errors="replace"
                    ).strip()
                    if text:
                        parts.append(f"### Project README ({candidate})\n{text}")
                        break
                except OSError:
                    pass

    # Per-resource comments harvested from raw .tf files. These are the
    # highest-signal source of human intent in the codebase — a developer
    # who wrote "# Processes incoming order events from SQS" above a
    # Lambda is telling the LLM exactly what to put on the edge label.
    resource_comments = tfdata.get("tf_comments") or {}
    if isinstance(resource_comments, dict) and resource_comments:
        comment_lines = [
            f"{resource}: {comment}"
            for resource, comment in list(resource_comments.items())[:200]
        ]
        parts.append("### Resource Comments\n" + "\n".join(comment_lines))

    # File / module level comments — the developer's explanation of
    # WHAT this stack does and WHY, not bound to a specific resource.
    unattached_comments = tfdata.get("tf_unattached_comments") or []
    if isinstance(unattached_comments, list) and unattached_comments:
        # Dedupe while preserving order so identical file headers across
        # modules don't crowd out unique commentary.
        seen = set()
        unique_lines = []
        for line in unattached_comments:
            if line and line not in seen:
                seen.add(line)
                unique_lines.append(line)
        if unique_lines:
            parts.append("### Project Comments\n" + "\n".join(unique_lines[:100]))

    # Tags from meta_data — flat list of "resource: tag=val tag=val".
    # We focus on tags only because they're compact and high-signal.
    meta = tfdata.get("meta_data") or {}
    if isinstance(meta, dict):
        tag_lines: List[str] = []
        for resource_name, attrs in meta.items():
            if not isinstance(attrs, dict):
                continue
            tags = attrs.get("tags")
            if isinstance(tags, dict) and tags:
                rendered = " ".join(
                    f"{k}={v}" for k, v in tags.items() if isinstance(k, str)
                )
                if rendered:
                    tag_lines.append(f"{resource_name}: {rendered}")
        if tag_lines:
            parts.append("### Resource Tags\n" + "\n".join(tag_lines[:200]))

    if not parts:
        return "(no additional context available)"

    block = "\n\n".join(parts)
    if len(block) > max_chars:
        block = block[:max_chars] + "\n... [context truncated]"
    return block


# ---------------------------------------------------------------------------
# Backend streaming helpers (Ollama + Bedrock).
#
# Both backends remain supported. Ollama is the local/air-gapped path;
# Bedrock is the cloud path (proxied through an API Gateway endpoint).
# Streaming is preserved so users see incremental output for long
# generations.
# ---------------------------------------------------------------------------


def _stream_ollama_text(
    client: ollama.Client,
    prompt: str,
    model: str = "llama3",
) -> str:
    """Stream a chat completion from Ollama and return the full string."""
    stream = client.chat(
        model=model,
        keep_alive=-1,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0, "seed": 42, "top_p": 1.0, "top_k": 1},
        stream=True,
    )
    full_response = ""
    for chunk in stream:
        content = chunk["message"]["content"]
        print(content, end="", flush=True)
        full_response += content
    return full_response


def _stream_bedrock_text(prompt: str, bedrock_endpoint: str) -> str:
    """Stream a chat completion from Bedrock proxy and return the full string."""
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10000,
    }
    response = requests.post(
        bedrock_endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        stream=True,
        timeout=300,
    )
    full_response = ""
    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            print(chunk, end="", flush=True)
            full_response += chunk
    return full_response


# ---------------------------------------------------------------------------
# YAML extraction + validation
# ---------------------------------------------------------------------------

# Match an optional ```yaml fence so we tolerate models that wrap output.
_YAML_FENCE_RE = re.compile(r"```(?:yaml|yml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_yaml_payload(raw: str) -> str:
    """Strip code fences / leading prose so yaml.safe_load can parse it."""
    if not raw:
        return ""
    fence = _YAML_FENCE_RE.search(raw)
    if fence:
        return fence.group(1).strip()
    # Otherwise drop everything before the first `format:` or top-level key.
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("format:", "title:", "add:", "connect:", "flows:")):
            return "\n".join(lines[i:]).strip()
    return raw.strip()


_TOP_LEVEL_REF_KEYS = ("connect", "disconnect", "update")


def _validate_against_graphdict(
    annotations: Dict[str, Any],
    graphdict: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Drop annotation entries referencing resources missing from graphdict.

    Returns the cleaned annotation dict and a list of warning messages
    describing what was dropped. The renderer will refuse to draw an
    annotation pointing at a non-existent node, so the LLM is not
    trusted to invent resource identifiers — every reference is checked
    against the deterministic graphdict before the file is written.

    The ``add`` section is the one exception: it is *allowed* to
    introduce new node names (external actors implied by the
    architecture, e.g. "End Users", "On-Premise Datacentre"). Those
    names then become valid targets for ``connect`` entries in the
    same file.
    """
    warnings: List[str] = []
    if not isinstance(annotations, dict):
        return {}, ["AI response was not a YAML mapping; ignoring entirely"]

    valid_nodes = set(graphdict.keys())
    cleaned: Dict[str, Any] = {}

    # Pass-through scalar / safe sections.
    for key in ("format", "title"):
        if annotations.get(key) is not None:
            cleaned[key] = annotations[key]

    # `add` is allowed to invent node names — pass through as-is, but
    # tolerate the list-of-strings shape too.
    if annotations.get("add"):
        cleaned["add"] = annotations["add"]

    # connect / disconnect / update — only keep entries whose keys *and*
    # target nodes (if applicable) exist in graphdict OR were introduced
    # via the `add` section.
    added_nodes = set()
    add_section = annotations.get("add") or {}
    if isinstance(add_section, dict):
        added_nodes = set(add_section.keys())
    elif isinstance(add_section, list):
        added_nodes = {x for x in add_section if isinstance(x, str)}

    allowed = valid_nodes | added_nodes

    for key in _TOP_LEVEL_REF_KEYS:
        section = annotations.get(key)
        if not isinstance(section, dict):
            continue
        kept: Dict[str, Any] = {}
        for source_node, value in section.items():
            if source_node not in allowed:
                warnings.append(
                    f"AI {key}: dropping unknown source resource '{source_node}'"
                )
                continue
            if key == "update":
                kept[source_node] = value
                continue
            # connect/disconnect: targets list. Each target name must
            # exist in graphdict OR have been introduced by `add`. For
            # `connect` specifically we ALSO require the (source,target)
            # pair to be an existing edge in graphdict — the AI's job
            # is to attach LABELS to existing edges, not to invent new
            # connections that the deterministic graph never had. The
            # one carved-out exception is when either endpoint is in
            # the AI's `add` section: that is a legitimate "external
            # actor connects to entry point" pattern (e.g. tv_aws_users
            # -> aws_cloudfront_distribution.this).
            existing_targets_for_source = set(graphdict.get(source_node, []))
            kept_targets = []
            for target in value or []:
                target_name = next(iter(target)) if isinstance(target, dict) else target
                if target_name not in allowed:
                    warnings.append(
                        f"AI {key}: dropping unknown target '{target_name}'"
                        f" under '{source_node}'"
                    )
                    continue
                if key == "connect":
                    pair_is_existing_edge = target_name in existing_targets_for_source
                    pair_involves_new_actor = (
                        source_node in added_nodes or target_name in added_nodes
                    )
                    if not pair_is_existing_edge and not pair_involves_new_actor:
                        warnings.append(
                            f"AI connect: dropping label for non-existent edge "
                            f"'{source_node}' -> '{target_name}' "
                            f"(graphdict has no such connection)"
                        )
                        continue
                kept_targets.append(target)
            if kept_targets:
                kept[source_node] = kept_targets
        if kept:
            cleaned[key] = kept

    # remove: list of node names; keep only those that exist
    if annotations.get("remove"):
        kept_remove = []
        for node in annotations["remove"]:
            if not isinstance(node, str):
                continue
            # Allow wildcards (existing modify_nodes supports them)
            if "*" in node or node in valid_nodes:
                kept_remove.append(node)
            else:
                warnings.append(f"AI remove: dropping unknown node '{node}'")
        if kept_remove:
            cleaned["remove"] = kept_remove

    # flows: validate each step's resource (or "src -> tgt" edge form).
    # For edge-form steps the (source, target) pair must be an existing
    # edge in graphdict (or involve a node from `add`) — same rule as
    # connect entries — otherwise the badge has nothing to attach to.
    if isinstance(annotations.get("flows"), dict):
        kept_flows: Dict[str, Any] = {}
        for flow_name, flow_def in annotations["flows"].items():
            if not isinstance(flow_def, dict):
                continue
            steps = flow_def.get("steps") or []
            kept_steps = []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                resource = step.get("resource", "")
                if "->" in str(resource):
                    src, tgt = (s.strip() for s in resource.split("->", 1))
                    if src not in allowed or tgt not in allowed:
                        warnings.append(
                            f"AI flow '{flow_name}': dropping edge step "
                            f"with unknown endpoints '{resource}'"
                        )
                        continue
                    edge_exists = tgt in (graphdict.get(src) or [])
                    pair_involves_new_actor = src in added_nodes or tgt in added_nodes
                    if not edge_exists and not pair_involves_new_actor:
                        warnings.append(
                            f"AI flow '{flow_name}': dropping edge step "
                            f"'{resource}' (graphdict has no such connection)"
                        )
                        continue
                    kept_steps.append(step)
                elif resource in allowed:
                    kept_steps.append(step)
                else:
                    warnings.append(
                        f"AI flow '{flow_name}': dropping step with "
                        f"unknown resource '{resource}'"
                    )
            if kept_steps:
                new_flow = dict(flow_def)
                new_flow["steps"] = kept_steps
                kept_flows[flow_name] = new_flow
        if kept_flows:
            cleaned["flows"] = kept_flows

    return cleaned, warnings


# ---------------------------------------------------------------------------
# Public API: generate_ai_annotations
# ---------------------------------------------------------------------------


def _resolve_model_identifier(backend: str) -> str:
    """Best-effort identification of the model in use.

    For ollama we record the default chat model. For bedrock we record
    the proxy endpoint host because the actual model is server-side.
    The result lands in the ``generated_by`` block of the written
    annotation file so users can see what produced the output and
    reproduce results across runs.
    """
    if backend.lower() == "ollama":
        return "llama3"
    return "bedrock-proxy"


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count_section_entries(section: Any) -> int:
    """Best-effort count of how many "things" a section declares.

    For ``connect`` / ``disconnect``, this counts every (source, target)
    pair across all source nodes (not just the number of source nodes),
    so the summary line reflects what the LLM actually proposed rather
    than how many keys it grouped them under.

    For ``flows`` we count steps across all flows, not flow names, for
    the same reason.
    """
    if not section:
        return 0
    if isinstance(section, list):
        return len(section)
    if isinstance(section, dict):
        total = 0
        for value in section.values():
            if isinstance(value, list):
                total += len(value)
            elif isinstance(value, dict):
                # update / add: each attribute is one "entry"
                total += len(value) if value else 1
            else:
                total += 1
        return total
    return 1


def _summarize_validation(
    raw_parsed: Any,
    cleaned: Dict[str, Any],
) -> str:
    """Build a one-line accept/drop summary across every annotation section.

    The output is intended to land directly under the per-warning lines
    so a user who sees "diagram looks unchanged" can immediately tell
    whether the AI hallucinated most of its references vs. produced
    nothing useful in the first place.
    """
    # yaml.safe_load can return a plain string / list / None for malformed
    # responses (e.g. prose-only output, an empty payload). Treat anything
    # that isn't a mapping as "nothing usable" — the validator will have
    # already emitted a warning explaining why.
    if not isinstance(raw_parsed, dict):
        raw_parsed = {}
    if not isinstance(cleaned, dict):
        cleaned = {}
    parts: List[str] = []
    sections = ("connect", "disconnect", "update", "remove", "flows", "add")
    for name in sections:
        raw_total = _count_section_entries(raw_parsed.get(name))
        kept_total = _count_section_entries(cleaned.get(name))
        if raw_total == 0 and kept_total == 0:
            continue
        # For flows, also count steps inside kept flows because a flow
        # may survive with fewer steps than the LLM proposed.
        if name == "flows":
            raw_steps = sum(
                len((f or {}).get("steps") or [])
                for f in (raw_parsed.get("flows") or {}).values()
                if isinstance(f, dict)
            )
            kept_steps = sum(
                len((f or {}).get("steps") or [])
                for f in (cleaned.get("flows") or {}).values()
                if isinstance(f, dict)
            )
            parts.append(
                f"flows: {len(cleaned.get('flows') or {})}/"
                f"{len(raw_parsed.get('flows') or {})} kept "
                f"({kept_steps}/{raw_steps} steps)"
            )
            continue
        parts.append(f"{name}: {kept_total}/{raw_total} kept")
    if raw_parsed.get("title"):
        parts.append("title: applied" if cleaned.get("title") else "title: dropped")
    return "; ".join(parts) if parts else "nothing to apply"


def generate_ai_annotations(
    tfdata: Dict[str, Any],
    backend: str,
    source_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Generate ``terravision.ai.yml`` from the deterministic graphdict.

    NEVER touches ``tfdata['graphdict']``. The result is written to
    ``terravision.ai.yml`` in ``output_dir`` (default: cwd) and the
    in-memory dict is also returned for downstream merging.

    Behaviour contract:
      * Reads graphdict + a small project context block; sends them to
        the configured backend (ollama or bedrock); parses the YAML
        response; drops every reference to a non-existent resource;
        writes the result to ``terravision.ai.yml`` with a
        ``generated_by`` provenance block (backend, model, UTC
        timestamp) appended.
      * Falls back to non-AI rendering — returns ``None`` and emits a
        user-visible warning, but never raises — when the backend is
        unreachable (network error, refused, timeout), the response
        cannot be parsed, or nothing survives reference validation.
        The warning identifies the backend by name so the user knows
        what failed.
      * Never reads or writes the user-authored ``terravision.yml``.
        That file is owned by the human and is merged on top of the AI
        file at render time, with the user always winning on conflict.

    Args:
        tfdata: Terraform data dict — must contain ``graphdict``.
        backend: ``"ollama"`` or ``"bedrock"``.
        source_dir: Source directory used for README discovery.
        output_dir: Where to write ``terravision.ai.yml``. Defaults to cwd.
    """
    graphdict = tfdata.get("graphdict") or {}
    if not graphdict:
        click.echo(
            click.style(
                "  AI annotation skipped: empty graphdict.",
                fg="yellow",
            )
        )
        return None

    backend_lower = backend.lower()
    if backend_lower not in ("ollama", "bedrock"):
        click.echo(
            click.style(
                f"  AI annotation skipped: unknown backend '{backend}'.",
                fg="yellow",
            )
        )
        return None

    provider = get_primary_provider_or_default(tfdata)
    config = load_config(provider)

    context_block = _extract_context_block(tfdata, source_dir)
    # Build the two allow-lists shown directly to the LLM. The graphdict
    # is NOT included separately — inventory + edges already encode all
    # of its information, and the duplicate would only give the model a
    # third format to potentially copy from instead of the strict
    # allow-lists.
    inventory_block = "\n".join(sorted(graphdict.keys()))
    edge_lines: List[str] = []
    for src in sorted(graphdict.keys()):
        for tgt in graphdict[src] or []:
            edge_lines.append(f"{src} -> {tgt}")
    edges_block = "\n".join(edge_lines) if edge_lines else "(graph has no edges)"
    # Build the external actor identifier list dynamically from the
    # provider's AUTO_ANNOTATIONS config. This is the single source of
    # truth — adding or removing a tv_* entry in cloud_config_<provider>.py
    # automatically updates what the LLM is allowed to use.
    actors_block = _build_actors_block(config, provider)
    # Use plain replace, not str.format(), because the YAML schema example
    # baked into ANNOTATION_PROMPT contains literal "{}" tokens that
    # str.format() would misinterpret as positional placeholders.
    prompt = (
        ANNOTATION_PROMPT.replace("{inventory}", inventory_block)
        .replace("{edges}", edges_block)
        .replace("{actors}", actors_block)
        .replace("{context}", context_block)
    )

    click.echo(
        click.style(
            f"\nRequesting AI annotations from {backend_lower}..\n",
            fg="white",
            bold=True,
        )
    )

    raw_response = ""
    try:
        if backend_lower == "ollama":
            client = create_ollama_client(config.OLLAMA_HOST)
            raw_response = _stream_ollama_text(client, prompt)
        else:
            raw_response = _stream_bedrock_text(prompt, config.BEDROCK_API_ENDPOINT)
    except (
        requests.exceptions.RequestException,
        ConnectionError,
        ConnectionRefusedError,
        TimeoutError,
        OSError,
    ) as exc:
        click.echo(
            click.style(
                f"\n  WARNING: AI backend '{backend_lower}' unreachable: {exc}. "
                f"Falling back to non-AI rendering.",
                fg="yellow",
            )
        )
        return None
    except Exception as exc:  # noqa: BLE001 — never propagate to user
        click.echo(
            click.style(
                f"\n  WARNING: AI backend '{backend_lower}' raised {type(exc).__name__}: "
                f"{exc}. Falling back to non-AI rendering.",
                fg="yellow",
            )
        )
        return None

    payload = _extract_yaml_payload(raw_response)
    if not payload:
        click.echo(
            click.style(
                "\n  WARNING: AI backend returned an empty response. "
                "Falling back to non-AI rendering.",
                fg="yellow",
            )
        )
        return None

    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        click.echo(
            click.style(
                f"\n  WARNING: AI response was not valid YAML ({exc}). "
                f"Falling back to non-AI rendering.",
                fg="yellow",
            )
        )
        return None

    cleaned, warnings = _validate_against_graphdict(parsed or {}, graphdict)
    for w in warnings:
        click.echo(click.style(f"    - {w}", fg="yellow"))

    # One-line accept/drop summary so users can immediately tell how
    # much of the AI's output was hallucinated. Without this you have
    # to scroll through individual warnings to figure out why a
    # diagram "looks unchanged".
    summary = _summarize_validation(parsed or {}, cleaned)
    drop_color = "yellow" if warnings else "cyan"
    click.echo(
        click.style(
            f"\n  AI annotation summary: {summary}",
            fg=drop_color,
            bold=True,
        )
    )

    if not cleaned or set(cleaned.keys()) <= {"format"}:
        click.echo(
            click.style(
                "\n  WARNING: No usable AI annotations after validation. "
                "Falling back to non-AI rendering.",
                fg="yellow",
            )
        )
        return None

    cleaned.setdefault("format", "0.2")
    cleaned["generated_by"] = {
        "backend": backend_lower,
        "model": _resolve_model_identifier(backend_lower),
        "timestamp": _utc_timestamp(),
    }

    out_path = Path(output_dir or os.getcwd()) / "terravision.ai.yml"
    try:
        with open(out_path, "w") as fh:
            yaml.safe_dump(cleaned, fh, sort_keys=False, default_flow_style=False)
        click.echo(
            click.style(
                f"\n  Wrote AI annotations: {out_path}",
                fg="cyan",
                bold=True,
            )
        )
    except OSError as exc:
        click.echo(
            click.style(
                f"\n  WARNING: Could not write {out_path}: {exc}. "
                f"AI annotations will be applied in-memory only.",
                fg="yellow",
            )
        )

    return cleaned
