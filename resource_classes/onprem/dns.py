from . import _OnPrem


class _Dns(_OnPrem):
    _type = "dns"
    _icon_dir = "resource_images/onprem/dns"


class Coredns(_Dns):
    _icon = "coredns.png"


class Powerdns(_Dns):
    _icon = "powerdns.png"


# Aliases
