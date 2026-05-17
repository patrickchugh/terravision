"""
Azure provides a set of services for Microsoft Azure provider.
"""

from resource_classes import Node


class _Azure(Node):
    _provider = "azure"
    _icon_dir = "resource_images/azure"
    _height = 5.2

    def __init__(self, label="", **kwargs):
        # Azure canonical tall card: fixed grey rounded rectangle
        card_style = {
            "shape": "box",
            "fixedsize": "true",
            "width": "3.8",
            "height": "5.2",
            "imagescale": "false",
            "imagepos": "mc",
            "style": "rounded,filled",
            "fillcolor": "#F2F2F2",
            "color": "#D0D0D0",
            "penwidth": "2",
            "fontcolor": "#2C2C2C",
            "labelloc": "b",
            "margin": "0.6,1.0",
        }
        # kwargs override card_style defaults
        merged_attrs = {**card_style, **kwargs}
        super().__init__(label, **merged_attrs)


class Azure(_Azure):
    _icon = "azure.png"
