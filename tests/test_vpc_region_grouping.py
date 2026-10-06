"""VPCs are drawn in a box for their region only when they span regions."""

import shutil
from pathlib import Path

import pytest

from modules.resource_handlers_aws import aws_handle_vpc_region_grouping

PROVIDERS = {
    "main.tf": [
        {"aws": {"region": "us-east-1"}},
        {"aws": {"alias": "dr", "region": "eu-west-1"}},
    ]
}


def _tfdata(vpcs):
    return {
        "graphdict": {f"aws_vpc.{name}": [] for name in vpcs},
        "meta_data": {},
        "all_provider": PROVIDERS,
        "all_resource": {"main.tf": [{"aws_vpc": vpcs}]},
    }


def test_vpcs_in_two_regions_get_region_boxes():
    tfdata = aws_handle_vpc_region_grouping(
        _tfdata({"primary": {}, "dr": {"provider": "${aws.dr}"}})
    )
    graph = tfdata["graphdict"]
    assert graph["tv_aws_region.us-east-1"] == ["aws_vpc.primary"]
    assert graph["tv_aws_region.eu-west-1"] == ["aws_vpc.dr"]


def test_a_single_region_gets_no_region_box():
    tfdata = aws_handle_vpc_region_grouping(_tfdata({"a": {}, "b": {}}))
    assert not any(k.startswith("tv_aws_region") for k in tfdata["graphdict"])


def test_an_unknown_alias_leaves_that_vpc_alone():
    tfdata = aws_handle_vpc_region_grouping(
        _tfdata({"primary": {}, "x": {"provider": "${aws.nope}"}})
    )
    assert not any(k.startswith("tv_aws_region") for k in tfdata["graphdict"])


FIXTURE = Path(__file__).parent / "fixtures" / "aws_terraform" / "multi_region_vpc"


@pytest.mark.slow
def test_multi_region_fixture_draws_each_vpc_in_its_region(tmp_path, monkeypatch):
    """terraform plan with mock credentials, so no AWS account is needed."""
    from terravision.terravision import compile_tfdata

    source = tmp_path / "multi_region_vpc"
    shutil.copytree(
        FIXTURE, source, ignore=shutil.ignore_patterns(".terraform*", "*.tfstate*")
    )
    (source / "mock_credentials_override.tf").write_text(
        'provider "aws" {\n'
        '  access_key                  = "mock"\n'
        '  secret_key                  = "mock"\n'
        "  skip_credentials_validation = true\n"
        "  skip_requesting_account_id  = true\n"
        "  skip_metadata_api_check     = true\n"
        "}\n"
        'provider "aws" {\n'
        '  alias                       = "dr"\n'
        '  access_key                  = "mock"\n'
        '  secret_key                  = "mock"\n'
        "  skip_credentials_validation = true\n"
        "  skip_requesting_account_id  = true\n"
        "  skip_metadata_api_check     = true\n"
        "}\n"
    )
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    graph = compile_tfdata(
        str(source), [], "default", debug=False, annotate="", upgrade=True
    )["graphdict"]
    assert "aws_vpc.primary" in graph["tv_aws_region.us-east-1"]
    assert "aws_vpc.dr" in graph["tv_aws_region.eu-west-1"]
