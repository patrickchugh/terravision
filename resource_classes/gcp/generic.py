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


tv_gcp_users_icon = Users
