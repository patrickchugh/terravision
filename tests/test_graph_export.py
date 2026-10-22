"""Export keeps the innermost containment listing without changing the pipeline."""

import copy

import pytest

from modules import helpers


def tfdata(graph, provider="aws"):
    return {
        "graphdict": graph,
        "provider_detection": {"primary_provider": provider, "providers": [provider]},
    }


@pytest.mark.parametrize(
    "provider, boxes, node",
    [
        (
            "aws",
            ["aws_vpc.main", "tv_aws_az.a", "aws_subnet.app~1"],
            "aws_instance.web~1",
        ),
        (
            "azure",
            [
                "azurerm_resource_group.app",
                "azurerm_virtual_network.main",
                "azurerm_subnet.app",
            ],
            "azurerm_linux_virtual_machine.web",
        ),
        (
            "gcp",
            ["google_project.app", "google_compute_network.main", "tv_gcp_zone.a"],
            "google_compute_instance.web",
        ),
    ],
)
@pytest.mark.parametrize("prefix", ["", 'module.app["eu.west"].module.network.'])
def test_export_keeps_only_innermost_listing(provider, boxes, node, prefix):
    outer, middle, inner = [prefix + box for box in boxes]
    node = prefix + node
    graph = {
        outer: [node, inner, middle],
        middle: [node, inner],
        inner: [node],
        node: [],
    }
    data = tfdata(graph, provider)
    before = copy.deepcopy(data)

    exported = helpers.graphdict_for_export(data)

    assert exported == {
        outer: [middle],
        middle: [inner],
        inner: [node],
        node: [],
    }
    assert data == before
    assert helpers.graphdict_for_export(tfdata(exported, provider)) == exported
    exported[node].append("new.target")
    assert data == before  # every target list is copied, not just changed lists


def test_export_preserves_siblings_arrows_and_exact_container_types():
    outer, left, right = "aws_vpc.main", "aws_subnet.left", "aws_subnet.right"
    web, db = "aws_instance.web", "aws_instance.db"
    not_a_box = "module.aws_vpc.aws_vpc_endpoint.interface"
    graph = {
        outer: [left, right, web, db, not_a_box],
        left: [web],
        right: [web],
        web: [db, left],
        db: [],
        not_a_box: [db],
    }

    exported = helpers.graphdict_for_export(tfdata(graph))

    assert exported == {**graph, outer: [left, right, db, not_a_box]}
    # The sibling ambiguity still needs numbered copies; do not pick a winner.
    assert exported[left] == exported[right] == [web]


@pytest.mark.parametrize("length", [1, 2, 3])
def test_export_leaves_cyclic_containers_intact(length):
    boxes = [f"aws_group.box{i}" for i in range(length)]
    node = "aws_instance.web"
    graph = {box: [boxes[(i + 1) % length], node] for i, box in enumerate(boxes)}
    graph["aws_vpc.main"] = [*boxes, node]
    graph[node] = []

    assert helpers.graphdict_for_export(tfdata(graph)) == graph


def test_export_empty_graph():
    assert helpers.graphdict_for_export({}) == {}
