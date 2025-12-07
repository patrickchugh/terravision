from . import _AWS


class _Game(_AWS):
    _type = "game"
    _icon_dir = "resource_images/aws/game"


class Gamelift(_Game):
    _icon = "gamelift.png"


# Aliases

# Terraform aliases
aws_gamelift_build = Gamelift
aws_gamelift_fleet = Gamelift
aws_gamelift_alias = Gamelift
