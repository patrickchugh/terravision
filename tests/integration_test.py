import filecmp
import subprocess
import os
import json

def test_help():
    result = subprocess.run(["terravision", "--help"], stdout=subprocess.PIPE)
    assert "Terravision" in result.stdout.decode("utf-8") and result.returncode == 0


def verify_json_output(result_file, github_repo, var_file):
    output_file = 'result.json'
    result = subprocess.run(
        [
            "terravision", "graphdata",
            "--source", github_repo,
            "--varfile", var_file,
            "--outfile", output_file,
        ],
        stdout=subprocess.PIPE,
    )
    assert result.returncode == 0
    assert os.path.isfile(output_file)
    with open(output_file) as json_file:
        result = json.load(json_file)


    with open(result_file) as json_file:
        expected = json.load(json_file)
    assert result == expected


def test_wordpress_fargate():
    expected_file = f"{os.getcwd()}/tests/testcase-wordpress.json"
    github_repo = "https://github.com/futurice/terraform-examples.git//aws/wordpress_fargate"
    var_file = "examples/variables.tfvars"
    verify_json_output(expected_file, github_repo, var_file)


def test_static_site():
    expected_file = f"{os.getcwd()}/tests/testcase-aws-static-site.json"
    github_repo = "https://github.com/futurice/terraform-examples.git//aws/aws_static_site"
    var_file = "examples/variables.tfvars"
    verify_json_output(expected_file, github_repo, var_file)
