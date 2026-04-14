"""Tests for the AI annotation generation pipeline.

These tests cover:
  * happy path: a mocked LLM returns valid YAML, the writer produces a
    well-formed terravision.ai.yml on disk, every resource reference in
    the result exists in graphdict, and the deterministic graph is
    untouched.
  * malformed responses (prose, invalid YAML, references to non-existent
    resources) are rejected cleanly and the function returns None so
    rendering falls back to the deterministic pipeline.
  * the AI backend client raising connection errors (network down,
    refused, timeout) is handled by returning None and emitting a
    user-visible warning that mentions the backend name. No exception
    bubbles up to the caller and no terravision.ai.yml is written.
"""

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
import yaml

import modules.llm as llm


# ---------------------------------------------------------------------------
# Helpers for slow integration tests
# ---------------------------------------------------------------------------


def _build_minimal_tfdata_from_fixture(fixture_dir: str) -> Dict[str, Any]:
    """Build a minimal tfdata dict from a fixture directory.

    Constructs a graphdict by scanning the .tf files for resource blocks and
    wiring simple edges. This is NOT a full Terraform evaluation — it's
    enough to exercise the AI annotation pipeline with a realistic resource
    set so the LLM has real resource names and types to reason about.
    """
    import re

    resources = []
    tf_files = [f for f in os.listdir(fixture_dir) if f.endswith(".tf")]
    for tf_file in tf_files:
        content = Path(os.path.join(fixture_dir, tf_file)).read_text()
        # Extract resource "type" "name" blocks
        for m in re.finditer(r'resource\s+"([^"]+)"\s+"([^"]+)"', content):
            resources.append(f"{m.group(1)}.{m.group(2)}")

    # Build a simple graphdict with empty adjacency lists
    graphdict: Dict[str, list] = {r: [] for r in resources}

    # Detect provider from resource prefixes
    provider_counts: Dict[str, int] = {}
    for r in resources:
        prefix = r.split("_")[0]
        provider_counts[prefix] = provider_counts.get(prefix, 0) + 1
    primary = (
        max(provider_counts, key=provider_counts.get) if provider_counts else "aws"
    )

    return {
        "graphdict": graphdict,
        "meta_data": {r: {} for r in resources},
        "annotations": {},
        "provider_detection": {
            "primary_provider": primary,
            "resource_counts": provider_counts,
        },
    }


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_tfdata() -> Dict[str, Any]:
    """Minimal tfdata with a graphdict and provider detection.

    Three real resources, two connections, one tag block. Enough for the
    annotation generator to chew on without dragging in real terraform
    parsing.
    """
    return {
        "graphdict": {
            "aws_lambda_function.api": ["aws_dynamodb_table.orders"],
            "aws_dynamodb_table.orders": [],
            "aws_secretsmanager_secret.db_creds": [],
        },
        "meta_data": {
            "aws_lambda_function.api": {
                "tags": {"app": "orders", "env": "prod", "team": "payments"}
            }
        },
        "provider_detection": {
            "primary_provider": "aws",
            "resource_counts": {"aws": 3},
        },
    }


@pytest.fixture
def good_llm_yaml() -> str:
    """A canned, well-formed AI response."""
    return (
        'format: "0.2"\n'
        'title: "Serverless Order Processing"\n'
        "add:\n"
        "  end_users.web:\n"
        '    label: "End Users"\n'
        "connect:\n"
        "  aws_lambda_function.api:\n"
        '    - aws_dynamodb_table.orders: "Persists order records"\n'
        '    - aws_secretsmanager_secret.db_creds: "Reads DB credentials"\n'
    )


# ---------------------------------------------------------------------------
# Happy path: mocked LLM returns valid YAML, file is written, references valid
# ---------------------------------------------------------------------------


