"""Zone box names for AWS subnets (generate_az_node_name)."""

from modules.resource_handlers_aws import generate_az_node_name

UNKNOWN = {"availability_zone": True, "availability_zone_id": True}


def test_zone_id_wins_when_known():
    meta = {"availability_zone_id": "euw1-az2", "availability_zone": "eu-west-1b"}
    assert generate_az_node_name("aws_subnet.a", meta) == (
        "aws_az.availability_zone_euw1_az2"
    )


def test_zone_name_gets_its_letter_suffix():
    meta = {"availability_zone": "eu-west-1b"}
    assert generate_az_node_name("aws_subnet.a~1", meta) == (
        "aws_az.availability_zone_eu_west_1b~2"
    )


def test_numbered_subnets_with_unknown_zones_get_a_zone_each():
    """Copies spread by count.index no longer share one box named after the region."""
    meta = {**UNKNOWN, "region": "eu-west-1"}
    names = {generate_az_node_name(f"aws_subnet.private~{n}", meta) for n in (1, 2, 3)}
    assert names == {
        "aws_az.availability_zone_1~1",
        "aws_az.availability_zone_2~2",
        "aws_az.availability_zone_3~3",
    }
    # A public and a private subnet with the same index share their zone.
    assert generate_az_node_name("aws_subnet.public~2", meta) == (
        generate_az_node_name("aws_subnet.private~2", meta)
    )


def test_count_index_is_zero_based():
    meta = {**UNKNOWN, "region": "eu-west-1"}
    assert generate_az_node_name("module.vpc.aws_subnet.public[0]", meta) == (
        "aws_az.availability_zone_1~1"
    )


def test_an_unnumbered_subnet_keeps_the_region_fallback():
    meta = {**UNKNOWN, "region": "us-east-1"}
    assert generate_az_node_name("aws_subnet.local", meta) == (
        "aws_az.availability_zone_us_east_1"
    )


def test_no_zone_and_no_region_is_plain_unknown():
    """No stray letter suffix from the word "unknown" (it was "~14")."""
    assert generate_az_node_name("aws_subnet.local", {}) == (
        "aws_az.availability_zone_unknown"
    )
