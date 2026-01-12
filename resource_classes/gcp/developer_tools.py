"""
GCP Developer Tools category - Cloud Code, Cloud Workstations, Duet AI.

Icon Resolution:
- All developer tools resources use category icon (2-color): resource_images/gcp/category/developer-tools.png
"""

from . import _GCP


class _DeveloperTools(_GCP):
    _type = "developer_tools"
    _icon_dir = "resource_images/gcp/category"
    _icon = "developer-tools.png"


class CloudCode(_DeveloperTools):
    """Cloud Code IDE plugin."""

    pass


class CloudWorkstations(_DeveloperTools):
    """Cloud Workstations managed dev environments."""

    pass


class DuetAI(_DeveloperTools):
    """Duet AI assistant."""

    pass


class Gemini(_DeveloperTools):
    """Gemini AI for developers."""

    pass


class CloudSDK(_DeveloperTools):
    """Cloud SDK command-line tools."""

    pass


class IDE(_DeveloperTools):
    """IDE integrations."""

    pass


class TestLab(_DeveloperTools):
    """Firebase Test Lab."""

    pass


# Aliases
Workstations = CloudWorkstations
SDK = CloudSDK

# Terraform resource aliases
google_workstations_workstation_cluster = CloudWorkstations
google_workstations_workstation_config = CloudWorkstations
google_workstations_workstation = CloudWorkstations
