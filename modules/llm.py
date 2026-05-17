"""LLM/AI backend integration for TerraVision.

Generates a separate ``terravision.ai.yml`` annotation file from the
deterministic graphdict without ever modifying the graphdict itself.
The deterministic graph (graphdict, tfdata) is the source of truth and
must remain byte-identical whether or not the AI is invoked; the AI
output is a *supplementary* artifact that the renderer merges in at
draw time, with the user's hand-authored ``terravision.yml`` always
winning on conflict.

Three backends are supported:

  * ``ollama``  — local Ollama HTTP API. Server URL and model are
    configured per-provider via ``OLLAMA_HOST`` and ``OLLAMA_MODEL`` in
    ``modules/config/cloud_config_<provider>.py`` (defaults
    ``http://localhost:11434`` and ``llama3``). Air-gapped / private path.
  * ``bedrock`` — AWS Bedrock Converse streaming via ``boto3``,
    authenticated through the standard AWS credential chain (env vars,
    ``~/.aws/credentials``, IAM role, SSO). Region and model id are
    overridable via ``TV_BEDROCK_REGION`` and ``TV_BEDROCK_MODEL_ID``.
  * ``restapi`` — generic OpenAI-compatible ``/v1/chat/completions``
    endpoint with SSE streaming. Endpoint, bearer token, and model id
    are supplied via ``TV_RESTAPI_URL``, ``TV_RESTAPI_KEY``, and
    ``TV_RESTAPI_MODEL``. Works against OpenAI, Anthropic-via-proxy,
    LiteLLM, vLLM, LM Studio, OpenRouter, etc.
"""

import datetime as _dt
import json
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
# Backend defaults / env-var names
#
# These live as module constants so tests can monkeypatch them and so
# callers see the same source of truth for env-var spellings.
# ---------------------------------------------------------------------------

_DEFAULT_BEDROCK_REGION = "us-east-1"
_DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_ENV_BEDROCK_REGION = "TV_BEDROCK_REGION"
_ENV_BEDROCK_MODEL_ID = "TV_BEDROCK_MODEL_ID"

_ENV_RESTAPI_URL = "TV_RESTAPI_URL"
_ENV_RESTAPI_KEY = "TV_RESTAPI_KEY"
_ENV_RESTAPI_MODEL = "TV_RESTAPI_MODEL"


def _bedrock_region() -> str:
    return os.environ.get(_ENV_BEDROCK_REGION) or _DEFAULT_BEDROCK_REGION


def _bedrock_model_id() -> str:
    return os.environ.get(_ENV_BEDROCK_MODEL_ID) or _DEFAULT_BEDROCK_MODEL_ID


