from . import _OnPrem


class _Compute(_OnPrem):
    _type = "compute"
    _icon_dir = "resource_images/onprem/compute"


class Nomad(_Compute):
    _icon = "nomad.png"


class Server(_Compute):
    _icon = "server.png"


# Aliases
