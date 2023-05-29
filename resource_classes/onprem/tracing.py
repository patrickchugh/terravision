from . import _OnPrem


class _Tracing(_OnPrem):
    _type = "tracing"
    _icon_dir = "resource_images/onprem/tracing"


class Jaeger(_Tracing):
    _icon = "jaeger.png"


# Aliases
