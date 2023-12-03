import subprocess
import os
import json
from pathlib import Path


base_repo = "https://github.com/patrickchugh/terraform-examples.git"


def test_help():
    result = subprocess.run(["terravision", "--help"], stdout=subprocess.PIPE)
    assert "Terravision" in result.stdout.decode("utf-8") and result.returncode == 0


def verify_json_output(github_repo, expected_output):
    output_file = os.path.join(Path.cwd(), "output.json")
    result = subprocess.run(
        [
            "terravision",
            "graphdata",
            "--source",
            github_repo,
            "--outfile",
            output_file,
        ],
        stdout=subprocess.PIPE,
    )
    assert result.returncode == 0
    assert os.path.exists(output_file)
    o_json_file = open(output_file)
    result = json.load(o_json_file)
    e_json_file = open(expected_output)
    expected = json.load(e_json_file)
    os.remove(output_file)
    assert result == expected


def test_wordpress_fargate():
    github_repo = f"{base_repo}//aws/wordpress_fargate"
    expected_output = os.path.join(Path.cwd(), "tests", "testcase-wordpress.json")
    verify_json_output(github_repo, expected_output)
