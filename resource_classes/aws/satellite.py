from . import _AWS


class _Satellite(_AWS):
    _type = "satellite"
    _icon_dir = "resource_images/aws/satellite"


class GroundStation(_Satellite):
    _icon = "ground-station.png"


# Aliases
