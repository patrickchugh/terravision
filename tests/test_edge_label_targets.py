"""Each arrow keeps its own label when its endpoints share a consolidated prefix.

aws_ecs_fargate.* nodes all match the aws_ecs consolidation prefix. The
label lookup accepted any label whose target matched that prefix, so a load
balancer with labelled arrows to two Fargate services drew one label on
both, and the other label nowhere.
"""

import json

import yaml
from click.testing import CliRunner

from terravision.terravision import cli

GRAPH = {
    "aws_alb.internal": ["aws_ecs_fargate.pooled", "aws_ecs_fargate.premium"],
    "aws_ecs_fargate.pooled": ["aws_rds_postgres.pooled"],
    "aws_ecs_fargate.premium": ["aws_rds_postgres.premium"],
}
ANNOTATIONS = {
    "format": "0.3",
    "connect": {
        "aws_alb.internal": [
            {"aws_ecs_fargate.pooled": "Shared tenants"},
            {"aws_ecs_fargate.premium": "Premium tenant"},
        ],
        "aws_ecs_fargate.pooled": [{"aws_rds_postgres.pooled": "Pooled schema"}],
        "aws_ecs_fargate.premium": [{"aws_rds_postgres.premium": "Own cluster"}],
    },
}


def test_each_arrow_keeps_its_own_label(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "g.tvg.json").write_text(json.dumps(GRAPH))
    (tmp_path / "a.yml").write_text(yaml.safe_dump(ANNOTATIONS))
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", "g.tvg.json", "--annotate", "a.yml",
         "--format", "svg", "--outfile", "out"],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    svg = next(tmp_path.glob("out*.svg")).read_text()
    for label in ("Shared tenants", "Premium tenant", "Pooled schema", "Own cluster"):
        assert svg.count(label) == 1, label


def test_an_unlabelled_arrow_borrows_no_label(tmp_path, monkeypatch):
    graph = dict(GRAPH)
    graph["aws_alb.internal"] = GRAPH["aws_alb.internal"] + ["aws_ecs_fargate.admin"]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "g.tvg.json").write_text(json.dumps(graph))
    (tmp_path / "a.yml").write_text(yaml.safe_dump(ANNOTATIONS))
    result = CliRunner().invoke(
        cli,
        ["draw", "--source", "g.tvg.json", "--annotate", "a.yml",
         "--format", "svg", "--outfile", "out"],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    svg = next(tmp_path.glob("out*.svg")).read_text()
    assert svg.count("Premium tenant") == 1
    assert svg.count("Shared tenants") == 1