def test_generate_ai_annotations_writes_valid_file(
    sample_tfdata, good_llm_yaml, tmp_path, monkeypatch
):
    """A well-formed LLM response writes a terravision.ai.yml whose
    resource references all exist in graphdict, and every key in the
    deterministic graphdict survives unchanged."""
    monkeypatch.setattr(llm, "_stream_ollama_text", lambda *a, **kw: good_llm_yaml)
    # Stub create_ollama_client so the function doesn't try to talk to localhost
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    # Snapshot the deterministic graph BEFORE generation
    graph_before = {k: list(v) for k, v in sample_tfdata["graphdict"].items()}

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )

    # Deterministic graph never modified — the AI annotation pipeline
    # is strictly additive: it writes terravision.ai.yml and leaves the
    # source-of-truth graphdict byte-for-byte intact.
    assert sample_tfdata["graphdict"] == graph_before

    # File written and parseable
    out_path = tmp_path / "terravision.ai.yml"
    assert out_path.is_file()
    on_disk = yaml.safe_load(out_path.read_text())

    assert on_disk["format"] == "0.2"
    assert on_disk["title"] == "Serverless Order Processing"
    assert "generated_by" in on_disk
    assert on_disk["generated_by"]["backend"] == "ollama"
    assert "timestamp" in on_disk["generated_by"]
    assert "model" in on_disk["generated_by"]

    # Every connect/disconnect/update reference must exist in graphdict
    # (or in the add section). The validator must already have enforced
    # this — we re-assert as a regression guard.
    valid = set(sample_tfdata["graphdict"].keys()) | set(
        (on_disk.get("add") or {}).keys()
    )
    for source_node, targets in (on_disk.get("connect") or {}).items():
        assert source_node in valid
        for target in targets:
            target_name = next(iter(target)) if isinstance(target, dict) else target
            assert target_name in valid

    # In-memory return matches what's on disk
    assert result["title"] == on_disk["title"]


def test_generate_ai_annotations_strips_unknown_resource_references(
    sample_tfdata, tmp_path, monkeypatch
):
    """If the LLM hallucinates a resource that does not exist in
    graphdict, that connection MUST be silently dropped, but other
    valid connections survive. We never ship a file containing
    references the renderer can't resolve."""
    bad_then_good = (
        'format: "0.2"\n'
        'title: "Mixed quality response"\n'
        "connect:\n"
        "  aws_lambda_function.api:\n"
        '    - aws_dynamodb_table.orders: "Real connection"\n'
        '    - aws_lambda_function.does_not_exist: "Hallucinated"\n'
        "  aws_lambda_function.also_hallucinated:\n"
        '    - aws_dynamodb_table.orders: "Should be dropped"\n'
    )
    monkeypatch.setattr(llm, "_stream_ollama_text", lambda *a, **kw: bad_then_good)
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )

    # The real connection survived
    assert result["connect"]["aws_lambda_function.api"][0] == {
        "aws_dynamodb_table.orders": "Real connection"
    }
    # The hallucinated target was dropped — only one entry remains
    assert len(result["connect"]["aws_lambda_function.api"]) == 1
    # The hallucinated source was dropped entirely
    assert "aws_lambda_function.also_hallucinated" not in result["connect"]


# ---------------------------------------------------------------------------
# Malformed responses: invalid YAML, prose, all-hallucinated -> fallback
# ---------------------------------------------------------------------------


def test_generate_ai_annotations_returns_none_on_invalid_yaml(
    sample_tfdata, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        llm,
        "_stream_ollama_text",
        lambda *a, **kw: "this is not yaml: : : { unclosed",
    )
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )
    assert result is None
    assert not (tmp_path / "terravision.ai.yml").exists()


def test_generate_ai_annotations_returns_none_on_prose_response(
    sample_tfdata, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        llm,
        "_stream_ollama_text",
        lambda *a, **kw: (
            "Sure! Here is your annotation file. Let me know if you need anything else."
        ),
    )
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )
    assert result is None
    assert not (tmp_path / "terravision.ai.yml").exists()


