from . import _AWS


class _Enduser(_AWS):
    _type = "enduser"
    _icon_dir = "resource_images/aws/enduser"


class Appstream20(_Enduser):
    _icon = "appstream-2-0.png"


class Workdocs(_Enduser):
    _icon = "workdocs.png"


class Worklink(_Enduser):
    _icon = "worklink.png"


class Workspaces(_Enduser):
    _icon = "workspaces.png"


# Aliases
