"""
GCP Mixed Reality category - ARCore, Immersive Stream.

Icon Resolution:
- All mixed reality resources use category icon (2-color): resource_images/gcp/category/mixed-reality.png
"""

from . import _GCP


class _MixedReality(_GCP):
    _type = "mixed_reality"
    _icon_dir = "resource_images/gcp/category"
    _icon = "mixed-reality.png"


class ARCore(_MixedReality):
    """ARCore augmented reality platform."""

    pass


class ImmersiveStream(_MixedReality):
    """Immersive Stream for XR streaming."""

    pass


class CloudAnchors(_MixedReality):
    """Cloud Anchors for shared AR experiences."""

    pass


class Geospatial(_MixedReality):
    """Geospatial API for location-based AR."""

    pass


# Aliases
AR = ARCore
XR = ImmersiveStream

# No direct Terraform resources - AR managed via Mobile SDK
