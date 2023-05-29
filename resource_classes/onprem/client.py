from . import _OnPrem


class _Client(_OnPrem):
    _type = "client"
    _icon_dir = "resource_images/onprem/client"


class Client(_Client):
    _icon = "client.png"


class User(_Client):
    _icon = "user.png"


class Users(_Client):
    _icon = "users.png"


# Aliases
