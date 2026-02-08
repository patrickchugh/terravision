"""Integration tests for TerraVision CLI tool.

Tests the main commands (draw, graphdata) against real Terraform examples
from the GitHub repository to ensure end-to-end functionality.
"""

import os
import subprocess
import platform
import json
import pytest
from pathlib import Path
from typing import Dict, List, Optional

# Platform detection for cross-platform command execution
WINDOWS = platform.system() == "Windows"
PARENT_DIR = Path(__file__).parent.parent
BASE_REPO = "https://github.com/patrickchugh"
JSON_DIR = Path(__file__).parent / "json"


def assert_graphs_equal_az_independent(actual: dict, expected: dict) -> None:
    """Compare graph dicts treating AZ-to-subnet assignments as permutable.

    AWS maps logical AZ names to physical AZ IDs differently per account,
    so subnet[0] might be in euw1-az1 locally but euw1-az2 in CI.
    The graph structure is identical — each AZ has the same shape of children —
    just the specific AZ-to-subnet binding may be rotated.
    """
    az_prefix = "aws_az."

    actual_az = {k: sorted(v) for k, v in actual.items() if k.startswith(az_prefix)}
    actual_rest = {k: v for k, v in actual.items() if not k.startswith(az_prefix)}

    expected_az = {k: sorted(v) for k, v in expected.items() if k.startswith(az_prefix)}
    expected_rest = {k: v for k, v in expected.items() if not k.startswith(az_prefix)}

    assert actual_rest == expected_rest, "Non-AZ graph entries don't match"
    assert set(actual_az.keys()) == set(expected_az.keys()), "AZ node names don't match"

    # The multiset of children lists must match (AZ assignment order doesn't matter)
    actual_children = sorted(actual_az.values())
    expected_children = sorted(expected_az.values())
    assert actual_children == expected_children, (
        f"AZ-to-subnet structure doesn't match.\n"
        f"Actual AZ mapping: {actual_az}\n"
        f"Expected AZ mapping: {expected_az}"
    )


