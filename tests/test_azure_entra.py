"""Entra ID objects and role assignments on Azure diagrams.

A role assignment is drawn as a dashed arrow from the identity to what it may
use, labelled with the role, rather than as a node named by a GUID; Entra ID
objects sit in a Microsoft Entra ID box; and arrows from identities are drawn
even into the Shared Services box, where most grants point.
"""

import json
import re
import xml.etree.ElementTree as ET

from click.testing import CliRunner

import modules.drawing as drawing
from modules import resource_handlers_azure as handlers
from terravision.terravision import cli


def _tfdata(graphdict, source):
    """tfdata with a graph and the Terraform source of its resources.

    source maps "type.name" to its attributes as the HCL writes them.
    """
    blocks = []
    for node, attributes in source.items():
        resource_type, name = node.split(".", 1)
        blocks.append({resource_type: {name: attributes}})
    return {
        "graphdict": {k: list(v) for k, v in graphdict.items()},
        "meta_data": {k: {} for k in graphdict},
        "original_metadata": {},
        "all_resource": {"main.tf": blocks},
        "hidden": [],
    }


def test_role_assignment_becomes_a_labelled_permission_arrow():
    tfdata = _tfdata(
        {
            "azurerm_user_assigned_identity.app": [],
            "azurerm_key_vault.secrets": [],
            "azurerm_role_assignment.read_secrets": [],
        },
        {
            "azurerm_role_assignment.read_secrets": {
                "principal_id": "${azurerm_user_assigned_identity.app.principal_id}",
                "scope": "${azurerm_key_vault.secrets.id}",
                "role_definition_name": "Key Vault Secrets User",
            }
        },
    )
    tfdata["meta_data"]["azurerm_role_assignment.read_secrets"] = {
        "role_definition_name": "Key Vault Secrets User"
    }
    tfdata = handlers.azure_handle_permission_links(tfdata)
    graph, meta = tfdata["graphdict"], tfdata["meta_data"]
    assert "azurerm_role_assignment.read_secrets" not in graph
    assert graph["azurerm_user_assigned_identity.app"] == ["azurerm_key_vault.secrets"]
    identity = meta["azurerm_user_assigned_identity.app"]
    assert identity["permission_edges"] == ["azurerm_key_vault.secrets"]
    assert identity["edge_labels"] == [
        {"azurerm_key_vault.secrets": "Key Vault Secrets User"}
    ]


def test_a_system_assigned_identity_draws_from_its_resource():
    """principal_id from the resource's own identity: the arrow starts there."""
    tfdata = _tfdata(
        {
            "azurerm_kubernetes_cluster.aks": [],
            "azurerm_container_registry.acr": [],
            "azurerm_role_assignment.pull": [],
        },
        {
            "azurerm_role_assignment.pull": {
                "principal_id": "${azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id}",
                "scope": "${azurerm_container_registry.acr.id}",
                "role_definition_name": "AcrPull",
            }
        },
    )
    tfdata = handlers.azure_handle_permission_links(tfdata)
    assert tfdata["graphdict"]["azurerm_kubernetes_cluster.aks"] == [
        "azurerm_container_registry.acr"
    ]


def test_a_custom_role_is_named_after_its_definition():
    tfdata = _tfdata(
        {
            "azuread_service_principal.ci": [],
            "azurerm_storage_account.data": [],
            "azurerm_role_definition.deployer": [],
            "azurerm_role_assignment.ci": [],
        },
        {
            "azurerm_role_assignment.ci": {
                "principal_id": "${azuread_service_principal.ci.object_id}",
                "scope": "${azurerm_storage_account.data.id}",
                "role_definition_id": "${azurerm_role_definition.deployer.role_definition_resource_id}",
            }
        },
    )
    tfdata["meta_data"]["azurerm_role_definition.deployer"] = {"name": "Deployer"}
    tfdata = handlers.azure_handle_permission_links(tfdata)
    labels = tfdata["meta_data"]["azuread_service_principal.ci"]["edge_labels"]
    assert labels == [{"azurerm_storage_account.data": "Deployer"}]


def test_a_box_scope_draws_no_arrow():
    """An arrow cannot end on a box (a resource group)."""
    tfdata = _tfdata(
        {
            "azurerm_user_assigned_identity.app": [],
            "azurerm_resource_group.rg": ["azurerm_user_assigned_identity.app"],
            "azurerm_role_assignment.contributor": [],
        },
        {
            "azurerm_role_assignment.contributor": {
                "principal_id": "${azurerm_user_assigned_identity.app.principal_id}",
                "scope": "${azurerm_resource_group.rg.id}",
                "role_definition_name": "Contributor",
            }
        },
    )
    tfdata = handlers.azure_handle_permission_links(tfdata)
    assert tfdata["graphdict"]["azurerm_user_assigned_identity.app"] == []
    assert "azurerm_role_assignment.contributor" not in tfdata["graphdict"]


