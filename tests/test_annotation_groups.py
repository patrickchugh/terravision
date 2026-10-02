"""Logical groups declared in terravision.yml, drawn from Terraform.

A logical group is a generic box (``aws_group``, ``azurerm_group``,
``tv_gcp_logical_group``) that an annotation file declares with ``add`` and
fills with ``connect``. Its members leave any automatic group (user groups
take precedence), and the box sits inside the innermost container that holds
all of them. Before this, the automatic Lambda group took the Lambdas out of
the user's group, ``reverse_relations`` turned the group's containment of a
Step Functions state machine into an arrow, and the box was drawn empty.
"""

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import graphmaker  # noqa: E402
from modules.config import (  # noqa: E402
    cloud_config_aws,
    cloud_config_azure,
    cloud_config_gcp,
)
from modules.resource_transformers import (  # noqa: E402
    auto_group_by_type,
    group_shared_services,
)

JSON_DIR = Path(__file__).parent / "json"
FIXTURE = Path(__file__).parent / "fixtures" / "aws_terraform" / "stepfunctions_lambda"

LAMBDAS = [
    "aws_lambda_function.notify",
    "aws_lambda_function.process",
    "aws_lambda_function.validate",
]
SFN = "aws_sfn_state_machine.order_workflow"
ORDER_WORKFLOW = {
    "format": 0.2,
    "title": "Group annotation test",
    "add": {"aws_group.order_workflow": {}},
    "connect": {"aws_group.order_workflow": [SFN, *LAMBDAS]},
}


def _tfdata(graph, provider="aws", annotations=None):
    return {
        "graphdict": copy.deepcopy(graph),
        "meta_data": {node: {} for node in graph},
        "provider_detection": {"primary_provider": provider},
        "annotations": annotations or {},
    }


def _group(name, *members):
    return {"add": {name: {}}, "connect": {name: list(members)}}


# --- config -----------------------------------------------------------------


@pytest.mark.parametrize(
    "config,attr,group_type",
    [
        (cloud_config_aws, "AWS", "aws_group"),
        (cloud_config_azure, "AZURE", "azurerm_group"),
        (cloud_config_gcp, "GCP", "tv_gcp_logical_group"),
    ],
)
def test_each_provider_names_a_logical_group_that_is_a_container(
    config, attr, group_type
):
    logical = getattr(config, f"{attr}_LOGICAL_GROUP_NODES")
    assert logical == [group_type]
    assert set(logical) <= set(getattr(config, f"{attr}_GROUP_NODES"))


# --- reverse_relations --------------------------------------------------------


def test_a_group_holding_a_forced_origin_is_not_reversed():
    tfdata = _tfdata({"aws_group.order_workflow": [SFN, *LAMBDAS], SFN: LAMBDAS})
    result = graphmaker.reverse_relations(tfdata)["graphdict"]
    assert result["aws_group.order_workflow"] == [SFN, *LAMBDAS]
    assert "aws_group.order_workflow" not in result[SFN]


def test_an_arrow_into_a_forced_origin_is_still_reversed():
    tfdata = _tfdata({"aws_lambda_function.notify": [SFN], SFN: []})
    result = graphmaker.reverse_relations(tfdata)["graphdict"]
    assert result["aws_lambda_function.notify"] == []
    assert result[SFN] == ["aws_lambda_function.notify"]


# --- automatic grouping leaves user groups alone ------------------------------


def test_auto_group_skips_resources_in_a_user_group():
    graph = {"aws_group.order_workflow": [SFN, *LAMBDAS], **{n: [] for n in LAMBDAS}}
    tfdata = auto_group_by_type(_tfdata(graph), ["aws_lambda_function"], 3)
    assert "aws_group.aws_lambda_function" not in tfdata["graphdict"]
    assert tfdata["graphdict"]["aws_group.order_workflow"] == [SFN, *LAMBDAS]


def test_auto_group_counts_only_ungrouped_resources_towards_the_threshold():
    extra = ["aws_lambda_function.audit", "aws_lambda_function.report"]
    graph = {
        "aws_group.order_workflow": LAMBDAS[:1],
        **{n: [] for n in LAMBDAS + extra},
    }
    tfdata = auto_group_by_type(_tfdata(graph), ["aws_lambda_function"], 3)
    auto = tfdata["graphdict"]["aws_group.aws_lambda_function"]
    assert sorted(auto) == sorted(LAMBDAS[1:] + extra)
    assert tfdata["graphdict"]["aws_group.order_workflow"] == LAMBDAS[:1]


def test_auto_group_still_groups_when_there_is_no_user_group():
    graph = {n: [] for n in LAMBDAS}
    tfdata = auto_group_by_type(_tfdata(graph), ["aws_lambda_function"], 3)
    assert sorted(tfdata["graphdict"]["aws_group.aws_lambda_function"]) == LAMBDAS


