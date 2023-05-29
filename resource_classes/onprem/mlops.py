from . import _OnPrem


class _Mlops(_OnPrem):
    _type = "mlops"
    _icon_dir = "resource_images/onprem/mlops"


class Polyaxon(_Mlops):
    _icon = "polyaxon.png"


# Aliases
