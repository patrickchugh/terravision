from . import _OnPrem


class _Cd(_OnPrem):
    _type = "cd"
    _icon_dir = "resource_images/onprem/cd"


class Spinnaker(_Cd):
    _icon = "spinnaker.png"


class TektonCli(_Cd):
    _icon = "tekton-cli.png"


class Tekton(_Cd):
    _icon = "tekton.png"


# Aliases
