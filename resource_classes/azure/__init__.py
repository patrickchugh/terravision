"""
Azure provides a set of services for Microsoft Azure provider.
"""

from resource_classes import Node


class _Azure(Node):
    _provider = "azure"
    _icon_dir = "resource_images/azure"

    def __init__(self, label="", **kwargs):
        # Azure service card styling - light grey rounded rectangles with internal padding
        card_style = {
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "#F2F2F2",
            "color": "#E0E0E0",
            "penwidth": "1",
            "fontcolor": "#2C2C2C",
            "margin": "0.4",  # Internal margin/padding around the icon
        }
        # kwargs override card_style defaults
        merged_attrs = {**card_style, **kwargs}
        super().__init__(label, **merged_attrs)


class Azure(_Azure):
    _icon = "azure.png"
