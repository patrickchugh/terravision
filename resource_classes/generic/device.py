from . import _Generic


class _Device(_Generic):
    _type = "device"
    _icon_dir = "resource_images/generic/device"


class Mobile(_Device):
    _icon = "mobile.png"


class Tablet(_Device):
    _icon = "tablet.png"


# Aliases
tv_aws_device = Tablet