def test_entra_objects_are_boxed_and_memberships_become_arrows():
    tfdata = _tfdata(
        {
            "azuread_user.alice": [],
            "azuread_group.admins": [],
            "azuread_group_member.alice": [],
        },
        {
            "azuread_group_member.alice": {
                "member_object_id": "${azuread_user.alice.object_id}",
                "group_object_id": "${azuread_group.admins.object_id}",
            }
        },
    )
    tfdata = handlers.azure_handle_entra(tfdata)
    graph = tfdata["graphdict"]
    assert sorted(graph["tv_azure_entra.tenant"]) == [
        "azuread_group.admins",
        "azuread_user.alice",
    ]
    assert graph["azuread_user.alice"] == ["azuread_group.admins"]
    assert tfdata["meta_data"]["azuread_user.alice"]["edge_labels"] == [
        {"azuread_group.admins": "member"}
    ]


def test_permission_edges_include_identities_and_numbered_copies(monkeypatch):
    monkeypatch.setattr(
        drawing, "PERMISSION_SOURCES", ["azurerm_user_assigned_identity"]
    )
    tfdata = {
        "meta_data": {
            "azurerm_kubernetes_cluster.aks": {
                "permission_edges": ["azurerm_container_registry.acr"]
            }
        }
    }
    assert drawing.is_permission_edge(
        "azurerm_user_assigned_identity.app", "azurerm_key_vault.kv", tfdata
    )
    assert drawing.is_permission_edge(
        "azurerm_kubernetes_cluster.aks", "azurerm_container_registry.acr~1", tfdata
    )
    assert not drawing.is_permission_edge(
        "azurerm_kubernetes_cluster.aks", "azurerm_key_vault.kv", tfdata
    )


GRAPH = {
    "azurerm_resource_group.app": [
        "azurerm_linux_web_app.portal",
        "azurerm_user_assigned_identity.portal",
    ],
    "azurerm_group.shared_services": ["azurerm_key_vault.secrets"],
    "azurerm_linux_web_app.portal": ["azurerm_user_assigned_identity.portal"],
    "azurerm_user_assigned_identity.portal": ["azurerm_key_vault.secrets"],
    "azurerm_key_vault.secrets": [],
    "tv_azure_entra.tenant": ["azuread_group.admins"],
    "azuread_group.admins": ["azurerm_key_vault.secrets"],
}


def _draw(tmp_path, fmt):
    source = tmp_path / "graph.tvg.json"
    source.write_text(json.dumps(GRAPH))
    out = tmp_path / "out"
    result = CliRunner().invoke(
        cli, ["draw", "--source", str(source), "--format", fmt, "--outfile", str(out)]
    )
    assert result.exit_code == 0, result.output
    [path] = tmp_path.glob(f"out*.{fmt}*")
    return path.read_text()


def test_identity_arrows_into_shared_services_are_drawn_dashed(tmp_path):
    dot = _draw(tmp_path, "dot")
    edges = re.findall(r'"([^"]+)" -> "([^"]+)"\s*\[([^\]]*)\]', dot)
    to_vault = [attrs for src, dst, attrs in edges if ".KeyVaults." in dst]
    # The managed identity's and the group's grant on the vault
    assert len(to_vault) == 2
    assert all("style=dashed" in attrs for attrs in to_vault)
    # The web app's use of its identity is not a grant
    to_identity = [attrs for src, dst, attrs in edges if ".ManagedIdentities." in dst]
    assert to_identity and "dashed" not in to_identity[0]


def test_permission_arrows_are_dashed_in_drawio(tmp_path):
    root = ET.fromstring(_draw(tmp_path, "drawio"))
    edges = [c.get("style") for c in root.iter("mxCell") if c.get("edge") == "1"]
    assert sum("dashed=1" in s for s in edges) == 2


def test_a_grant_survives_its_source_being_renamed_to_a_variant(monkeypatch):
    """handle_variants runs after the grant is recorded and renames a firewall
    VM to its appliance variant without moving its metadata. The grant on Key
    Vault, a shared service, must still be found, or the arrow is not drawn."""
    from modules import graphmaker

    vm = "azurerm_linux_virtual_machine.firewall"
    tfdata = _tfdata(
        {
            vm: [],
            "azurerm_key_vault.secrets": [],
            "azurerm_role_assignment.firewall_secrets": [],
        },
        {
            "azurerm_role_assignment.firewall_secrets": {
                "principal_id": f"${{{vm}.identity[0].principal_id}}",
                "scope": "${azurerm_key_vault.secrets.id}",
                "role_definition_name": "Key Vault Secrets User",
            }
        },
    )
    tfdata["provider_detection"] = {"primary_provider": "azure"}
    tfdata["meta_data"][vm] = {"plan": {"publisher": "paloaltonetworks"}}
    tfdata["original_metadata"][vm] = {"source_image_reference": "paloaltonetworks"}
    tfdata["meta_data"]["azurerm_role_assignment.firewall_secrets"] = {
        "role_definition_name": "Key Vault Secrets User"
    }
    tfdata = handlers.azure_handle_permission_links(tfdata)
    tfdata = graphmaker.handle_variants(tfdata)
    appliance = "azurerm_virtual_machine_appliance.firewall"
    assert appliance in tfdata["graphdict"]  # renamed

    monkeypatch.setattr(drawing, "PERMISSION_SOURCES", [])
    assert drawing.is_permission_edge(appliance, "azurerm_key_vault.secrets", tfdata)
    assert drawing._origin_edge_labels(appliance, tfdata) == [
        {"azurerm_key_vault.secrets": "Key Vault Secrets User"}
    ]