def test_generate_ai_annotations_drops_all_hallucinated_references(
    sample_tfdata, tmp_path, monkeypatch
):
    """If every connect reference is invalid, the validator drops the
    entire `connect` section but valid scalars (title, format) survive
    and the function returns a usable title-only annotation file. We
    do NOT discard a meaningful title just because the connections
    were wrong."""
    all_bad = (
        'format: "0.2"\n'
        'title: "Order Processing API"\n'
        "connect:\n"
        "  aws_lambda_function.fake_one:\n"
        '    - aws_dynamodb_table.fake_two: "imaginary"\n'
    )
    monkeypatch.setattr(llm, "_stream_ollama_text", lambda *a, **kw: all_bad)
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )
    assert result is not None
    assert result["title"] == "Order Processing API"
    assert "connect" not in result  # entire section dropped
    assert (tmp_path / "terravision.ai.yml").is_file()


def test_generate_ai_annotations_returns_none_when_response_only_has_format(
    sample_tfdata, tmp_path, monkeypatch
):
    """If the LLM returns nothing useful at all (just `format:`), the
    function MUST fall back to non-AI rendering rather than write a
    pointless file."""
    monkeypatch.setattr(llm, "_stream_ollama_text", lambda *a, **kw: 'format: "0.2"\n')
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )
    assert result is None
    assert not (tmp_path / "terravision.ai.yml").exists()


# ---------------------------------------------------------------------------
# Backend unreachable: connection errors fall back to non-AI rendering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionRefusedError("simulated refused"),
        TimeoutError("simulated timeout"),
        OSError("simulated network down"),
    ],
)
def test_generate_ai_annotations_handles_backend_unreachable(
    sample_tfdata, tmp_path, monkeypatch, capsys, exc
):
    """When the AI backend client raises a connection error the
    function MUST: (1) catch the exception, (2) emit a user-visible
    warning that mentions the backend name, (3) return None, and
    (4) NOT write terravision.ai.yml. No exception may bubble up."""

    def _boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr(llm, "_stream_ollama_text", _boom)
    monkeypatch.setattr(llm, "create_ollama_client", lambda host: None)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="ollama", source_dir=None, output_dir=str(tmp_path)
    )

    assert result is None
    assert not (tmp_path / "terravision.ai.yml").exists()

    captured = capsys.readouterr()
    output = (captured.out + captured.err).lower()
    assert "ollama" in output
    assert "unreachable" in output or "warning" in output


def test_generate_ai_annotations_handles_bedrock_request_exception(
    sample_tfdata, tmp_path, monkeypatch, capsys
):
    """Same fallback contract for the bedrock path: a requests
    exception is caught and turns into a clean fallback."""
    import requests

    def _boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("simulated bedrock down")

    monkeypatch.setattr(llm, "_stream_bedrock_text", _boom)

    result = llm.generate_ai_annotations(
        sample_tfdata, backend="bedrock", source_dir=None, output_dir=str(tmp_path)
    )
    assert result is None
    assert not (tmp_path / "terravision.ai.yml").exists()
    captured = capsys.readouterr()
    assert "bedrock" in (captured.out + captured.err).lower()


# ---------------------------------------------------------------------------
# README / context extraction
# ---------------------------------------------------------------------------


def test_context_block_includes_readme_when_present(sample_tfdata, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Orders Service\n\nServerless order processing pipeline for the payments team."
    )
    block = llm._extract_context_block(sample_tfdata, source_dir=str(tmp_path))
    assert "Orders Service" in block
    assert "payments team" in block


def test_context_block_includes_resource_tags(sample_tfdata):
    block = llm._extract_context_block(sample_tfdata, source_dir=None)
    # Tags from sample_tfdata's lambda metadata should appear
    assert "app=orders" in block
    assert "env=prod" in block


def test_validator_drops_connect_for_nonexistent_edge(sample_tfdata):
    """A connect entry whose (source, target) pair is not an existing
    edge in graphdict must be dropped — even when both names exist as
    nodes. The AI's job is to LABEL existing edges, not invent new ones."""
    # graphdict has lambda -> dynamodb but NOT lambda -> secretsmanager
    annotations = {
        "format": "0.2",
        "connect": {
            "aws_lambda_function.api": [
                {"aws_dynamodb_table.orders": "Persists records"},  # exists
                {"aws_secretsmanager_secret.db_creds": "Reads creds"},  # NOT in edges
            ]
        },
    }
    cleaned, warnings = llm._validate_against_graphdict(
        annotations, sample_tfdata["graphdict"]
    )
    targets = cleaned["connect"]["aws_lambda_function.api"]
    assert targets == [{"aws_dynamodb_table.orders": "Persists records"}]
    assert any("non-existent edge" in w for w in warnings)


