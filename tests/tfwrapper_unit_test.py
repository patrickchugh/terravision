"""Unit tests for tfwrapper helper functions."""

import pytest

from modules import helpers
from modules.tfwrapper import (
    find_node_in_gvid_table,
    setup_tfdata,
    _normalize_for_gvid_match,
)


def test_exact_match():
    table = ["aws_instance.web", "aws_s3_bucket.data"]
    assert find_node_in_gvid_table("aws_instance.web", table) == 0


def test_strips_count_index_and_tilde_suffix():
    table = ["aws_instance.web"]
    assert find_node_in_gvid_table("aws_instance.web[0]~1", table) == 0


def test_strips_for_each_key_on_top_level_resource():
    table = ["aws_instance.web"]
    assert find_node_in_gvid_table('aws_instance.web["primary"]', table) == 0


def test_module_resource_with_count_and_tilde():
    table = ["module.vpc.aws_subnet.public"]
    assert find_node_in_gvid_table("module.vpc.aws_subnet.public[0]~1", table) == 0


def test_nested_module_for_each_with_inner_count():
    """Regression for issue #186.

    `module.projects["devops"].module.project-factory.<resource>[0]~1` must
    match the bare module-prefixed entry that terraform graph emits for the
    expand node.
    """
    table = [
        "module.projects.module.project-factory."
        "google_project_default_service_accounts.default_service_accounts"
    ]
    node = (
        'module.projects["devops"].module.project-factory.'
        "google_project_default_service_accounts.default_service_accounts[0]~1"
    )
    assert find_node_in_gvid_table(node, table) == 0


def test_unmatched_node_raises_terravision_error():
    table = ["aws_instance.web"]
    with pytest.raises(helpers.TerravisionError) as excinfo:
        find_node_in_gvid_table("aws_lambda_function.api[0]~1", table)
    msg = str(excinfo.value)
    assert "Cannot map node" in msg
    assert "Normalized form tried" in msg


def test_normalize_strips_all_brackets_and_tilde():
    assert (
        _normalize_for_gvid_match('module.foo["k"].module.bar.aws_thing.x[0]~3')
        == "module.foo.module.bar.aws_thing.x"
    )


# ---------------------------------------------------------------------------
# setup_tfdata() node naming
# ---------------------------------------------------------------------------


def _resource_change(address, index=None, resource_type=None):
    """Build a minimal `terraform show -json` resource_changes entry."""
    obj = {
        "address": address,
        "mode": "managed",
        "type": resource_type or address.split(".")[0],
        "change": {"after": {"name": "x"}, "after_unknown": {}},
    }
    if index is not None:
        obj["index"] = index
    return obj


def _nodes_for(*resource_changes):
    tfdata = setup_tfdata({"tf_resources_created": list(resource_changes)})
    return list(tfdata["graphdict"].keys())


def test_for_each_key_is_not_appended_twice():
    """Regression: plan `address` already carries the for_each key.

    Appending `index` again produced `generic_subnet["apps"][apps]`, which
    broke key matching and node labels.
    """
    nodes = _nodes_for(
        _resource_change(
            'azurerm_subnet.generic_subnet["security.rt_mgmt.mgmt01"]',
            index="security.rt_mgmt.mgmt01",
        )
    )
    assert nodes == ['azurerm_subnet.generic_subnet["security.rt_mgmt.mgmt01"]']


def test_count_index_keeps_tilde_suffix():
    """The ~N convention for count is relied on across the codebase."""
    nodes = _nodes_for(
        _resource_change("aws_subnet.private[0]", index=0),
        _resource_change("aws_subnet.private[1]", index=1),
    )
    assert nodes == ["aws_subnet.private[0]~1", "aws_subnet.private[1]~2"]


def test_resource_without_index_is_unchanged():
    nodes = _nodes_for(_resource_change("aws_vpc.main"))
    assert nodes == ["aws_vpc.main"]


def test_for_each_key_appended_when_address_lacks_it():
    """Defensive: honour `index` if a plan ever omits it from `address`."""
    nodes = _nodes_for(_resource_change("aws_subnet.private", index="web"))
    assert nodes == ["aws_subnet.private[web]"]
