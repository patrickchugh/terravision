"""Regression tests for issue #295: every module call gets its .tf attributes.

The .tf files of a module folder are parsed once. When the folder was called
several times, only the first call got the attributes (and with them the
references that links are built from), and for_each or count instances of a
call never found them because their addresses carry a key the files lack.
"""

import os

import pytest

from modules import interpreter

MODULE_DIR = os.path.join(os.sep, "project", "modules", "bucket")
MODULE_FILE = os.path.join(MODULE_DIR, "main.tf")


def _tfdata(module_source_dict):
    return {
        "module_source_dict": module_source_dict,
        "all_resource": {
            MODULE_FILE: [
                {"aws_s3_bucket": {"this": {"bucket": "${var.name}"}}},
                {
                    "aws_s3_bucket_versioning": {
                        "this": {"bucket": "${aws_s3_bucket.this.id}"}
                    }
                },
            ]
        },
    }


def test_every_call_of_a_module_folder_gets_its_own_copy():
    tfdata = interpreter.prefix_module_names(
        _tfdata({"shared": MODULE_DIR, "per_team": MODULE_DIR})
    )
    names = {
        name
        for element in tfdata["all_resource"][MODULE_FILE]
        for value in element.values()
        for name in value
    }
    assert names == {
        "module.shared.aws_s3_bucket.this",
        "module.shared.aws_s3_bucket_versioning.this",
        "module.per_team.aws_s3_bucket.this",
        "module.per_team.aws_s3_bucket_versioning.this",
    }


def test_copies_are_independent():
    tfdata = interpreter.prefix_module_names(
        _tfdata({"shared": MODULE_DIR, "per_team": MODULE_DIR})
    )
    elements = tfdata["all_resource"][MODULE_FILE]
    shared = next(e for e in elements if "module.shared.aws_s3_bucket.this" in str(e))
    shared["aws_s3_bucket"]["module.shared.aws_s3_bucket.this"]["bucket"] = "x"
    per_team = next(
        e for e in elements if "module.per_team.aws_s3_bucket.this" in str(e)
    )
    assert (
        per_team["aws_s3_bucket"]["module.per_team.aws_s3_bucket.this"]["bucket"]
        == "${var.name}"
    )


def test_running_twice_does_not_duplicate():
    tfdata = _tfdata({"shared": MODULE_DIR, "per_team": MODULE_DIR})
    once = len(interpreter.prefix_module_names(tfdata)["all_resource"][MODULE_FILE])
    twice = len(interpreter.prefix_module_names(tfdata)["all_resource"][MODULE_FILE])
    assert once == twice == 4


def test_only_the_most_specific_module_folder_counts():
    module_source_dict = {
        "bucket": MODULE_DIR,
        "bucket_logs": MODULE_DIR + "_logs",
        "inner": os.path.join(MODULE_DIR, "inner"),
    }
    assert interpreter._module_calls_for_file(MODULE_FILE, module_source_dict) == [
        "bucket"
    ]
    inner_file = os.path.join(MODULE_DIR, "inner", "main.tf")
    assert interpreter._module_calls_for_file(inner_file, module_source_dict) == [
        "inner"
    ]


@pytest.mark.parametrize(
    "node, expected",
    [
        (
            'module.per_team["a"].aws_s3_bucket.this',
            "module.per_team.aws_s3_bucket.this",
        ),
        (
            'module.per_team["a.b"].aws_s3_bucket.this[0]',
            "module.per_team.aws_s3_bucket.this[0]",
        ),
        (
            "module.app[0].module.db.aws_db_instance.this",
            "module.app.module.db.aws_db_instance.this",
        ),
        ('aws_s3_bucket.this["a"]', 'aws_s3_bucket.this["a"]'),
    ],
)
def test_without_module_keys(node, expected):
    assert interpreter.without_module_keys(node) == expected
