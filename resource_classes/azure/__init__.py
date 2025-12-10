"""
Azure provides a set of services for Microsoft Azure provider.
"""

from resource_classes import Node


class _Azure(Node):
    _provider = "azure"
    _icon_dir = "resource_images/azure"

    fontcolor = "#ffffff"


class Azure(_Azure):
    _icon = "azure.png"
