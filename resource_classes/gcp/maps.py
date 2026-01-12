"""
GCP Maps & Geospatial category - Maps Platform, Earth Engine.

Icon Resolution:
- All maps resources use category icon (2-color): resource_images/gcp/category/maps.png
"""

from . import _GCP


class _Maps(_GCP):
    _type = "maps"
    _icon_dir = "resource_images/gcp/category"
    _icon = "maps.png"


class MapsPlatform(_Maps):
    """Google Maps Platform."""

    pass


class EarthEngine(_Maps):
    """Google Earth Engine for geospatial analysis."""

    pass


class MapsJavaScriptAPI(_Maps):
    """Maps JavaScript API."""

    pass


class PlacesAPI(_Maps):
    """Places API for location data."""

    pass


class DirectionsAPI(_Maps):
    """Directions API for routing."""

    pass


class GeocodingAPI(_Maps):
    """Geocoding API for address lookup."""

    pass


class RoutesAPI(_Maps):
    """Routes API for route optimization."""

    pass


# Aliases
Maps = MapsPlatform
Earth = EarthEngine

# No direct Terraform resources - Maps managed via APIs
