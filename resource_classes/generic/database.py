from . import _Generic


class _Database(_Generic):
    _type = "database"
    _icon_dir = "resource_images/generic/database"


class SQL(_Database):
    _icon = "sql.png"


# Aliases
