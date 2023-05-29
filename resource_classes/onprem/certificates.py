from . import _OnPrem


class _Certificates(_OnPrem):
    _type = "certificates"
    _icon_dir = "resource_images/onprem/certificates"


class CertManager(_Certificates):
    _icon = "cert-manager.png"


class LetsEncrypt(_Certificates):
    _icon = "lets-encrypt.png"


# Aliases
