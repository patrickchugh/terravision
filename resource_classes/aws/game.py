from . import _AWS


class _Game(_AWS):
    _type = "game"
    _icon_dir = "resource_images/aws/game"


class Gamelift(_Game):
    _icon = "gamelift.png"


# Aliases
aws_gamelift_build = Gamelift
