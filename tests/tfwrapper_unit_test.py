"""Unit tests for tfwrapper helper functions."""

import pytest

from modules import helpers
from modules.tfwrapper import find_node_in_gvid_table, _normalize_for_gvid_match


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
