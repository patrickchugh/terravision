"""Annotation names follow the renames the pipeline makes.

An annotation file names resources by Terraform address, but consolidation
(aws_lb.main merged into aws_lb.elb), variants (aws_lb.elb drawn as
aws_alb.elb) and numbering (aws_alb.elb~1) rename them, so labels and flow
badges written against the address silently did nothing.
"""

import shutil
from pathlib import Path

import pytest

from modules.annotations import resolve_annotation_names

AWS = {"primary_provider": "aws", "providers": ["aws"]}


def _tfdata(graph, merged=None):
    return {
        "graphdict": graph,
        "consolidated_into": merged or {},
        "provider_detection": AWS,
    }


def test_a_consolidated_name_is_translated():
    tfdata = _tfdata({"aws_lb.elb": []}, {"aws_lb.main": "aws_lb.elb"})
    out = resolve_annotation_names(
        {"update": {"aws_lb.main": {"label": "Entry"}}}, tfdata
    )
    assert out["update"] == {"aws_lb.elb": {"label": "Entry"}}


def test_a_variant_and_numbered_copies_are_followed_for_flow_steps():
    tfdata = _tfdata(
        {"aws_alb.elb~1": ["aws_instance.web~1"], "aws_alb.elb~2": []},
        {"aws_lb.main": "aws_lb.elb"},
    )
    annotations = {
        "flows": {
            "f": {
                "steps": [
                    {"resource": "aws_lb.main"},
                    {"resource": "aws_lb.main -> aws_instance.web"},
                ]
            }
        },
        "update": {"aws_lb.main": {"label": "Entry"}},
    }
    out = resolve_annotation_names(annotations, tfdata)
    steps = out["flows"]["f"]["steps"]
    # A flow step badges one exact node: the first copy
    assert steps[0]["resource"] == "aws_alb.elb~1"
    assert steps[1]["resource"] == "aws_alb.elb~1 -> aws_instance.web~1"
    # An update names every copy through its base name
    assert out["update"] == {"aws_alb.elb": {"label": "Entry"}}


def test_names_the_graph_has_and_wildcards_are_left_alone():
    tfdata = _tfdata({"aws_lambda_function.api": []})
    annotations = {
        "connect": {"aws_lambda_function.api": ["tv_aws_users.users"]},
        "update": {"aws_lambda*": {"label": "Fn"}, "aws_vpc.nope": {"label": "x"}},
        "remove": ["aws_iam_role.r"],
    }
    assert resolve_annotation_names(annotations, tfdata) == annotations


def test_the_input_is_not_changed():
    tfdata = _tfdata({"aws_lb.elb": []}, {"aws_lb.main": "aws_lb.elb"})
    annotations = {"update": {"aws_lb.main": {"label": "Entry"}}}
    resolve_annotation_names(annotations, tfdata)
    assert annotations == {"update": {"aws_lb.main": {"label": "Entry"}}}


FIXTURE = Path(__file__).parent / "fixtures" / "aws_terraform" / "waf_alb"


@pytest.mark.slow
def test_waf_alb_annotations_by_terraform_address_reach_the_drawn_alb(
    tmp_path, monkeypatch
):
    """aws_lb.main is drawn as aws_alb.elb~1; its label and badge still land."""
    import yaml
    from click.testing import CliRunner

    from terravision.terravision import cli

    source = tmp_path / "waf_alb"
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
    )
    annotate = tmp_path / "terravision.yml"
    annotate.write_text(
        yaml.safe_dump(
            {
                "format": "0.3",
                "update": {"aws_lb.main": {"label": "Public entry"}},
                "flows": {
                    "request": {
                        "description": "A visitor reaches the app",
                        "steps": [
                            {"resource": "aws_lb.main", "detail": "Request arrives"}
                        ],
                    }
                },
            }
        )
    )
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            "draw",
            "--source",
            str(source),
            "--annotate",
            str(annotate),
            "--format",
            "dot",
            "--outfile",
            str(tmp_path / "out"),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    [dot] = list(tmp_path.glob("out*.dot"))
    text = dot.read_text()
    assert "Public entry" in text
    assert "_flowsteps" in text
