from . import _OnPrem


class _Aggregator(_OnPrem):
    _type = "aggregator"
    _icon_dir = "resource_images/onprem/aggregator"


class Fluentd(_Aggregator):
    _icon = "fluentd.png"


class Vector(_Aggregator):
    _icon = "vector.png"


# Aliases
