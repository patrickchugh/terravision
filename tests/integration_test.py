"""Integration tests for TerraVision CLI tool.

Tests the main commands (draw, graphdata) against real Terraform examples
from the GitHub repository to ensure end-to-end functionality.

Includes multi-cloud provider tests for AWS, Azure, and GCP (Phase 7).
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
    # Use the installed terravision binary from the virtualenv
    # Find the virtualenv's bin directory
    venv_bin = Path(PARENT_DIR) / ".venv" / "bin" / "terravision"

    # If .venv doesn't exist, try Poetry's cache location
    if not venv_bin.exists():
        # Get Poetry's virtualenv path
        result = subprocess.run(
            ["poetry", "env", "info", "--path"],
            capture_output=True,
            text=True,
            cwd=str(PARENT_DIR),
        )
        if result.returncode == 0:
            venv_path = Path(result.stdout.strip())
            venv_bin = venv_path / "bin" / "terravision"

    # Use the terravision binary directly (doesn't require pyproject.toml in cwd)
    if venv_bin.exists():
        cmd = [str(venv_bin)] + args
    else:
        # Fallback to poetry run if binary not found
        cmd = ["poetry", "run", "terravision"] + args

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
            str(local_json),
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


@pytest.mark.parametrize(
    "json_path,expected_provider,expected_resources",
    [
        (
            "azure-basic-tfdata.json",
            "azurerm",
            [
                "azurerm_resource_group.main",
                "azurerm_virtual_network.main",
                "azurerm_subnet.internal",
                "azurerm_network_interface.main",
                "azurerm_linux_virtual_machine.main",
            ],
        ),
        (
            "gcp-basic-tfdata.json",
            "google",
            [
                "google_compute_network.main",
                "google_compute_subnetwork.main",
                "google_compute_firewall.allow_ssh",
                "google_compute_instance.main",
            ],
        ),
    ],
)
def test_multi_cloud_provider_detection(
    json_path: str,
    expected_provider: str,
    expected_resources: List[str],
    tmp_path: Path,
) -> None:
    """Test multi-cloud provider detection for Azure and GCP (Phase 7).

    Validates that TerraVision correctly detects Azure and GCP providers
    and processes their resources through the provider abstraction layer.

    This test verifies:
    - Provider detection from Terraform JSON
    - Resource extraction and processing
    - Graph data generation with provider-specific configurations

    Args:
        json_path: Path to the test Terraform plan JSON file
        expected_provider: Expected provider ID (azurerm or google)
        expected_resources: List of expected resource addresses
        tmp_path: Pytest fixture providing temporary directory
    """
    local_json = JSON_DIR / json_path
    output_file = tmp_path / "output.json"

    # Execute graphdata command
    result = run_terravision(
        [
            "graphdata",
            "--source",
            str(local_json),
            "--outfile",
            output_file.name,
            "--debug",
        ],
        cwd=str(tmp_path),
    )

    # Command should succeed
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert output_file.exists(), f"Output file not created: {output_file}"

    # Load and validate output
    # Note: graphdata command outputs only the graphdict, not full tfdata
    with open(output_file) as f:
        graphdict = json.load(f)

    # Validate graph dictionary structure (graphdata outputs graphdict only)
    assert isinstance(graphdict, dict), "Output should be a dictionary"
    assert len(graphdict) > 0, "graphdict is empty"

    # Validate expected resources exist in graph
    graph_nodes = list(graphdict.keys())
    for expected_resource in expected_resources:
        assert expected_resource in graph_nodes, (
            f"Expected resource {expected_resource} not found in graph. "
            f"Available: {graph_nodes}"
        )

    # Validate provider prefix is correct (all resources should have provider prefix)
    for node in graph_nodes:
        assert node.startswith(expected_provider + "_"), (
            f"Resource {node} does not have expected provider prefix {expected_provider}_"
        )

    print(f"✓ {expected_provider} provider test passed:")
    print(f"  - Detected {len(graph_nodes)} resources with {expected_provider} prefix")
    print(f"  - All expected resources found in graph")
    print(f"  - Graph has {sum(len(deps) for deps in graphdict.values())} total edges")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
