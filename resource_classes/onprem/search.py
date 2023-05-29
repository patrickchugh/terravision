from . import _OnPrem


class _Search(_OnPrem):
    _type = "search"
    _icon_dir = "resource_images/onprem/search"


class Solr(_Search):
    _icon = "solr.png"


# Aliases
