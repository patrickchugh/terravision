from . import _AWS


class _Devtools(_AWS):
    _type = "devtools"
    _icon_dir = "resource_images/aws/devtools"


class CloudDevelopmentKit(_Devtools):
    _icon = "cloud-development-kit.png"


class Cloud9(_Devtools):
    _icon = "cloud9.png"


class Codebuild(_Devtools):
    _icon = "codebuild.png"


class Codecommit(_Devtools):
    _icon = "codecommit.png"


class Codedeploy(_Devtools):
    _icon = "codedeploy.png"


class Codepipeline(_Devtools):
    _icon = "codepipeline.png"


class Codestar(_Devtools):
    _icon = "codestar.png"


class CommandLineInterface(_Devtools):
    _icon = "command-line-interface.png"


class DeveloperTools(_Devtools):
    _icon = "developer-tools.png"


class ToolsAndSdks(_Devtools):
    _icon = "tools-and-sdks.png"


class XRay(_Devtools):
    _icon = "x-ray.png"


# Aliases

CLI = CommandLineInterface
DevTools = DeveloperTools

# Terraform Resource mappings
aws_cloud9_environment_ec2 = Cloud9
aws_codebuild_project = Codebuild
aws_codecommit_repository = Codecommit
aws_codedeploy_app = Codedeploy
aws_codepipeline = Codepipeline
aws_codestarconnections_connection = Codestar
aws_xray_group = XRay
