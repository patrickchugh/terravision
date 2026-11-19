"""Terraform graph links reach for_each and count module instances (#298).

terraform graph names a resource once per module call
(module.per_team.aws_s3_bucket.this); the plan names each instance
(module.per_team["a"].aws_s3_bucket.this). Each link applies inside every
instance, and never from one instance to another.
"""

import pytest

from modules import helpers, tfwrapper

BUCKET = "aws_s3_bucket.this"
VERSIONING = "aws_s3_bucket_versioning.this"


def _tfdata(nodes):
    labels = [f"module.per_team.{VERSIONING}", f"module.per_team.{BUCKET}"]
    labels += [f"module.shared.{VERSIONING}", f"module.shared.{BUCKET}"]
    return {
        "graphdict": {n: [] for n in nodes},
        "tfgraph": {
            "objects": [
                {"_gvid": i, "name": label, "label": label}
                for i, label in enumerate(labels)
            ],
            # versioning depends on bucket, in both calls
            "edges": [{"head": 0, "tail": 1}, {"head": 2, "tail": 3}],
        },
    }


def test_edges_apply_inside_each_instance():
    nodes = [
        f'module.per_team["a"].{VERSIONING}',
        f'module.per_team["a"].{BUCKET}',
        f'module.per_team["b"].{VERSIONING}',
        f'module.per_team["b"].{BUCKET}',
        f"module.shared.{VERSIONING}",
        f"module.shared.{BUCKET}",
    ]
    tfdata = _tfdata(nodes)
    gvid_table = tfwrapper._build_gvid_table(tfdata)
    tfwrapper._process_edges(tfdata, gvid_table, [])
    graph = tfdata["graphdict"]
    assert graph[f'module.per_team["a"].{VERSIONING}'] == [
        f'module.per_team["a"].{BUCKET}'
    ]
    assert graph[f'module.per_team["b"].{VERSIONING}'] == [
        f'module.per_team["b"].{BUCKET}'
    ]
    assert graph[f"module.shared.{VERSIONING}"] == [f"module.shared.{BUCKET}"]


@pytest.mark.parametrize(
    "graph_name, node, expected",
    [
        (
            f"module.per_team.{BUCKET}",
            f'module.per_team["a"].{VERSIONING}',
            f'module.per_team["a"].{BUCKET}',
        ),
        (
            f"module.app.module.db.{BUCKET}",
            f"module.app[0].module.db.{VERSIONING}",
            f"module.app[0].module.db.{BUCKET}",
        ),
        (
            f"module.shared.{BUCKET}",
            f"module.shared.{VERSIONING}",
            f"module.shared.{BUCKET}",
        ),
        ("aws_iam_role.x", f'module.per_team["a"].{VERSIONING}', "aws_iam_role.x"),
        (
            f"module.other.{BUCKET}",
            f'module.per_team["a"].{VERSIONING}',
            f"module.other.{BUCKET}",
        ),
    ],
)
def test_in_same_instance(graph_name, node, expected):
    assert tfwrapper._in_same_instance(graph_name, node) == expected


@pytest.mark.parametrize(
    "node, expected",
    [
        ("aws_s3_bucket.this[0]~1", True),
        ('aws_s3_bucket.this["k"]', True),
        ('module.per_team["a"].aws_s3_bucket.this', False),
        ('module.per_team["a"].aws_s3_bucket.this[0]', True),
        ("aws_s3_bucket.this", False),
    ],
)
def test_has_own_index(node, expected):
    assert helpers.has_own_index(node) is expected
