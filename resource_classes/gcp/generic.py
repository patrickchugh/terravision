"""
GCP Generic Icons category - All synthentic TV nodes.

Icon Resolution:
- All generic resources: resource_images/gcp/generic/web3.png
"""

from . import _GCP


class _Generic(_GCP):
    _type = "generic"
    _icon_dir = "resource_images/gcp/generic"


class Users(_Generic):
    _icon = "users.png"


# Systems outside Google Cloud, such as on-premises servers in a
# tv_gcp_onprem box. Google's icon set has no plain server or workstation, so
# these use the neutral generic icons, drawn on Google Cloud's node cards.
class OnPremServer(_GCP):
    _type = "generic"
    _icon_dir = "resource_images/generic/compute"
    _icon = "rack.png"


class OnPremClient(_GCP):
    _type = "generic"
    _icon_dir = "resource_images/onprem/client"
    _icon = "client.png"


class OnPremDatabase(_GCP):
    _type = "generic"
    _icon_dir = "resource_images/generic/database"
    _icon = "sql.png"


class IotDevice(_GCP):
    _type = "generic"
    _icon_dir = "resource_images/aws/iot"
    _icon = "iot-sensor.png"


tv_gcp_users_icon = Users
tv_gcp_server = OnPremServer
tv_gcp_client = OnPremClient
tv_gcp_database = OnPremDatabase
tv_gcp_iot_device = IotDevice
