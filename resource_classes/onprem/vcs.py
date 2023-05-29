from . import _OnPrem


class _Vcs(_OnPrem):
    _type = "vcs"
    _icon_dir = "resource_images/onprem/vcs"


class Git(_Vcs):
    _icon = "git.png"


class Github(_Vcs):
    _icon = "github.png"


class Gitlab(_Vcs):
    _icon = "gitlab.png"


# Aliases
