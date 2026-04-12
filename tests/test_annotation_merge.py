"""Tests for the terravision.ai.yml + terravision.yml merge precedence rules.

Verifies that when AI-generated annotations and user-authored annotations
both exist, the user file always wins on direct conflicts; that lists
(add, remove, connect targets) are unioned correctly; that flows are
replaced at the flow-name level rather than per-step; and that legacy
single-file annotation YAMLs continue to work alongside the new
two-file model.
"""

from modules.annotations import merge_annotations


def test_merge_empty_sources_returns_empty_dict():
    assert merge_annotations() == {}
    assert merge_annotations(None, None, None) == {}
    assert merge_annotations({}, {}, {}) == {}


def test_user_title_wins_over_ai_title():
    ai = {"title": "AI Generated"}
    user = {"title": "User Override"}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert merged["title"] == "User Override"


def test_cli_title_wins_over_user_and_ai():
    ai = {"title": "AI"}
    user = {"title": "User"}
    cli = {"title": "CLI"}
    merged = merge_annotations(
        ai_annotations=ai, user_annotations=user, cli_annotations=cli
    )
    assert merged["title"] == "CLI"


def test_only_ai_title_when_user_has_none():
    ai = {"title": "AI Generated"}
    user = {}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert merged["title"] == "AI Generated"


