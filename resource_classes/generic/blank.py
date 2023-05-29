from . import _Generic


class _Blank(_Generic):
    _type = "blank"
    _icon_dir = "resource_images/generic/blank"


class Blank(_Blank):
    _icon = "blank.png"


# Aliases
