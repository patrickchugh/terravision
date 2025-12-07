from . import _AWS


class _Ar(_AWS):
    _type = "ar"
    _icon_dir = "resource_images/aws/ar"


class Sumerian(_Ar):
    _icon = "sumerian.png"


# Aliases

# Terraform aliases
aws_sumerian_scene = Sumerian
