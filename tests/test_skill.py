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


DOCS = SKILL.parents[1] / "docs"
_EXAMPLE_LINK = re.compile(r"\]\((?:[^)\s]*/)?([\w.-]+\.tvg\.json)\)")


def _graph_format(text: str) -> str:
    """A graph-format copy with its example links reduced to the file name.

    The docs site links examples on GitHub and the skill links its own
    examples folder; that is the only difference the copies may have.
    """
    return _EXAMPLE_LINK.sub(r"](\1)", text).strip()


def _llms_full_graph_format() -> str:
    """The Graph Format section of docs/llms-full.txt, up to its separator."""
    text = (DOCS / "llms-full.txt").read_text()
    start = text.index("# TerraVision Graph Format (TVG)")
    end = text.index("\n---\n", start)
    return text[start:end]


def test_graph_format_copies_match():
    """AI-005: the docs page, the skill's reference and llms-full.txt carry
    the same Graph Format, so an assistant reads the same rules everywhere."""
    docs = _graph_format((DOCS / "graph-format.md").read_text())
    skill = _graph_format((SKILL / "references" / "graph-format.md").read_text())
    llms = _graph_format(_llms_full_graph_format())
    assert skill == docs, "skill references/graph-format.md differs from docs"
    assert llms == docs, "docs/llms-full.txt Graph Format differs from docs"


def test_graph_format_example_links_point_at_real_files():
    """Normalising the links must not hide a link to a missing example."""
    for page, folder in (
        (DOCS / "graph-format.md", SKILL.parents[1] / "examples" / "graphs"),
        (SKILL / "references" / "graph-format.md", SKILL / "examples"),
    ):
        names = _EXAMPLE_LINK.findall(page.read_text())
        assert names, page
        for name in names:
            assert (folder / name).is_file(), f"{page.name} links missing {name}"


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


def test_validator_group_links_match_provider_configs():
    from modules.config import cloud_config_aws, cloud_config_azure, cloud_config_gcp

    expected = {
        link["resource_type"]
        for config, prefix in (
            (cloud_config_aws, "AWS"),
            (cloud_config_azure, "AZURE"),
            (cloud_config_gcp, "GCP"),
        )
        for link in getattr(config, f"{prefix}_GROUP_LINKS")
    }
    links = _validator().GROUP_LINKS
    assert set(links) == expected
    assert set(links.values()) <= _validator().CONTAINER_TYPES


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
            # Listed in a subnet and in the resource group around it: the
            # subnet is the one to keep.
            {
                "azurerm_resource_group.app": [
                    "azurerm_virtual_network.main",
                    "azurerm_function_app.api",
                ],
                "azurerm_virtual_network.main": ["azurerm_subnet.app"],
                "azurerm_subnet.app": ["azurerm_function_app.api"],
            },
            "Remove azurerm_function_app.api from azurerm_resource_group.app "
            "and keep it in azurerm_subnet.app.",
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


def test_nested_boxes_do_not_suggest_numbered_copies():
    """Azure Functions went missing from its subnet: listed in the subnet and
    the resource group, the warning said to use numbered copies, and the
    assistant dropped the subnet listing instead."""
    found = _validator().warnings(
        {
            "aws_vpc.main": ["aws_subnet.app", "aws_lambda_function.fn"],
            "aws_subnet.app": ["aws_lambda_function.fn"],
        }
    )
    assert len(found) == 1
    assert "keep it in aws_subnet.app" in found[0]
    assert "numbered copies" not in found[0]


def test_two_subnets_inside_a_listed_network_get_both_warnings():
    found = _validator().warnings(
        {
            "google_compute_network.vpc": [
                "google_compute_subnetwork.a",
                "google_compute_subnetwork.b",
                "google_compute_instance.vm",
            ],
            "google_compute_subnetwork.a": ["google_compute_instance.vm"],
            "google_compute_subnetwork.b": ["google_compute_instance.vm"],
        }
    )
    assert any("Remove google_compute_instance.vm from" in w for w in found)
    assert any("numbered copies" in w for w in found)


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


# ── Pattern library (examples/patterns) ─────────────────────────────

PATTERNS = SKILL / "examples" / "patterns"


def _index():
    return json.loads((PATTERNS / "index.json").read_text())


def test_pattern_index_matches_files_and_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_example_patterns",
        SKILL.parents[1] / "scripts" / "gen_example_patterns.py",
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    names = [entry["name"] for entry in _index()]
    assert names == list(generator.PATTERNS)
    assert sorted(
        p.stem.removesuffix(".tvg") for p in PATTERNS.glob("*.tvg.json")
    ) == sorted(names)
    assert {entry["provider"] for entry in _index()} <= {"aws", "azure", "gcp"}


@pytest.mark.parametrize("entry", _index(), ids=lambda e: e["name"])
def test_patterns_are_valid_plain_single_provider_graphs(entry):
    validator = _validator()
    graph = json.loads((PATTERNS / f"{entry['name']}.tvg.json").read_text())
    assert validator.validate(graph) == []
    nodes = set(graph) | {t for targets in graph.values() for t in targets}
    assert not any(n.startswith("module.") or "[" in n for n in nodes)
    assert {validator.provider_of(n) for n in nodes} - {None} == {entry["provider"]}


@pytest.mark.parametrize(
    "unknown, best",
    [
        ("google_sql_instance", "google_sql_database_instance"),
        ("aws_lamda_function", "aws_lambda_function"),
        ("aws_ecs_fargte", "aws_ecs_fargate"),
        ("aws_rds_sql_server", "aws_rds_sqlserver"),
    ],
)
def test_unknown_type_suggestions(unknown, best):
    validator = _validator()
    [warning] = [
        w
        for w in validator.warnings({f"{unknown}.x": []})
        if w.startswith("Unknown type")
    ]
    assert f"Did you mean {best}" in warning
