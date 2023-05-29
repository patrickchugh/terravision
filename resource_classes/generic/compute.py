from . import _Generic


class _Compute(_Generic):
    _type = "compute"
    _icon_dir = "resource_images/generic/compute"


class Rack(_Compute):
    _icon = "rack.png"


# Aliases
