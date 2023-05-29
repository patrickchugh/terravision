from . import _OnPrem


class _Groupware(_OnPrem):
    _type = "groupware"
    _icon_dir = "resource_images/onprem/groupware"


class Nextcloud(_Groupware):
    _icon = "nextcloud.png"


# Aliases
