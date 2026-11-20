"""Regression tests for issue #294: references scoped to their module instance.

A plain reference such as ``aws_s3_bucket.this``, written inside a module,
means the resource in that same module instance. Matching used to accept any
node whose name contained the reference, so when one module folder was called
several times, a resource in one call linked to the matching resource in every
other call. On large roots the extra edges stalled the draw.
"""

import pytest

from modules import graphmaker, helpers

BUCKETS = [
    "module.shared.aws_s3_bucket.this",
    'module.per_team["a"].aws_s3_bucket.this',
    'module.per_team["b"].aws_s3_bucket.this',
    "module.other_call.aws_s3_bucket.this",
]
VERSIONING = [b.replace("aws_s3_bucket.", "aws_s3_bucket_versioning.") for b in BUCKETS]
NODES = BUCKETS + VERSIONING
REFERENCE = "${aws_s3_bucket.this.id}"


@pytest.mark.parametrize(
    "source, expected",
    [
        pytest.param(
            'module.per_team["a"].aws_s3_bucket_versioning.this',
            ['module.per_team["a"].aws_s3_bucket.this'],
            id="for_each-instance",
        ),
        pytest.param(
            "module.shared.aws_s3_bucket_versioning.this",
            ["module.shared.aws_s3_bucket.this"],
            id="plain-call",
        ),
    ],
)
def test_reference_matches_only_its_own_module_instance(source, expected):
    assert graphmaker._find_matching_resources(REFERENCE, NODES, source) == expected


def test_top_level_reference_prefers_top_level_resource():
    nodes = NODES + ["aws_s3_bucket.this", "aws_s3_bucket_policy.this"]
    matching = graphmaker._find_matching_resources(
        REFERENCE, nodes, "aws_s3_bucket_policy.this"
    )
    assert matching == ["aws_s3_bucket.this"]


def test_falls_back_when_module_instance_has_no_match():
    """A root resource passed in through a module variable still resolves."""
    nodes = ["aws_kms_key.main", 'module.per_team["a"].aws_s3_bucket.this']
    matching = graphmaker._find_matching_resources(
        "${aws_kms_key.main.arn}", nodes, 'module.per_team["a"].aws_s3_bucket.this'
    )
    assert matching == ["aws_kms_key.main"]


def test_explicit_module_reference_is_not_scoped():
    nodes = ["module.vpc.aws_subnet.private", "aws_instance.web"]
    matching = graphmaker._find_matching_resources(
        "${module.vpc.aws_subnet.private.id}", nodes, "aws_instance.web"
    )
    assert "module.vpc.aws_subnet.private" in matching


@pytest.mark.parametrize(
    "node, expected",
    [
        ("aws_s3_bucket.this", ""),
        ("data.aws_vpc.main", ""),
        ("module.shared.aws_s3_bucket.this", "module.shared"),
        ('module.per_team["a.b"].aws_s3_bucket.this', 'module.per_team["a.b"]'),
        ("module.app[0].module.db.aws_db_instance.this~1", "module.app[0].module.db"),
    ],
)
def test_module_address(node, expected):
    assert helpers.module_address(node) == expected


def test_add_relations_links_each_call_to_its_own_bucket():
    """End to end: no versioning resource links to another call's bucket."""
    tfdata = {
        "graphdict": {n: [] for n in NODES},
        "node_list": list(NODES),
        "meta_data": {v: {"bucket": REFERENCE} for v in VERSIONING},
        "original_metadata": {n: {} for n in NODES},
        "hidden": [],
        "provider_detection": {"primary_provider": "aws", "providers": ["aws"]},
    }
    graphdict = graphmaker.add_relations(tfdata)["graphdict"]

    for versioning, bucket in zip(VERSIONING, BUCKETS):
        linked = set(graphdict[versioning]) | {
            n for n, targets in graphdict.items() if versioning in targets
        }
        assert bucket in linked, f"{versioning} lost its own bucket"
        assert not linked & (set(BUCKETS) - {bucket}), (
            f"{versioning} linked to another module call's bucket: "
            f"{sorted(linked & (set(BUCKETS) - {bucket}))}"
        )
