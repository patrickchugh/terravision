from . import _GCP


class _Iot(_GCP):
    _type = "iot"
    _icon_dir = "resources/gcp/iot"


class IotCore(_Iot):
    _icon = "iot-core.png"


# Aliases

# Terraform aliases
google_cloudiot_registry = IotCore
google_cloudiot_device = IotCore
