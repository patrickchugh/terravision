"""Tests for the agent skill in skills/terravision-cloud-diagrams: its
frontmatter, and the dependency-free graph validator it ships."""

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

SKILL = Path(__file__).resolve().parents[1] / "skills" / "terravision-cloud-diagrams"


def _validator():
    spec = importlib.util.spec_from_file_location(
        "validate_graph", SKILL / "scripts" / "validate_graph.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter():
    text = (SKILL / "SKILL.md").read_text()
    return yaml.safe_load(re.match(r"---\n(.*?)\n---\n", text, re.S).group(1))


def _minimal_example():
    text = (SKILL / "SKILL.md").read_text()
    return json.loads(
        re.search(r"Minimal example:\n\n```json\n(.*?)```", text, re.S)[1]
    )


def test_frontmatter_is_valid_yaml():
    """A strict YAML parser must accept it; an unquoted ': ' in the
    description once made the whole skill unloadable for strict agents."""
    meta = _frontmatter()
    assert meta["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9-]+", meta["name"])
    assert 0 < len(meta["description"]) <= 1024


@pytest.mark.parametrize(
    "attr, config_suffix",
    [
        ("CONTAINER_TYPES", "GROUP_NODES"),
        ("SHARED_SERVICES", "SHARED_SERVICES"),
        ("ALWAYS_DRAW_LINE", "ALWAYS_DRAW_LINE"),
    ],
)
def test_validator_rules_match_provider_configs(attr, config_suffix):
    from modules.config import cloud_config_aws, cloud_config_azure, cloud_config_gcp

    expected = set()
    for config, prefix in (
        (cloud_config_aws, "AWS"),
        (cloud_config_azure, "AZURE"),
        (cloud_config_gcp, "GCP"),
    ):
        expected |= set(getattr(config, f"{prefix}_{config_suffix}"))
    assert getattr(_validator(), attr) == expected


@pytest.mark.parametrize("example", sorted((SKILL / "examples").glob("*.json")))
def test_shipped_examples_are_valid(example):
    assert _validator().validate(json.loads(example.read_text())) == []


def test_minimal_example_is_clean():
    validator = _validator()
    graph = _minimal_example()
    assert validator.validate(graph) == []
    assert validator.warnings(graph) == []


@pytest.mark.parametrize(
    "graph, expected",
    [
        (
            {"aws_lambda_function.fn": ["aws_vpc.main"]},
            "is not drawn: aws_vpc is a container",
        ),
        (
            {"aws_ecs_fargate.api": ["aws_ecr_repository.images"]},
            "List it in aws_group.shared_services",
        ),
        (
            {"google_cloud_run_v2_service.api": ["google_secret_manager_secret.s"]},
            "google_secret_manager_secret is a shared service.",
        ),
        (
            {
                "aws_subnet.a": ["aws_alb.web"],
                "aws_subnet.b": ["aws_alb.web"],
            },
            "is drawn in only one of them",
        ),
        (
            {
                "aws_subnet.a": ["aws_instance.web~1"],
                "aws_alb.lb": ["aws_instance.web"],
            },
            "which has numbered copies",
        ),
        (
            {
                "aws_lambda_function.a": ["aws_sqs_queue.q"],
                "aws_sqs_queue.q": ["aws_lambda_function.a"],
            },
            "only one arrow is drawn",
        ),
        (
            {"aws_lambda_function.fn": ["aws_lamda_function.typo"]},
            "Unknown type 'aws_lamda_function'",
        ),
        (
            {"aws_lambda_function.fn": ["aws_dynamodb_table.Orders-Table"]},
            "use a lowercase snake_case name",
        ),
    ],
)
def test_warnings(graph, expected):
    validator = _validator()
    assert validator.validate(graph) == []
    found = validator.warnings(graph)
    assert any(expected in w for w in found), found


@pytest.mark.parametrize(
    "graph",
    [
        # Arrows that do draw: containment, and exempt sources into a shared service
        {
            "aws_vpc.main": ["aws_subnet.app"],
            "aws_subnet.app": ["aws_lambda_function.fn"],
        },
        {"aws_ecs_service.api": ["aws_ecr_repository.images"]},
        # A shared service already in the group has its arrows hidden on purpose
        {
            "aws_ecs_fargate.api": ["aws_cloudwatch_log_group.logs"],
            "aws_group.shared_services": ["aws_cloudwatch_log_group.logs"],
        },
    ],
)
def test_no_false_warnings(graph):
    assert _validator().warnings(graph) == []


def test_cli_prints_warnings_and_succeeds(tmp_path):
    import subprocess
    import sys

    graph = tmp_path / "g.tvg.json"
    graph.write_text(json.dumps({"aws_lambda_function.fn": ["aws_vpc.main"]}))
    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "validate_graph.py"), str(graph)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.startswith(
        "WARNING: Arrow aws_lambda_function.fn -> aws_vpc.main"
    )
    assert result.stdout.rstrip().endswith("OK: 2 nodes, 1 edges")
