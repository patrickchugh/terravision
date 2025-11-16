import subprocess
import platform
import json
import pytest
from pathlib import Path

WINDOWS = platform.system() == "Windows"
PARENT_DIR = Path(__file__).parent.parent
BASE_REPO = "https://github.com/patrickchugh/terraform-examples.git"
JSON_DIR = Path(__file__).parent / "json"


def run_terravision(args, cwd=None):
    """Execute terravision command consistently across platforms."""
    if WINDOWS:
        cmd = ["poetry", "run", "python", str(PARENT_DIR / "terravision.py")] + args
    else:
        cmd = ["terravision"] + args

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result


def test_help():
    result = run_terravision(["--help"])
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert "terravision" in result.stdout, "Help text missing 'terravision'"


@pytest.mark.parametrize(
    "repo_path,expected_file",
    [
        ("aws/wordpress_fargate", "wordpress-expected.json"),
        ("aws/static_site", "static-site-expected.json"),
    ],
)
def test_graphdata_output(repo_path, expected_file, tmp_path):
    github_repo = f"{BASE_REPO}//{repo_path}"
    expected_path = JSON_DIR / expected_file
    output_file = tmp_path / "output.json"

    result = run_terravision(
        ["graphdata", "--source", github_repo, "--outfile", output_file.name],
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert output_file.exists(), f"Output file not created: {output_file}"

    with open(output_file) as f:
        actual = json.load(f)

    with open(expected_path) as f:
        expected = json.load(f)

    assert actual == expected, "JSON output doesn't match expected"


def test_draw_command_basic(tmp_path):
    """Test basic draw command execution."""
    github_repo = f"{BASE_REPO}//aws/wordpress_fargate"
    output_name = "test_arch"

    result = run_terravision(
        ["draw", "--source", github_repo, "--outfile", output_name, "--format", "png"],
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, f"Draw command failed: {result.stderr}"
    assert (tmp_path / f"{output_name}.dot.png").exists(), "PNG output not created"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
