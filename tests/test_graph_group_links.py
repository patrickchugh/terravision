"""Peerings in graph files draw as a line between the two network boxes.

Issue #220: a graph file carries no attributes, so the peering's two ends
were never found. Azure hid the peering, AWS drew it as an icon inside one
VPC and GCP as a generic box, and none drew the line. The graph says both
ends: the network that lists the peering, and the network the peering lists.
"""

import json

import pytest
from click.testing import CliRunner

from terravision.terravision import cli

PEERINGS = {
    "aws": ("aws_vpc", "aws_subnet", "aws_instance", "aws_vpc_peering_connection"),
    "azure": (
        "azurerm_virtual_network",
        "azurerm_subnet",
        "azurerm_linux_virtual_machine",
        "azurerm_virtual_network_peering",
    ),
    "gcp": (
        "google_compute_network",
        "google_compute_subnetwork",
        "google_compute_instance",
        "google_compute_network_peering",
    ),
}


def _peered(provider):
    network, subnet, vm, peering = PEERINGS[provider]
    return {
        f"{network}.a": [f"{subnet}.a", f"{peering}.a_to_b"],
        f"{subnet}.a": [f"{vm}.a"],
        f"{network}.b": [f"{subnet}.b"],
        f"{subnet}.b": [f"{vm}.b"],
        f"{peering}.a_to_b": [f"{network}.b"],
    }


@pytest.mark.parametrize("provider", sorted(PEERINGS))
def test_peering_in_a_graph_file_draws_a_line(tmp_path, provider):
    source = tmp_path / "peered.tvg.json"
    source.write_text(json.dumps(_peered(provider)))
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(source),
            "--format",
            "dot",
            "--outfile",
            str(tmp_path / "peered"),
        ],
    )
    assert result.exit_code == 0, result.output
    [dot] = tmp_path.glob("peered*.dot")
    text = dot.read_text()
    links = [e for e in text.split("];") if "_grouplink=1" in e]
    assert len(links) == 1, "one line between the two networks"
    assert "ltail=" in links[0] and "lhead=" in links[0]
    peering = PEERINGS[provider][3]
    assert f'tf_resource_name="{peering}.a_to_b"' not in text, "no icon as well"


def _validator():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).parents[1]
        / "skills/terravision-cloud-diagrams/scripts/validate_graph.py"
    )
    spec = importlib.util.spec_from_file_location("validate_graph", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("provider", sorted(PEERINGS))
def test_validator_accepts_a_listed_peering(provider):
    validator = _validator()
    graph = _peered(provider)
    assert validator.validate(graph) == []
    assert not [w for w in validator.warnings(graph) if "peering" in w]


def test_validator_warns_about_a_peering_that_cannot_be_drawn():
    graph = _peered("azure")
    graph["azurerm_virtual_network_peering.a_to_b"] = []
    [warning] = [w for w in _validator().warnings(graph) if "peering" in w]
    assert "is drawn as a line between two azurerm_virtual_network boxes" in warning