def run_terravision(
    args: List[str],
    cwd: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Execute terravision command consistently across platforms.

    Args:
        args: Command line arguments to pass to terravision
        cwd: Working directory for command execution
        extra_env: Additional environment variables to set for the subprocess

    Returns:
        CompletedProcess object with stdout, stderr, and returncode
    """
    # Windows requires explicit Python invocation via Poetry and full path
    if WINDOWS:
        cmd = ["poetry", "run", "python", str(PARENT_DIR / "terravision.py")] + args
    else:
        cmd = [str(PARENT_DIR / "terravision/terravision.py")] + args

    env = None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    return result


def test_help() -> None:
    """Test that help command executes successfully and displays usage information."""
    result = run_terravision(["--help"])
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert "terravision" in result.stdout, "Help text missing 'terravision'"


@pytest.mark.parametrize(
    "json_path,expected_file",
    [
        ("wordpress-tfdata.json", "expected-wordpress.json"),
        ("bastion-tfdata.json", "bastion-expected.json"),
        ("eks-basic-tfdata.json", "expected-eks-basic.json"),
        ("static-website-tfdata.json", "expected-static-website.json"),
        (
            "api-gateway-rest-lambda-tfdata.json",
            "expected-api-gateway-rest-lambda.json",
        ),
        # Event-Driven Architecture patterns
        (
            "eventbridge-lambda-tfdata.json",
            "expected-eventbridge-lambda.json",
        ),
        (
            "sns-sqs-lambda-tfdata.json",
            "expected-sns-sqs-lambda.json",
        ),
        (
            "dynamodb-streams-lambda-tfdata.json",
            "expected-dynamodb-streams-lambda.json",
        ),
        (
            "elasticache-redis-tfdata.json",
            "expected-elasticache-redis.json",
        ),
        (
            "elasticache-replication-tfdata.json",
            "expected-elasticache-replication.json",
        ),
        # Authentication (Cognito) patterns
        (
            "cognito-api-gateway-tfdata.json",
            "expected-cognito-api-gateway.json",
        ),
        # WAF Security patterns
        (
            "waf-alb-tfdata.json",
            "expected-waf-alb.json",
        ),
        # SageMaker ML patterns
        (
            "sagemaker-endpoint-tfdata.json",
            "expected-sagemaker-endpoint.json",
        ),
        (
            "sagemaker-notebook-vpc-tfdata.json",
            "expected-sagemaker-notebook-vpc.json",
        ),
        # Step Functions patterns
        (
            "stepfunctions-lambda-tfdata.json",
            "expected-stepfunctions-lambda.json",
        ),
        (
            "stepfunctions-multi-service-tfdata.json",
            "expected-stepfunctions-multi-service.json",
        ),
        # S3 Notifications patterns
        (
            "s3-notification-lambda-tfdata.json",
            "expected-s3-notification-lambda.json",
        ),
        (
            "s3-replication-tfdata.json",
            "expected-s3-replication.json",
        ),
        # Secrets Manager patterns
        (
            "secretsmanager-lambda-tfdata.json",
            "expected-secretsmanager-lambda.json",
        ),
        (
            "secretsmanager-rds-tfdata.json",
            "expected-secretsmanager-rds.json",
        ),
        # Data Processing (Glue/Firehose) patterns
        (
            "glue-s3-tfdata.json",
            "expected-glue-s3.json",
        ),
        (
            "firehose-lambda-tfdata.json",
            "expected-firehose-lambda.json",
        ),
        # Azure patterns
        (
            "azure-vm-vmss-tfdata.json",
            "expected-azure-vm-vmss.json",
        ),
        (
            "azure-appgw-lb-tfdata.json",
            "expected-azure-appgw-lb.json",
        ),
        (
            "azure-aks-tfdata.json",
            "expected-azure-aks.json",
        ),
        # GCP patterns
        (
            "gcp-us1-compute-tfdata.json",
            "expected-gcp-us1-compute.json",
        ),
        (
            "gcp-us2-igm-tfdata.json",
            "expected-gcp-us2-igm.json",
        ),
        (
            "gcp-us4-gke-tfdata.json",
            "expected-gcp-us4-gke.json",
        ),
        (
            "gcp-us8-vpc-tfdata.json",
            "expected-gcp-us8-vpc.json",
        ),
        # GCP Terraform Registry Module pattern
        (
            "gcp-us10-lb-http-tfdata.json",
            "expected-gcp-us10-lb-http.json",
        ),
        # GCP Three-Tier Web Application (comprehensive pattern with VPC, subnets, zones, IGM, Cloud SQL, Memorystore)
        (
            "gcp-three-tier-webapp-tfdata.json",
            "expected-gcp-three-tier-webapp.json",
        ),
    ],
)
def test_graphdata_output(json_path: str, expected_file: str, tmp_path: Path) -> None:
    """Test graphdata command generates correct JSON output.

    Validates that the graphdata command correctly parses Terraform code
    and produces JSON matching expected resource relationships.

    Args:
        repo_path: Path within the GitHub repository to test
        expected_file: Expected JSON output file for comparison
        tmp_path: Pytest fixture providing temporary directory
    """
    # Construct full GitHub repository URL with subfolder
    local_json = JSON_DIR / json_path
    expected_path = JSON_DIR / expected_file
    output_file = tmp_path / "output.json"

    # Execute graphdata command
    result = run_terravision(
        [
            "graphdata",
            "--source",
            local_json,
            "--outfile",
            output_file.name,
            "--debug",
        ],
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert output_file.exists(), f"Output file not created: {output_file}"

    # Load and compare actual vs expected JSON
    with open(output_file) as f:
        actual = json.load(f)

    with open(expected_path) as f:
        expected = json.load(f)

    assert actual == expected, "JSON output doesn't match expected"


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "aws_terraform"

# Terraform Cloud token for module source tests (read from env or use default test token)
TFC_ENV = {
    "TF_TOKEN_app_terraform_io": os.environ.get(
        "TF_TOKEN_app_terraform_io",
        "0B5XyeGU1NWJBQ.atlasv1.h3D7X0z5k3w6IDYpEsjvmMhdRJIXMsqt9VV80OdkzYXOCIlwk5v94YNOzymlQzrvFX4",
    )
}


@pytest.mark.parametrize(
    "source,expected_file",
    [
        (f"{BASE_REPO}/testcase-bastion.git//examples", "expected-bastion-live.json"),
        (f"{BASE_REPO}/testcase-bastion.git//examples", "expected-bastion-live.json"),
        (str(FIXTURES_DIR / "module_sources"), "expected-module-sources.json"),
    ],
)
@pytest.mark.slow
def test_live_source(source: str, expected_file: str, tmp_path: Path) -> None:
    """Test graphdata against live sources (git repos and local fixtures).

    The bastion source is listed twice to verify module cache correctness
    (first run downloads, second run uses cache).
    """
    expected_path = JSON_DIR / expected_file
    output_file = tmp_path / "output.json"

    with open(expected_path) as f:
        expected = json.load(f)

    result = run_terravision(
        [
            "graphdata",
            "--source",
            source,
            "--outfile",
            output_file.name,
        ],
        cwd=str(tmp_path),
        extra_env=TFC_ENV,
    )

    assert result.returncode == 0, f"graphdata failed: {result.stderr}"
    assert output_file.exists(), "Output file not created"

    with open(output_file) as f:
        actual = json.load(f)

    assert_graphs_equal_az_independent(actual, expected)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
