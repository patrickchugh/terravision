import filecmp
import subprocess

def test_help():
    result = subprocess.run(["terravision", "--help"], stdout=subprocess.PIPE)
    assert "Terravision" in result.stdout.decode("utf-8") and result.returncode == 0


def test_wordpress_fargate():
    result = subprocess.run(
        [
            "terravision",
            "graphdata",
            "--source",
            "https://github.com/futurice/terraform-examples.git//aws/wordpress_fargate",
            "--varfile",
            "examples/variables.tfvars",
            "--outfile",
            "tests/architecture-wordpress.json",
        ],
        stdout=subprocess.PIPE,
    )
    assert filecmp.cmp("tests/architecture-wordpress.json", "tests/testcase-wordpress.json" )and result.returncode == 0


# def test_static_site():
#     result = subprocess.run(
#         [
#             "terravision",
#             "graphdata",
#             "--source",
#             "https://github.com/futurice/terraform-examples.git//aws/aws_static_site",
#             "--varfile",
#             "examples/variables.tfvars",
#             "--outfile",
#             "tests/architecture-static-site.json",
#         ],
#         stdout=subprocess.PIPE,
#     )
#     assert filecmp.cmp("tests/architecture-static-site.json", "tests/testcase-wordpress.json" )and result.returncode == 0
