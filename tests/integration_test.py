import subprocess
import os
import json
import pathlib

def test_help():
    result = subprocess.run(["terravision", "--help"], stdout=subprocess.PIPE)
    assert "Terravision" in result.stdout.decode("utf-8") and result.returncode == 0

base_repo = "https://github.com/patrickchugh/terraform-examples.git"

def verify_json_output(github_repo, var_file, expected_output):
    output_file = f'{os.getcwd()}/output/result.json'
    result = subprocess.run(
        [
            "terravision", "graphdata",
            "--source", github_repo,
            "--varfile", var_file,
            "--outfile", output_file,
        ],
        stdout=subprocess.PIPE,
    )
    print(output_file)
    root = pathlib.Path("/home/runner/work/terravision/output")
    print(list(root.rglob("*")))
    assert result.returncode == 0
    assert os.path.isfile(output_file)
    with open(output_file) as json_file:
        result = json.load(json_file)
    with open(expected_output) as json_file:
        expected = json.load(json_file)
    assert result == expected


# def test_wordpress_fargate():
#     github_repo = "https://github.com/futurice/terraform-examples.git//aws/wordpress_fargate"
#     var_file = "examples/variables.tfvars"
#     expected_output = f"{os.getcwd()}/tests/testcase-wordpress.json"
#     verify_json_output(github_repo, var_file, expected_output)


def test_static_site():
    github_repo = f"{base_repo}//aws/aws_static_site"
    var_file = "examples/variables.tfvars"
    expected_output = f"{os.getcwd()}/tests/testcase-aws-static-site.json"
    verify_json_output(github_repo, var_file, expected_output)