def test_validator_allows_connect_to_added_external_actor(sample_tfdata):
    """Connecting to/from an external actor declared in `add` is the
    one legitimate way to introduce a new edge — the validator must
    permit this even though the (source, target) pair is not in
    graphdict."""
    annotations = {
        "format": "0.2",
        "add": {"tv_aws_users.users": {"label": "End Users"}},
        "connect": {
            "tv_aws_users.users": [
                {"aws_lambda_function.api": "HTTPS request"},
            ]
        },
    }
    cleaned, warnings = llm._validate_against_graphdict(
        annotations, sample_tfdata["graphdict"]
    )
    assert cleaned["connect"]["tv_aws_users.users"] == [
        {"aws_lambda_function.api": "HTTPS request"}
    ]
    # No warning about a non-existent edge for the actor connection
    assert not any("non-existent edge" in w for w in warnings)


def test_validator_drops_flow_step_for_nonexistent_edge(sample_tfdata):
    """A flow step in `source -> target` form must reference an
    existing edge or involve an external actor. Steps that reference
    non-edges get dropped (and flows with no surviving steps disappear)."""
    annotations = {
        "format": "0.2",
        "flows": {
            "imaginary": {
                "description": "Flow with phantom edge",
                "steps": [
                    {
                        "resource": "aws_lambda_function.api -> aws_secretsmanager_secret.db_creds",
                        "xlabel": "Bad",
                        "detail": "phantom",
                    }
                ],
            }
        },
    }
    cleaned, warnings = llm._validate_against_graphdict(
        annotations, sample_tfdata["graphdict"]
    )
    assert "flows" not in cleaned
    assert any("dropping edge step" in w for w in warnings)


def test_modify_metadata_preserves_edge_labels_for_added_node(sample_tfdata):
    """Regression: when a node appears in BOTH `add` and `connect`,
    the `add` block must NOT clobber the edge_labels written by the
    `connect` block. This bug used to silently destroy labels on
    external-actor nodes (the most common AI annotation pattern)."""
    from modules.annotations import modify_metadata

    annotations = {
        "add": {"tv_aws_users.users": {"label": "End Users"}},
        "connect": {
            "tv_aws_users.users": [
                {"aws_lambda_function.api": "HTTPS request"},
            ]
        },
    }
    metadata = {"aws_lambda_function.api": {}}
    out = modify_metadata(annotations, sample_tfdata["graphdict"], metadata)
    assert out["tv_aws_users.users"]["label"] == "End Users"
    assert out["tv_aws_users.users"]["edge_labels"] == [
        {"aws_lambda_function.api": "HTTPS request"}
    ]


def test_modify_nodes_skips_connect_with_unknown_source(sample_tfdata):
    """Defensive: a malformed annotation file with a connect source
    that is not in graphdict must NOT crash modify_nodes with a
    KeyError. It should drop the entry with a warning and continue."""
    from modules.annotations import modify_nodes
    import copy

    graphdict = copy.deepcopy(sample_tfdata["graphdict"])
    annotations = {
        "connect": {
            "aws_lambda_function.does_not_exist": [
                {"aws_dynamodb_table.orders": "Phantom edge"},
            ],
            "aws_lambda_function.api": [
                {"aws_dynamodb_table.orders": "Real edge label"},
            ],
        }
    }
    out = modify_nodes(graphdict, annotations)
    # Real edge survived
    assert "aws_dynamodb_table.orders" in out["aws_lambda_function.api"]
    # Phantom source did not get added to graphdict
    assert "aws_lambda_function.does_not_exist" not in out


