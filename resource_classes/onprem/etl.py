from . import _OnPrem


class _Etl(_OnPrem):
    _type = "etl"
    _icon_dir = "resource_images/onprem/etl"


class Embulk(_Etl):
    _icon = "embulk.png"


# Aliases
