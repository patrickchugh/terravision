from . import _OnPrem


class _Identity(_OnPrem):
    _type = "identity"
    _icon_dir = "resource_images/onprem/identity"


class Dex(_Identity):
    _icon = "dex.png"


# Aliases