def test_shared_services_skip_a_resource_in_a_user_group():
    graph = {
        "aws_group.observability": ["aws_cloudwatch_log_group.app"],
        "aws_cloudwatch_log_group.app": [],
        "aws_kms_key.main": [],
    }
    tfdata = group_shared_services(
        _tfdata(graph), ["aws_cloudwatch_log_group", "aws_kms_key"]
    )
    shared = tfdata["graphdict"]["aws_group.shared_services"]
    assert "aws_cloudwatch_log_group.app" not in shared
    # KMS keys are consolidated into one node, so match the type
    assert any(node.startswith("aws_kms_key.") for node in shared)


def test_azure_shared_services_box_is_not_created_when_users_grouped_all():
    graph = {
        "azurerm_group.platform": ["azurerm_key_vault.kv"],
        "azurerm_key_vault.kv": [],
    }
    tfdata = group_shared_services(
        _tfdata(graph, "azure"),
        ["azurerm_key_vault"],
        group_name="azurerm_group.shared_services",
        always_include="",
    )
    assert "azurerm_group.shared_services" not in tfdata["graphdict"]


# --- place_annotation_groups --------------------------------------------------


def test_without_annotation_groups_the_graph_is_unchanged():
    graph = {"aws_group.shared_services": ["aws_kms_key.main"], "aws_kms_key.main": []}
    tfdata = graphmaker.place_annotation_groups(_tfdata(graph))
    assert tfdata["graphdict"] == graph


def test_members_leave_an_automatic_group_which_is_then_removed():
    graph = {
        "aws_group.order_workflow": [SFN, *LAMBDAS],
        "aws_group.aws_lambda_function": list(LAMBDAS),
        "aws_group.shared_services": ["aws_iam_group.of_services"],
        **{n: [] for n in LAMBDAS},
        SFN: [],
    }
    tfdata = _tfdata(graph, annotations=ORDER_WORKFLOW)
    result = graphmaker.place_annotation_groups(tfdata)["graphdict"]
    assert result["aws_group.order_workflow"] == [SFN, *LAMBDAS]
    assert "aws_group.aws_lambda_function" not in result
    # An automatic group the user group took nothing from is left alone
    assert result["aws_group.shared_services"] == ["aws_iam_group.of_services"]


def test_a_group_is_nested_in_the_container_its_members_share():
    graph = {
        "azurerm_resource_group.main": [
            "azurerm_container_registry.acr",
            "azurerm_storage_account.logs",
            "azurerm_virtual_network.main",
        ],
        "azurerm_group.platform": [
            "azurerm_container_registry.acr",
            "azurerm_storage_account.logs",
        ],
    }
    annotations = _group(
        "azurerm_group.platform",
        "azurerm_container_registry.acr",
        "azurerm_storage_account.logs",
    )
    tfdata = _tfdata(graph, "azure", annotations)
    result = graphmaker.place_annotation_groups(tfdata)["graphdict"]
    # One box per node: the members are drawn in the group, inside the
    # resource group, and no longer listed in the resource group itself
    assert result["azurerm_resource_group.main"] == [
        "azurerm_virtual_network.main",
        "azurerm_group.platform",
    ]
    assert result["azurerm_group.platform"] == [
        "azurerm_container_registry.acr",
        "azurerm_storage_account.logs",
    ]


def test_a_group_is_nested_in_the_innermost_shared_container():
    graph = {
        "google_compute_network.main": [
            "google_sql_database_instance.main",
            "tv_gcp_region.central",
        ],
        "tv_gcp_region.central": ["google_redis_instance.cache"],
        "tv_gcp_logical_group.data": [
            "google_sql_database_instance.main",
            "google_redis_instance.cache",
        ],
    }
    annotations = _group(
        "tv_gcp_logical_group.data",
        "google_sql_database_instance.main",
        "google_redis_instance.cache",
    )
    tfdata = _tfdata(graph, "gcp", annotations)
    result = graphmaker.place_annotation_groups(tfdata)["graphdict"]
    # The network holds both (the cache through the region); the region does
    # not hold the database, so the group goes in the network
    assert "tv_gcp_logical_group.data" in result["google_compute_network.main"]
    assert "tv_gcp_logical_group.data" not in result["tv_gcp_region.central"]
    assert (
        "google_sql_database_instance.main" not in result["google_compute_network.main"]
    )
    # The cache sits in a container the group is not inside, so it stays there
    assert result["tv_gcp_region.central"] == ["google_redis_instance.cache"]
    assert result["tv_gcp_logical_group.data"] == ["google_sql_database_instance.main"]


def test_members_without_a_container_leave_the_group_at_the_top_level():
    graph = {"aws_group.order_workflow": [SFN, *LAMBDAS], SFN: LAMBDAS}
    tfdata = _tfdata(graph, annotations=ORDER_WORKFLOW)
    result = graphmaker.place_annotation_groups(tfdata)["graphdict"]
    assert not [p for p, c in result.items() if "aws_group.order_workflow" in c]


