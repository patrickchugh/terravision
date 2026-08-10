"""Reference matching when provider-assigned ids are unknown.

terravision forces a local backend (see tfwrapper._write_override) so the plan
runs against empty state and reports every resource as to-be-created. That is
deliberate - it is how a diagram shows the whole architecture rather than the
delta - but it means provider-assigned values are almost never available:
across the test corpus only 21% of ids and 23% of arns are concrete, while 92%
of names are, because names are usually written in the config.

So the greenfield case is not an edge case, it is the normal one, and these
tests model it: ids arrive as the "(known after apply)" marker and the only
evidence of which instance is meant is the HCL expression naming it.

The exception, covered by test_hardcoded_parent_id_still_matches, is an AWS
resource pointing at a pre-existing VPC by literal id - that value IS in the
plan, and matching on it must keep working.
"""

import pytest

from modules.graphmaker import _identify_instance, _is_concrete


# ---------------------------------------------------------------------------
# _is_concrete: what counts as usable evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected,why",
    [
        ("vpc-0prod", True, "a real resolved value"),
        ("/subscriptions/x/virtualNetworks/vnet-a", True, "an ARM id"),
        (True, False, "'(known after apply)' as the raw plan boolean"),
        ("True", False, "the same marker after variable resolution stringifies it"),
        ("${aws_vpc.this.id}", False, "an unresolved interpolation"),
        ('"" ', False, "a variable that could not be resolved"),
        ("   ", False, "whitespace only"),
        ("", False, "empty"),
    ],
)
def test_is_concrete(value, expected, why):
    assert _is_concrete(value) is expected, why


# ---------------------------------------------------------------------------
# Rule 1: the HCL reference names its target exactly
# ---------------------------------------------------------------------------


def _greenfield(source_reference):
    """Two candidate parents whose ids are all "(known after apply)"."""
    candidates = ['aws_vpc.this["prod"]', 'aws_vpc.this["dev"]']
    return candidates, {
        # plan view: nothing usable, exactly as a greenfield plan reports it
        "original_metadata": {
            'aws_vpc.this["prod"]': {"id": True},
            'aws_vpc.this["dev"]': {"id": True},
            "aws_subnet.web": {"vpc_id": True},
        },
        # HCL view: the expression naming the instance
        "meta_data": {
            'aws_vpc.this["prod"]': {},
            'aws_vpc.this["dev"]': {},
            "aws_subnet.web": {"vpc_id": source_reference},
        },
    }


def test_reference_identifies_instance_when_every_id_is_unknown():
    """The normal terravision case: no ids at all, only the expression."""
    candidates, tfdata = _greenfield('${aws_vpc.this["prod"].id}')

    assert _identify_instance(candidates, "aws_subnet.web", None, tfdata) == (
        'aws_vpc.this["prod"]'
    )


def test_reference_to_the_other_instance_picks_the_other_one():
    candidates, tfdata = _greenfield('${aws_vpc.this["dev"].id}')

    assert _identify_instance(candidates, "aws_subnet.web", None, tfdata) == (
        'aws_vpc.this["dev"]'
    )


def test_unkeyed_reference_stays_ambiguous():
    """`terraform show -json` normalises this[each.key] to the base address.

    That names no instance, so nothing may be guessed.
    """
    candidates, tfdata = _greenfield("${aws_vpc.this.id}")

    assert _identify_instance(candidates, "aws_subnet.web", None, tfdata) is None


def test_known_after_apply_marker_never_matches():
    """The string "True" must not be treated as a value shared by both sides."""
    candidates = ['aws_vpc.this["prod"]', 'aws_vpc.this["dev"]']
    tfdata = {
        "original_metadata": {
            'aws_vpc.this["prod"]': {"id": "True"},
            'aws_vpc.this["dev"]': {"id": "True"},
            "aws_subnet.web": {"vpc_id": "True"},
        },
        "meta_data": {},
    }

    assert _identify_instance(candidates, "aws_subnet.web", None, tfdata) is None


# ---------------------------------------------------------------------------
# Rule 2: a literal id in the config - the case that still resolves by id
# ---------------------------------------------------------------------------


def test_hardcoded_parent_id_still_matches():
    """An AWS subnet pointing at a pre-existing VPC by literal id.

    Seen in the field where the VPC is not managed by the same configuration,
    so its id is a plain string in the plan rather than "(known after apply)".
    Matching on it must keep working.
    """
    candidates = ["aws_vpc.imported", 'aws_vpc.this["dev"]']
    tfdata = {
        "original_metadata": {
            "aws_vpc.imported": {"id": "vpc-0abc123hardcoded"},
            'aws_vpc.this["dev"]': {"id": True},
            "aws_subnet.web": {"vpc_id": "vpc-0abc123hardcoded"},
        },
        "meta_data": {},
    }

    assert _identify_instance(candidates, "aws_subnet.web", None, tfdata) == (
        "aws_vpc.imported"
    )


def test_plan_value_wins_over_the_hcl_expression():
    """Where both views have something, the resolved value is the better one."""
    candidates = ["aws_vpc.imported", "aws_vpc.other"]
    tfdata = {
        "original_metadata": {
            "aws_vpc.imported": {"id": "vpc-real"},
            "aws_vpc.other": {"id": "vpc-other"},
            "aws_subnet.web": {"vpc_id": "vpc-real"},
        },
        "meta_data": {
            # stale/unresolvable expression pointing elsewhere
            "aws_subnet.web": {"vpc_id": "${aws_vpc.other.id}"},
        },
    }

    assert _identify_instance(candidates, "aws_subnet.web", None, tfdata) == (
        "aws_vpc.imported"
    )