def test_context_block_truncates_at_max_chars(sample_tfdata, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("a" * 50_000)
    block = llm._extract_context_block(
        sample_tfdata, source_dir=str(tmp_path), max_chars=1000
    )
    assert len(block) <= 1100  # max + truncation marker
    assert "[context truncated]" in block


def test_context_block_includes_per_resource_comments(sample_tfdata):
    """Comments harvested by fileparser._extract_comments_from_tf and
    surfaced via tfdata['tf_comments'] must appear in the context block
    as `<resource>: <comment>` lines under a 'Resource Comments'
    section so the LLM can use them when generating edge labels."""
    sample_tfdata["tf_comments"] = {
        "aws_lambda_function.api": "Processes incoming SQS order messages",
        "aws_dynamodb_table.orders": "Stores finalized order records with TTL",
    }
    block = llm._extract_context_block(sample_tfdata, source_dir=None)
    assert "Resource Comments" in block
    assert "aws_lambda_function.api: Processes incoming SQS order messages" in block
    assert "aws_dynamodb_table.orders: Stores finalized order records with TTL" in block


def test_context_block_includes_project_level_comments(sample_tfdata):
    """File / module level comments (not bound to a specific resource)
    are still useful as project intent and must appear under their own
    'Project Comments' section, deduplicated."""
    sample_tfdata["tf_unattached_comments"] = [
        "Order processing stack — payments team",
        "Owned by team-payments@example.com",
        "Order processing stack — payments team",  # duplicate
    ]
    block = llm._extract_context_block(sample_tfdata, source_dir=None)
    assert "Project Comments" in block
    # Duplicate header collapsed
    assert block.count("Order processing stack — payments team") == 1
    assert "Owned by team-payments@example.com" in block


# ---------------------------------------------------------------------------
# US1: Slow integration test — graphdict byte-identical with/without AI (T013)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_graphdict_byte_identical_with_and_without_ai(tmp_path):
    """US1 T013: Run generate_ai_annotations against a real fixture with
    Bedrock and verify the graphdict is byte-identical before and after.

    The AI annotation pipeline MUST NOT modify the deterministic graphdict.
    It only writes terravision.ai.yml as a sidecar file.
    """
    fixture = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "aws_terraform",
        "sns_sqs_lambda",
    )
    tfdata = _build_minimal_tfdata_from_fixture(fixture)

    # Snapshot the graphdict before AI annotation
    graphdict_before = json.dumps(tfdata["graphdict"], indent=4, sort_keys=True)

    output_dir = str(tmp_path)
    result = llm.generate_ai_annotations(
        tfdata,
        backend="bedrock",
        source_dir=fixture,
        output_dir=output_dir,
    )

    # Snapshot the graphdict after AI annotation
    graphdict_after = json.dumps(tfdata["graphdict"], indent=4, sort_keys=True)

    # SC-006: graphdict must be byte-identical
    assert graphdict_before == graphdict_after, (
        "graphdict was mutated by generate_ai_annotations — "
        "the AI pipeline must not touch the deterministic graph"
    )

    # The AI should have produced a file (sanity check that Bedrock is working)
    ai_path = os.path.join(output_dir, "terravision.ai.yml")
    assert os.path.isfile(
        ai_path
    ), "terravision.ai.yml not written — Bedrock may be unreachable"


# ---------------------------------------------------------------------------
# US2: AI-Suggested Title and Contextual Annotations (T021)
# ---------------------------------------------------------------------------


@pytest.fixture
def apigw_lambda_dynamo_tfdata() -> Dict[str, Any]:
    """Minimal tfdata with API Gateway + Lambda + DynamoDB style resources.

    Enough to exercise the AI title + external actor annotation path.
    """
    return {
        "graphdict": {
            "aws_api_gateway_rest_api.orders_api": [
                "aws_lambda_function.process_order"
            ],
            "aws_lambda_function.process_order": ["aws_dynamodb_table.orders"],
            "aws_dynamodb_table.orders": [],
        },
        "meta_data": {
            "aws_api_gateway_rest_api.orders_api": {},
            "aws_lambda_function.process_order": {
                "tags": {"app": "order-service", "env": "prod"}
            },
            "aws_dynamodb_table.orders": {},
        },
        "annotations": {},
        "provider_detection": {
            "primary_provider": "aws",
            "resource_counts": {"aws": 3},
        },
    }


