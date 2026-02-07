"""Validation tests to ensure graph output quality.

These tests validate that generated graphs meet quality standards and don't
have common issues that cause rendering problems or inaccurate diagrams.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

from modules.helpers import validate_graphdict, validate_no_shared_connections


JSON_DIR = Path(__file__).parent / "json"


@pytest.mark.parametrize(
    "expected_file",
    [
        "expected-wordpress.json",
        "bastion-expected.json",
        "expected-eks-basic.json",
        "expected-static-website.json",
        "expected-api-gateway-rest-lambda.json",
        "expected-eventbridge-lambda.json",
        "expected-sns-sqs-lambda.json",
        "expected-dynamodb-streams-lambda.json",
        "expected-elasticache-redis.json",
        "expected-elasticache-replication.json",
        "expected-cognito-api-gateway.json",
        "expected-waf-alb.json",
        "expected-module-sources.json",
    ],
)
def test_no_shared_connections_in_expected_outputs(expected_file: str) -> None:
    """Validate that expected outputs have no shared connections between groups.

    This test ensures that when multiple groups (subnets, AZs) connect to the
    same resource, that resource has been properly expanded into numbered
    instances (~1, ~2, etc.) to avoid graphviz rendering issues.

    CRITICAL: This test should NEVER be skipped or modified to pass.
    If this test fails, it means:
    1. The expected output has a rendering issue that needs fixing
    2. OR the resource handler needs to expand resources into numbered instances
    3. Expected JSON should NOT be regenerated to make this pass

    Args:
        expected_file: Expected JSON output file to validate
    """
    expected_path = JSON_DIR / expected_file

    # Load expected graphdict
    with open(expected_path) as f:
        graphdict = json.load(f)

    # Create minimal tfdata with provider detection
    # This is needed for validation to load provider-specific GROUP_NODES
    tfdata = {
        "graphdict": graphdict,
        "provider_detection": {
            "primary_provider": "aws",  # Most tests are AWS
            "providers": {"aws": 10},
        },
    }

    # Run validation
    is_valid, errors = validate_no_shared_connections(graphdict, tfdata)

    # If validation fails, provide detailed error message
    if not is_valid:
        error_msg = f"\n\nVALIDATION FAILED for {expected_file}:\n\n"
        error_msg += "=" * 80 + "\n"
        for error in errors:
            error_msg += f"❌ {error}\n\n"
        error_msg += "=" * 80 + "\n\n"
        error_msg += "HOW TO FIX:\n"
        error_msg += "1. DO NOT regenerate expected JSON to make this pass\n"
        error_msg += (
            "2. Identify which resource handler should expand the shared resource\n"
        )
        error_msg += "3. Add logic to create numbered instances (~1, ~2) matching parent groups\n"
        error_msg += "4. Ensure each group points to its own numbered instance\n"
        error_msg += "\nExample: If aws_subnet.a and aws_subnet.b both point to aws_instance.web,\n"
        error_msg += (
            "the handler should create aws_instance.web~1 and aws_instance.web~2\n"
        )

        pytest.fail(error_msg)


def test_validation_detects_shared_connections() -> None:
    """Test that validation correctly detects shared connection violations.

    This test ensures the validation logic itself works correctly.
    """
    # Create a test case with shared connections (violation)
    # Note: Security groups are GROUP_NODES so they're allowed to be shared
    bad_graphdict = {
        "aws_subnet.a": ["aws_instance.web", "aws_lambda_function.func"],
        "aws_subnet.b": ["aws_instance.web", "aws_lambda_function.func"],  # VIOLATION
        "aws_instance.web": [],
        "aws_lambda_function.func": [],
    }

    tfdata = {
        "graphdict": bad_graphdict,
        "provider_detection": {
            "primary_provider": "aws",
            "providers": {"aws": 4},
        },
    }

    is_valid, errors = validate_no_shared_connections(bad_graphdict, tfdata)

    assert not is_valid, "Should detect shared connections"
    assert len(errors) >= 2, "Should detect both shared resources"
    # Check that both resources are mentioned in error messages
    all_errors = " ".join(errors)
    assert "aws_instance.web" in all_errors, "Should detect aws_instance.web"
    assert (
        "aws_lambda_function.func" in all_errors
    ), "Should detect aws_lambda_function.func"


def test_validation_allows_numbered_instances() -> None:
    """Test that validation allows properly numbered instances.

    This test ensures validation doesn't flag correctly expanded resources.
    """
    # Create a test case with numbered instances (correct)
    good_graphdict = {
        "aws_subnet.a": ["aws_instance.web~1", "aws_security_group.sg~1"],
        "aws_subnet.b": ["aws_instance.web~2", "aws_security_group.sg~2"],
        "aws_instance.web~1": [],
        "aws_instance.web~2": [],
        "aws_security_group.sg~1": [],
        "aws_security_group.sg~2": [],
    }

    tfdata = {
        "graphdict": good_graphdict,
        "provider_detection": {
            "primary_provider": "aws",
            "providers": {"aws": 6},
        },
    }

    is_valid, errors = validate_no_shared_connections(good_graphdict, tfdata)

    assert is_valid, f"Should allow numbered instances, but got errors: {errors}"
    assert len(errors) == 0


def test_validation_allows_single_parent() -> None:
    """Test that validation allows resources with single parent.

    This test ensures validation doesn't flag resources with only one parent.
    """
    good_graphdict = {
        "aws_subnet.a": ["aws_instance.web", "aws_security_group.sg"],
        "aws_instance.web": [],
        "aws_security_group.sg": [],
    }

    tfdata = {
        "graphdict": good_graphdict,
        "provider_detection": {
            "primary_provider": "aws",
            "providers": {"aws": 3},
        },
    }

    is_valid, errors = validate_no_shared_connections(good_graphdict, tfdata)

    assert is_valid, f"Should allow single parent, but got errors: {errors}"
    assert len(errors) == 0
