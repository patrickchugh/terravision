"""
GCP Business Intelligence category - Looker, Looker Studio, Data Studio.

Icon Resolution:
- Looker uses unique icon (4-color): resource_images/gcp/unique/looker.png
- Other BI resources use category icon (2-color): resource_images/gcp/category/business-intelligence.png
"""

from . import _GCP


class _BusinessIntelligence(_GCP):
    _type = "business_intelligence"
    _icon_dir = "resource_images/gcp/category"
    _icon = "business-intelligence.png"


class Looker(_BusinessIntelligence):
    """Looker BI platform - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "looker.png"


class LookerStudio(_BusinessIntelligence):
    """Looker Studio (formerly Data Studio)."""

    _icon = "business-intelligence.png"


class DataStudio(_BusinessIntelligence):
    """Data Studio (now Looker Studio)."""

    _icon = "business-intelligence.png"


class ConnectedSheets(_BusinessIntelligence):
    """Connected Sheets for BigQuery."""

    _icon = "business-intelligence.png"


# Aliases
BI = Looker

# No direct Terraform resources - Looker is managed via looker_instance
google_looker_instance = Looker