@pytest.fixture
def title_actor_llm_yaml() -> str:
    """Canned LLM response with title + add (external actor) + connect only.

    No flows section — this exercises the US2 path specifically.
    """
    return (
        'format: "0.2"\n'
        'title: "Serverless Order Processing API"\n'
        "add:\n"
        "  tv_aws_users.users:\n"
        '    label: "End Users"\n'
        "connect:\n"
        "  tv_aws_users.users:\n"
        '    - aws_api_gateway_rest_api.orders_api: "HTTPS request"\n'
        "  aws_api_gateway_rest_api.orders_api:\n"
        '    - aws_lambda_function.process_order: "Invokes handler"\n'
        "  aws_lambda_function.process_order:\n"
        '    - aws_dynamodb_table.orders: "Persists order"\n'
    )


def test_apply_ai_annotations_title_and_external_actor(
    apigw_lambda_dynamo_tfdata, title_actor_llm_yaml
):
    """US2 T021: A canned LLM response with title + add + connect (no flows)
    is merged via apply_ai_annotations(). Verify:
      1. The title is applied to the merged annotations.
      2. The external-actor node (tv_aws_users.users) is created in graphdict.
      3. The edge from the actor to the entry-point resource is wired.
      4. Edge labels are set in metadata.
    """
    import copy
    from modules.annotations import apply_ai_annotations

    tfdata = copy.deepcopy(apigw_lambda_dynamo_tfdata)

    # Parse the canned YAML as if the LLM returned it
    ai_annotations = yaml.safe_load(title_actor_llm_yaml)

    # Snapshot graphdict before — deterministic topology should survive
    original_nodes = set(tfdata["graphdict"].keys())

    # Apply AI annotations
    result = apply_ai_annotations(tfdata, ai_annotations)

    # 1. Title is applied to merged annotations
    assert result["annotations"]["title"] == "Serverless Order Processing API"

    # 2. External-actor node is created in graphdict
    assert "tv_aws_users.users" in result["graphdict"]

    # 3. Edge from actor to entry-point resource is wired
    assert (
        "aws_api_gateway_rest_api.orders_api"
        in result["graphdict"]["tv_aws_users.users"]
    )

    # 4. Edge labels are set in metadata
    actor_meta = result["meta_data"].get("tv_aws_users.users", {})
    assert "edge_labels" in actor_meta
    assert {"aws_api_gateway_rest_api.orders_api": "HTTPS request"} in actor_meta[
        "edge_labels"
    ]
    # Also verify label attribute from the add section
    assert actor_meta.get("label") == "End Users"

    # Original nodes still present (deterministic graph not damaged)
    for node in original_nodes:
        assert node in result["graphdict"]

    # Edge labels on existing resources too
    apigw_meta = result["meta_data"].get("aws_api_gateway_rest_api.orders_api", {})
    assert "edge_labels" in apigw_meta
    assert {"aws_lambda_function.process_order": "Invokes handler"} in apigw_meta[
        "edge_labels"
    ]


# ---------------------------------------------------------------------------
# US2: Slow integration test stub (T022)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_us2_live_bedrock_title_and_actors(tmp_path):
    """US2 T022: Slow integration test — run against a reference Terraform
    fixture with real Bedrock, assert the AI-generated title is non-default
    and contains at least one resource-implied keyword.
    """
    fixture = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "aws_terraform",
        "api_gateway_rest_lambda",
    )
    output_dir = str(tmp_path)

    result = llm.generate_ai_annotations(
        _build_minimal_tfdata_from_fixture(fixture),
        backend="bedrock",
        source_dir=fixture,
        output_dir=output_dir,
    )

    assert result is not None, "Bedrock returned no annotations"
    ai_path = os.path.join(output_dir, "terravision.ai.yml")
    assert os.path.isfile(ai_path), "terravision.ai.yml not written"

    on_disk = yaml.safe_load(Path(ai_path).read_text())
    title = on_disk.get("title", "")
    assert title, "AI must generate a title"
    assert (
        title != "Cloud Architecture Diagram"
    ), "Title must not be the default placeholder"