def test_add_dict_merge_user_wins_per_attribute():
    ai = {"add": {"external_api.payment": {"endpoint": "https://ai.example.com"}}}
    user = {"add": {"external_api.payment": {"endpoint": "https://user.example.com"}}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert (
        merged["add"]["external_api.payment"]["endpoint"] == "https://user.example.com"
    )


def test_add_union_across_sources():
    ai = {"add": {"node.a": {}}}
    user = {"add": {"node.b": {}}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert set(merged["add"].keys()) == {"node.a", "node.b"}


def test_add_tolerates_list_of_strings():
    """data-model.md documents add as List[str]; existing code uses dict.
    The merger MUST accept both shapes from either source."""
    ai = {"add": ["external.thing"]}
    user = {"add": {"other.thing": {"k": "v"}}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert "external.thing" in merged["add"]
    assert merged["add"]["other.thing"] == {"k": "v"}


def test_remove_list_union_dedupes():
    ai = {"remove": ["aws_iam_role.role_a", "aws_iam_role.role_b"]}
    user = {"remove": ["aws_iam_role.role_b", "aws_iam_role.role_c"]}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert merged["remove"] == [
        "aws_iam_role.role_a",
        "aws_iam_role.role_b",
        "aws_iam_role.role_c",
    ]


def test_connect_user_label_wins_on_same_target():
    ai = {
        "connect": {
            "aws_lambda.api": [{"aws_dynamodb.t": "ai writes data"}],
        }
    }
    user = {
        "connect": {
            "aws_lambda.api": [{"aws_dynamodb.t": "Persists order records"}],
        }
    }
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    targets = merged["connect"]["aws_lambda.api"]
    assert len(targets) == 1
    assert targets[0] == {"aws_dynamodb.t": "Persists order records"}


def test_connect_targets_union():
    ai = {"connect": {"aws_lambda.api": [{"aws_dynamodb.t": "ai label"}]}}
    user = {"connect": {"aws_lambda.api": [{"aws_s3.bucket": "user label"}]}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    targets = merged["connect"]["aws_lambda.api"]
    assert {"aws_dynamodb.t": "ai label"} in targets
    assert {"aws_s3.bucket": "user label"} in targets


def test_connect_label_preserved_when_higher_source_uses_bare_string():
    """If AI provides {target: label} and user provides bare 'target',
    the AI label MUST be preserved (user labels never disappear, but
    user also doesn't accidentally erase a label by omission)."""
    ai = {"connect": {"aws_lambda.api": [{"aws_dynamodb.t": "ai label"}]}}
    user = {"connect": {"aws_lambda.api": ["aws_dynamodb.t"]}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    targets = merged["connect"]["aws_lambda.api"]
    assert targets == [{"aws_dynamodb.t": "ai label"}]


def test_disconnect_list_union():
    ai = {"disconnect": {"aws_log_group.l": ["aws_lambda.a"]}}
    user = {"disconnect": {"aws_log_group.l": ["aws_lambda.b"]}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert set(merged["disconnect"]["aws_log_group.l"]) == {
        "aws_lambda.a",
        "aws_lambda.b",
    }


def test_update_per_attribute_user_wins():
    ai = {"update": {"aws_s3.bucket": {"icon": "ai-icon", "label": "AI label"}}}
    user = {"update": {"aws_s3.bucket": {"icon": "user-icon"}}}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    # user icon wins, AI label survives because user did not set it
    assert merged["update"]["aws_s3.bucket"]["icon"] == "user-icon"
    assert merged["update"]["aws_s3.bucket"]["label"] == "AI label"


def test_flows_user_replaces_entire_flow_with_same_name():
    """Flow merge is at the flow-name level, NOT per step. If user
    defines auth-flow it completely replaces the AI's auth-flow, even
    if the AI had more steps."""
    ai = {
        "flows": {
            "auth-flow": {
                "description": "AI version",
                "steps": [
                    {"resource": "a", "xlabel": "1", "detail": "ai step 1"},
                    {"resource": "b", "xlabel": "2", "detail": "ai step 2"},
                    {"resource": "c", "xlabel": "3", "detail": "ai step 3"},
                ],
            },
            "data-flow": {
                "description": "AI data ingestion",
                "steps": [{"resource": "x", "xlabel": "1", "detail": "ai data"}],
            },
        }
    }
    user = {
        "flows": {
            "auth-flow": {
                "description": "User version",
                "steps": [
                    {"resource": "u1", "xlabel": "1", "detail": "user step 1"},
                ],
            }
        }
    }
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    # auth-flow fully replaced
    assert merged["flows"]["auth-flow"]["description"] == "User version"
    assert len(merged["flows"]["auth-flow"]["steps"]) == 1
    assert merged["flows"]["auth-flow"]["steps"][0]["resource"] == "u1"
    # data-flow untouched
    assert merged["flows"]["data-flow"]["description"] == "AI data ingestion"


def test_legacy_0_1_file_merges_cleanly_without_flows():
    """A legacy format 0.1 file with no flows section should merge with
    a 0.2 AI file without errors and the flows from the AI file should
    survive."""
    ai = {
        "format": "0.2",
        "flows": {"f1": {"description": "AI flow", "steps": []}},
        "title": "AI title",
    }
    user = {
        "format": "0.1",
        "title": "User title",
        "connect": {"aws_lambda.x": ["aws_s3.y"]},
    }
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert merged["title"] == "User title"
    assert merged["flows"]["f1"]["description"] == "AI flow"
    assert merged["connect"]["aws_lambda.x"] == ["aws_s3.y"]


def test_generated_by_metadata_surfaced_only_from_ai_file():
    ai = {
        "generated_by": {
            "backend": "ollama",
            "model": "llama3:latest",
            "timestamp": "2026-04-11T12:00:00Z",
        },
        "title": "AI",
    }
    user = {"title": "User"}
    merged = merge_annotations(ai_annotations=ai, user_annotations=user)
    assert merged["generated_by"]["backend"] == "ollama"
    # user file generated_by is ignored even if present (it shouldn't be)
    user_with_meta = {"generated_by": {"backend": "should-be-ignored"}}
    merged2 = merge_annotations(user_annotations=user_with_meta)
    assert "generated_by" not in merged2


def test_unsupported_format_warns_but_does_not_crash(capsys):
    weird = {"format": "9.9", "title": "from future"}
    merged = merge_annotations(user_annotations=weird)
    # Title still merges (we don't refuse to process — we only warn)
    assert merged["title"] == "from future"
    captured = capsys.readouterr()
    assert "unsupported format" in captured.out.lower()
