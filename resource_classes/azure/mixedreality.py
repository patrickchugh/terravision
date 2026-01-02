from . import _Azure


class _Mixedreality(_Azure):
    _type = "mixedreality"
    _icon_dir = "resource_images/azure/mixedreality"


class RemoteRendering(_Mixedreality):
    _icon = "remote-rendering.png"


class SpatialAnchorAccounts(_Mixedreality):
    _icon = "spatial-anchor-accounts.png"


# Aliases
