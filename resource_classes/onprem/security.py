from . import _OnPrem


class _Security(_OnPrem):
    _type = "security"
    _icon_dir = "resource_images/onprem/security"


class Bitwarden(_Security):
    _icon = "bitwarden.png"


class Trivy(_Security):
    _icon = "trivy.png"


class Vault(_Security):
    _icon = "vault.png"


# Aliases
