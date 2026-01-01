"""Integration tests for TerraVision CLI tool.

Tests the main commands (draw, graphdata) against real Terraform examples
from the GitHub repository to ensure end-to-end functionality.
"""

import subprocess
import platform
import json
import pytest
from pathlib import Path
from typing import List, Optional

# Platform detection for cross-platform command execution
WINDOWS = platform.system() == "Windows"
PARENT_DIR = Path(__file__).parent.parent
BASE_REPO = "https://github.com/patrickchugh"
JSON_DIR = Path(__file__).parent / "json"


def run_terravision(
    args: List[str], cwd: Optional[str] = None
) -> subprocess.CompletedProcess:
    """Execute terravision command consistently across platforms.

    Args:
        args: Command line arguments to pass to terravision
        cwd: Working directory for command execution

    Returns:
        CompletedProcess object with stdout, stderr, and returncode
    """
    # Windows requires explicit Python invocation via Poetry and full path
    if WINDOWS:
        cmd = ["poetry", "run", "python", str(PARENT_DIR / "terravision.py")] + args
    else:
        cmd = [str(PARENT_DIR / "terravision.py")] + args

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
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
        # Phase 4: Event-Driven Architecture patterns
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
        # Phase 6: Authentication (Cognito) patterns
        (
            "cognito-api-gateway-tfdata.json",
            "expected-cognito-api-gateway.json",
        ),
        # Phase 7: WAF Security patterns
        (
            "waf-alb-tfdata.json",
            "expected-waf-alb.json",
        ),
        # Phase 8: SageMaker ML patterns
        (
            "sagemaker-endpoint-tfdata.json",
            "expected-sagemaker-endpoint.json",
        ),
        (
            "sagemaker-notebook-vpc-tfdata.json",
            "expected-sagemaker-notebook-vpc.json",
        ),
        # Phase 9: Step Functions patterns
        (
            "stepfunctions-lambda-tfdata.json",
            "expected-stepfunctions-lambda.json",
        ),
        (
            "stepfunctions-multi-service-tfdata.json",
            "expected-stepfunctions-multi-service.json",
        ),
        # Phase 10: S3 Notifications patterns
        (
            "s3-notification-lambda-tfdata.json",
            "expected-s3-notification-lambda.json",
        ),
        (
            "s3-replication-tfdata.json",
            "expected-s3-replication.json",
        ),
        # Phase 11: Secrets Manager patterns
        (
            "secretsmanager-lambda-tfdata.json",
            "expected-secretsmanager-lambda.json",
        ),
        (
            "secretsmanager-rds-tfdata.json",
            "expected-secretsmanager-rds.json",
        ),
        # Phase 12: Data Processing (Glue/Firehose) patterns
        (
            "glue-s3-tfdata.json",
            "expected-glue-s3.json",
        ),
        (
            "firehose-lambda-tfdata.json",
            "expected-firehose-lambda.json",
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


@pytest.mark.parametrize(
    "repo_path",
    ["testcase-bastion.git//examples"],
)
@pytest.mark.slow
def test_draw_command_basic(repo_path: str, tmp_path: Path) -> None:
    """Test basic draw command execution.

    Validates that the draw command successfully generates a PNG diagram
    from Terraform code in a GitHub repository.

    Args:
        tmp_path: Pytest fixture providing temporary directory
    """
    github_repo = f"{BASE_REPO}/{repo_path}"
    output_name = "test_arch"

    # Execute draw command to generate PNG diagram
    result = run_terravision(
        [
            "draw",
            "--source",
            github_repo,
            "--outfile",
            output_name,
            "--format",
            "png",
            "--debug",
        ],
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, f"Draw command failed: {result.stderr}"
    assert (tmp_path / f"{output_name}.dot.png").exists(), "PNG output not created"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
