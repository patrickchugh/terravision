from . import _Generic


class _Place(_Generic):
    _type = "place"
    _icon_dir = "resource_images/generic/place"


class Datacenter(_Place):
    _icon = "datacenter.png"


# Aliases