def test_a_member_in_another_container_stays_there_with_a_warning(capsys):
    graph = {
        "azurerm_resource_group.main": [
            "azurerm_container_registry.acr",
            "azurerm_virtual_network.main",
        ],
        "azurerm_virtual_network.main": ["azurerm_subnet.nodes"],
        "azurerm_subnet.nodes": ["azurerm_kubernetes_cluster.aks"],
        "azurerm_group.platform": [
            "azurerm_container_registry.acr",
            "azurerm_kubernetes_cluster.aks",
        ],
    }
    annotations = _group(
        "azurerm_group.platform",
        "azurerm_container_registry.acr",
        "azurerm_kubernetes_cluster.aks",
    )
    tfdata = _tfdata(graph, "azure", annotations)
    result = graphmaker.place_annotation_groups(tfdata)["graphdict"]
    assert result["azurerm_group.platform"] == ["azurerm_container_registry.acr"]
    assert result["azurerm_subnet.nodes"] == ["azurerm_kubernetes_cluster.aks"]
    out = capsys.readouterr().out
    assert "azurerm_kubernetes_cluster.aks is not drawn in azurerm_group.platform" in (
        out
    )
    assert "azurerm_subnet.nodes" in out


def test_a_group_the_user_placed_is_not_moved():
    graph = {
        "aws_vpc.main": ["aws_subnet.private", "aws_group.app"],
        "aws_subnet.private": ["aws_lambda_function.api"],
        "aws_group.app": ["aws_lambda_function.worker"],
    }
    annotations = {
        "add": {"aws_group.app": {}},
        "connect": {
            "aws_vpc.main": ["aws_group.app"],
            "aws_group.app": ["aws_lambda_function.worker"],
        },
    }
    tfdata = _tfdata(graph, annotations=annotations)
    result = graphmaker.place_annotation_groups(tfdata)["graphdict"]
    # The worker has no container of its own; the group stays where the
    # annotation put it rather than moving to the top level
    assert result["aws_vpc.main"] == ["aws_subnet.private", "aws_group.app"]
    assert result["aws_group.app"] == ["aws_lambda_function.worker"]


# --- whole pipeline, replayed (no Terraform) ----------------------------------


def _replay(tmp_path, tfdata_file, annotations):
    """Run the enrichment pipeline on a debug replay carrying annotations.

    A tfdata.json replay keeps the annotations it was captured with and
    ignores --annotate, so the annotations are written into a copy.
    """
    from terravision.terravision import compile_tfdata

    data = json.loads((JSON_DIR / tfdata_file).read_text())
    data["annotations"] = annotations
    replay = tmp_path / "tfdata.json"
    replay.write_text(json.dumps(data))
    return compile_tfdata(str(replay), [], "default", debug=False)["graphdict"]


def test_stepfunctions_replay_draws_the_order_workflow_group(tmp_path):
    graph = _replay(tmp_path, "stepfunctions-lambda-tfdata.json", ORDER_WORKFLOW)
    assert sorted(graph["aws_group.order_workflow"]) == sorted([SFN, *LAMBDAS])
    assert "aws_group.aws_lambda_function" not in graph
    assert "aws_group.order_workflow" not in graph[SFN]
    assert sorted(graph[SFN]) == sorted(["aws_iam_role.sfn_role", *LAMBDAS])


def test_azure_replay_nests_the_group_in_the_resource_group(tmp_path):
    members = [
        "azurerm_container_registry.acr",
        "azurerm_log_analytics_workspace.aks",
        "azurerm_storage_account.aks",
    ]
    annotations = _group("azurerm_group.platform", *members)
    graph = _replay(tmp_path, "azure-aks-tfdata.json", annotations)
    assert graph["azurerm_group.platform"] == members
    assert "azurerm_group.platform" in graph["azurerm_resource_group.aks"]
    assert not set(members) & set(graph["azurerm_resource_group.aks"])
    # Every shared service went to the user group, so no empty box is left
    assert "azurerm_group.shared_services" not in graph


# --- whole pipeline, from Terraform --------------------------------------------


@pytest.mark.slow
def test_stepfunctions_fixture_with_annotate_draws_the_group(tmp_path, monkeypatch):
    """terraform plan with mock credentials, so no AWS account is needed."""
    from terravision.terravision import compile_tfdata
    import yaml

    source = tmp_path / "stepfunctions_lambda"
    shutil.copytree(
        FIXTURE, source, ignore=shutil.ignore_patterns(".terraform*", "*.tfstate*")
    )
    # Terraform merges *_override.tf into the provider block in main.tf
    (source / "mock_credentials_override.tf").write_text(
        'provider "aws" {\n'
        '  access_key                  = "mock"\n'
        '  secret_key                  = "mock"\n'
        "  skip_credentials_validation = true\n"
        "  skip_requesting_account_id  = true\n"
        "  skip_metadata_api_check     = true\n"
        "}\n"
    )
    annotate = tmp_path / "terravision.yml"
    annotate.write_text(yaml.safe_dump(ORDER_WORKFLOW))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)

    graph = compile_tfdata(
        str(source), [], "default", debug=False, annotate=str(annotate), upgrade=True
    )["graphdict"]

    assert sorted(graph["aws_group.order_workflow"]) == sorted([SFN, *LAMBDAS])
    assert "aws_group.aws_lambda_function" not in graph
    assert "aws_group.order_workflow" not in graph[SFN]
