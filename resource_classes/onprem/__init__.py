"""
OnPrem provides a set of general on-premise services.
"""

from resource_classes import Node


class _OnPrem(Node):
    _provider = "onprem"
    _icon_dir = "resource_images/onprem"

    fontcolor = "#ffffff"
