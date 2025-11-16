import subprocess
import platform
import os
import json
import sys
from pathlib import Path

# Static globals
WINDOWS = platform.system() == "Windows"
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
BASE_REPO = "https://github.com/patrickchugh/terraform-examples.git"
BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))


def test_help():
    if WINDOWS:
        result = subprocess.run(
            ["poetry", "run", "python", f"{PARENT_DIR}/terravision-ai", "--help"],
            stdout=subprocess.PIPE,
        )
    else:
        result = subprocess.run(["terravision", "--help"], stdout=subprocess.PIPE)
    assert "terravision" in result.stdout.decode("utf-8") and result.returncode == 0


def verify_json_output(github_repo, expected_output):
    output_file = os.path.join(BASE_DIR, "output.json")
    if WINDOWS:
        os.system(
            f"poetry run python {PARENT_DIR}/terravision graphdata --source {github_repo} --outfile {output_file}"
        )
    else:
        os.system(
            f"terravision graphdata --source {github_repo} --outfile {output_file}"
        )
    assert os.path.exists(output_file)
    o_json_file = open(output_file)
    result = json.load(o_json_file)
    e_json_file = open(expected_output)
    expected = json.load(e_json_file)
    assert result == expected
    o_json_file.close()
    os.remove(output_file)


def test_wordpress_fargate():
    github_repo = f"{BASE_REPO}//aws/wordpress_fargate"
    expected_output = os.path.join(BASE_DIR, "testcase-wordpress.json")
    verify_json_output(github_repo, expected_output)