def _restapi_settings() -> Tuple[str, str, str]:
    """Return (url, api_key, model) from the environment.

    Raises a ``RuntimeError`` if any required value is missing — the
    restapi backend has no sensible default URL, so we fail loudly rather
    than guess.
    """
    url = os.environ.get(_ENV_RESTAPI_URL, "").strip()
    key = os.environ.get(_ENV_RESTAPI_KEY, "").strip()
    model = os.environ.get(_ENV_RESTAPI_MODEL, "").strip()
    missing = [
        name
        for name, value in (
            (_ENV_RESTAPI_URL, url),
            (_ENV_RESTAPI_KEY, key),
            (_ENV_RESTAPI_MODEL, model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "restapi backend requires environment variables: " + ", ".join(missing)
        )
    return url, key, model


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


def check_bedrock_credentials() -> None:
    """Verify AWS credentials are configured for the Bedrock backend.

    Calls ``sts:GetCallerIdentity`` — the cheapest, read-only,
    universally-available probe — to confirm boto3 has resolvable
    credentials and can reach AWS. We do NOT call Bedrock directly here
    because that would require Bedrock IAM permissions just to run
    preflight; users may have valid creds but no Bedrock access until
    the real call. STS keeps the preflight permissionless.
    """
    click.echo("  checking AWS credentials for Bedrock..")
    try:
        import boto3  # local import: pay the cost only on the bedrock path
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError as e:
        click.echo(
            click.style(
                "\n  ERROR: boto3 is required for the bedrock backend but is "
                f"not installed: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()

    region = _bedrock_region()
    model_id = _bedrock_model_id()
    try:
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        click.echo(
            f"  AWS credentials OK (account={identity.get('Account')}, region={region})"
        )
        click.echo(f"  Bedrock model: {model_id}")
    except NoCredentialsError:
        click.echo(
            click.style(
                "\n  ERROR: No AWS credentials found. Configure via env vars, "
                "~/.aws/credentials, IAM role, or SSO.",
                fg="red",
                bold=True,
            )
        )
        sys.exit()
    except (BotoCoreError, ClientError) as e:
        click.echo(
            click.style(
                f"\n  ERROR: Could not verify AWS credentials: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def check_restapi_endpoint() -> None:
    """Verify the OpenAI-compatible REST API endpoint is configured and reachable.

    Validates that the three required env vars are set, then performs a
    cheap ``GET`` against the URL's host (most OpenAI-compatible servers
    return 4xx on a bare GET to ``/v1/chat/completions``, which is fine
    — we just want TCP + TLS to work, not a real completion).
    """
    click.echo("  checking REST API endpoint..")
    try:
        url, _, model = _restapi_settings()
    except RuntimeError as e:
        click.echo(click.style(f"\n  ERROR: {e}", fg="red", bold=True))
        sys.exit()

    try:
        # A bare GET on a chat-completions URL is expected to return 4xx.
        # We accept any HTTP response as proof of reachability — we are
        # not authenticating here, only confirming the network path.
        response = requests.get(url, timeout=5)
        click.echo(
            f"  REST API reachable at: {url} (status={response.status_code}, model={model})"
        )
    except requests.exceptions.RequestException as e:
        click.echo(
            click.style(
                f"\n  ERROR: Cannot reach REST API endpoint at {url}: {e}",
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
You are to annotate an existing cloud architecture diagram represented in text. You will be given
TWO allow-lists below: a list of mostly Terraform resource names and a list of edges.
Your job is to produce a YAML annotation file that adds a TITLE,
short LABELS to existing edges, and optionally one or two external
ACTORS connected to entry-point resources. You MUST NOT redraw the
diagram or invent any name not in the allow-lists.

================================================================
ALLOW-LIST 1 — TERRAFORM RESOURCE NAMES
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
ENTRY POINT RULE — when you draw a new edge from an actor
================================================================
The `add` section is the ONLY exception to ALLOW-LIST 2. Any
other invented edge — actor or not — will be silently dropped, so
do not waste output on connections that are not in ALLOW-LIST 2.
Use the actor exception carefully:

  - Connect each external actor to AT MOST ONE existing resource:
    the FRONTMOST public-facing entry point in the request path.
    Do NOT add multiple actor→resource edges, even if several
    resources look "public".

  - Walk the architecture from outside in and stop at the first
    match present in ALLOW-LIST 1, in this priority order:

      1. DNS / domain service
      2. Content delivery network (CDN) / front door
      3. API gateway / GraphQL endpoint
      4. Public-facing load balancer
      5. None — if no public-facing entry point exists in the
         allow-list, do NOT add a user actor at all. A diagram
         with no user node is better than one with a misleading
         edge.

  - If a CDN sits in front of a load balancer, the actor connects
    to the CDN ONLY — the load balancer is behind the CDN and is
    not a direct user endpoint. The same principle applies to any
    "frontdoor → backdoor" chain: connect to the frontmost
    service, never anything further down the chain.

The principle is provider-agnostic: identify the role each
allow-listed resource plays (DNS / CDN / gateway / load balancer
/ internal) from its name and pick the topmost that exists. Do
not encode any single cloud's resource-type names into your
reasoning.

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
  <actor identifier copied from EXTERNAL ACTORS list above>:
    label: "Short human-readable description (e.g. End Users / Web Browsers)"
connect:
  <source name copied from ALLOW-LIST 1>:
    - <target name copied from ALLOW-LIST 1>: "Short verb-phrase label"
flows:                          # optional, omit if no clear request path
  user-request:
    description: "End-user request flow"
    steps:
      - resource: <actor identifier copied from EXTERNAL ACTORS list above>
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

REMEMBER THIS IMPORTANT INSTRUCTION: never invent a name not in
the list above. The most common ways models accidentally invent
names:

  - Writing the brand or marketing name of a service instead of
    the actual Terraform resource type from the allow-list.
  - Dropping ``module.`` prefixes, ``~N`` numbered-instance
    suffixes, or ``[N]`` index suffixes.
  - Replacing local names like ``.this`` or ``.main`` with a
    friendlier-sounding invented name.
  - Translating a name from one cloud provider's vocabulary to
    another.

If a resource you want to reference is not in ALLOW-LIST 1, do
not reference it — it is not part of this architecture and any
label you write referencing it will be silently dropped.

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
        # tv_aws_users.users → "users",
        # tv_aws_onprem.corporate_datacenter → "corporate datacenter"
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
# Backend streaming helpers (Ollama + Bedrock + REST API).
#
# Streaming is preserved across all three backends so users see
# incremental output for long generations.
#
#   * Ollama   — Python client streams parsed chunks; we concat .content
#   * Bedrock  — boto3 Converse API; demux EventStream events and pull
#                text from contentBlockDelta events. Auth is SigV4 via
#                the standard boto3 credential chain — no signing here.
#   * REST API — OpenAI-compatible /v1/chat/completions with SSE
#                streaming (`data: {...}\n\n` framing, `[DONE]` sentinel).
# ---------------------------------------------------------------------------


def _stream_ollama_text(
    client: ollama.Client,
    prompt: str,
    model: str,
) -> str:
    """Stream a chat completion from Ollama and return the full string.

    The model is resolved by the caller from the provider config
    (``OLLAMA_MODEL``) — there is no fallback default here so a
    misconfigured provider config fails loudly instead of silently
    requesting llama3.
    """
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


def _stream_bedrock_text(prompt: str) -> str:
    """Stream a chat completion from AWS Bedrock via the Converse API.

    Uses ``bedrock-runtime.converse_stream`` so the same code works
    across every Bedrock chat model (Claude, Llama, Nova, Mistral) by
    swapping ``TV_BEDROCK_MODEL_ID``. Authenticates through the standard
    boto3 credential chain — env vars, ``~/.aws/credentials``, IAM
    role, or SSO. Region defaults to ``us-east-1`` (override with
    ``TV_BEDROCK_REGION``).

    The streaming response is a sequence of typed events; we pull text
    from ``contentBlockDelta`` events and ignore framing events
    (``messageStart``, ``contentBlockStop``, ``messageStop``,
    ``metadata``). This is structurally different from a raw HTTP body
    stream and is why the old API-Gateway-style ``iter_content`` loop
    is not reusable here.
    """
    import boto3  # local import: avoid forcing boto3 onto ollama-only users

    client = boto3.client("bedrock-runtime", region_name=_bedrock_region())
    response = client.converse_stream(
        modelId=_bedrock_model_id(),
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 10000},
    )

    full_response = ""
    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            text = delta.get("text", "")
            if text:
                print(text, end="", flush=True)
                full_response += text
    return full_response


def _stream_restapi_text(prompt: str) -> str:
    """Stream a chat completion from any OpenAI-compatible endpoint.

    Sends a standard ``/v1/chat/completions`` request with
    ``stream: true`` and parses the Server-Sent Events response,
    pulling ``choices[0].delta.content`` from each chunk. Accepts the
    ``data: [DONE]`` sentinel as the terminator.

    Endpoint, bearer token, and model id come from
    ``TV_RESTAPI_URL`` / ``TV_RESTAPI_KEY`` / ``TV_RESTAPI_MODEL``.
    """
    url, api_key, model = _restapi_settings()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": 0,
        "max_tokens": 10000,
    }
    response = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream",
        },
        stream=True,
        timeout=300,
    )
    response.raise_for_status()

    full_response = ""
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        # SSE lines start with "data: "; ignore other field types
        # (event:, id:, retry:) — none of them carry token text.
        if not raw_line.startswith("data:"):
            continue
        data = raw_line[len("data:") :].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            # Malformed chunk; skip rather than abort the whole stream.
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content") or ""
        if content:
            print(content, end="", flush=True)
            full_response += content
    return full_response


# ---------------------------------------------------------------------------
# YAML extraction + validation
# ---------------------------------------------------------------------------

# Match an optional ```yaml fence so we tolerate models that wrap output.
_YAML_FENCE_RE = re.compile(r"```(?:yaml|yml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# Top-level keys we recognise in the annotation schema. Used both to
# locate the start of the payload (skipping prose preamble) and to
# detect / repair inconsistent top-level indentation in model output.
_TOP_LEVEL_KEYS = (
    "format:",
    "title:",
    "add:",
    "connect:",
    "disconnect:",
    "update:",
    "remove:",
    "flows:",
)


def _normalize_yaml_indentation(payload: str) -> str:
    """Repair inconsistent top-level indentation produced by some models.

    Some LLMs emit annotation YAML where top-level keys are at different
    indents — e.g. ``format:`` at column 0 but ``title:`` and ``add:`` at
    column 3 (the model behaves as if it's still inside a code block).
    ``yaml.safe_load`` rejects this with "expected <block end>, but
    found <block mapping start>".

    We detect the mismatch by scanning for top-level keys, and if they
    appear at differing columns we treat the minimum column as canonical
    and dedent each over-indented block (top-level key + its children)
    by the difference. Lines without enough leading whitespace to dedent
    safely are left untouched.

    No-op when indentation is already consistent — safe to call
    unconditionally on every payload.
    """
    if not payload:
        return payload
    lines = payload.splitlines()

    # Locate every top-level key and its column.
    key_positions: List[Tuple[int, int]] = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if any(stripped.startswith(k) for k in _TOP_LEVEL_KEYS):
            indent = len(line) - len(stripped)
            key_positions.append((i, indent))

    if not key_positions:
        return payload
    indents = {ind for _, ind in key_positions}
    if len(indents) <= 1:
        return payload  # Already consistent — nothing to do.

    canonical = min(indents)

    # Walk each block (top-level key → next top-level key) and dedent
    # over-indented blocks down to the canonical column.
    fixed = list(lines)
    for pos_idx, (line_idx, indent) in enumerate(key_positions):
        delta = indent - canonical
        if delta <= 0:
            continue
        end_idx = (
            key_positions[pos_idx + 1][0]
            if pos_idx + 1 < len(key_positions)
            else len(lines)
        )
        for j in range(line_idx, end_idx):
            line = fixed[j]
            if line.startswith(" " * delta):
                fixed[j] = line[delta:]
            # else: blank or under-indented → leave alone, can't safely
            # dedent without risking corrupting the structure.

    return "\n".join(fixed)


def _extract_yaml_payload(raw: str) -> str:
    """Strip code fences / leading prose so yaml.safe_load can parse it.

    Also normalises top-level indentation (see
    ``_normalize_yaml_indentation``) so payloads from models that emit
    inconsistent column alignment still parse.
    """
    if not raw:
        return ""
    fence = _YAML_FENCE_RE.search(raw)
    if fence:
        return _normalize_yaml_indentation(fence.group(1).strip())
    # Otherwise drop everything before the first `format:` or top-level key.
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(_TOP_LEVEL_KEYS):
            payload = "\n".join(lines[i:]).strip()
            return _normalize_yaml_indentation(payload)
    return _normalize_yaml_indentation(raw.strip())


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


def _resolve_model_identifier(backend: str, ollama_model: Optional[str] = None) -> str:
    """Best-effort identification of the model in use.

    Used in the ``generated_by`` provenance block so users can see what
    produced the output and reproduce results across runs.

    For ``ollama`` the caller passes the resolved ``OLLAMA_MODEL`` from
    the provider config. For ``bedrock`` and ``restapi`` the model is
    pulled from the same env vars the streamers read, so provenance
    matches the request.
    """
    backend_lower = backend.lower()
    if backend_lower == "ollama":
        return ollama_model or "unknown"
    if backend_lower == "bedrock":
        return _bedrock_model_id()
    if backend_lower == "restapi":
        # Don't crash provenance recording if env vars are missing — the
        # caller will already have failed elsewhere.
        return os.environ.get(_ENV_RESTAPI_MODEL, "unknown")
    return backend_lower


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
    if backend_lower not in ("ollama", "bedrock", "restapi"):
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

    # Resolve provider-config-driven Ollama settings up-front so the same
    # value flows into the streamer and the provenance block.
    ollama_model = getattr(config, "OLLAMA_MODEL", "llama3")

    raw_response = ""
    try:
        if backend_lower == "ollama":
            client = create_ollama_client(config.OLLAMA_HOST)
            raw_response = _stream_ollama_text(client, prompt, ollama_model)
        elif backend_lower == "bedrock":
            raw_response = _stream_bedrock_text(prompt)
        else:  # restapi
            raw_response = _stream_restapi_text(prompt)
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
        # Catches botocore exceptions (BotoCoreError / ClientError /
        # NoCredentialsError) for the bedrock path, RuntimeError from
        # missing restapi env vars, malformed JSON in SSE chunks, etc.
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
        "model": _resolve_model_identifier(backend_lower, ollama_model),
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
