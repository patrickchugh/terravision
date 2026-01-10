"""
GCP Marketplace category - Cloud Marketplace, SaaS integrations.

Icon Resolution:
- All marketplace resources use category icon (2-color): resource_images/gcp/category/marketplace.png
"""

from . import _GCP


class _Marketplace(_GCP):
    _type = "marketplace"
    _icon_dir = "resource_images/gcp/category"
    _icon = "marketplace.png"


class CloudMarketplace(_Marketplace):
    """Google Cloud Marketplace."""

    pass


class PrivateCatalog(_Marketplace):
    """Private Catalog for internal solutions."""

    pass


class SaaSIntegration(_Marketplace):
    """SaaS integration partner solutions."""

    pass


class VMImages(_Marketplace):
    """Pre-built VM images."""

    pass


class ContainerImages(_Marketplace):
    """Pre-built container images."""

    pass


class Solutions(_Marketplace):
    """Click-to-deploy solutions."""

    pass


# Aliases
Marketplace = CloudMarketplace

# No direct Terraform resources - Marketplace managed via Console
