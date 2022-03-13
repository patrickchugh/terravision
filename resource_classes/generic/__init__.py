"""
Generic provides the possibility of load an image to be presented as a node.
"""

from resource_classes import Node


class _Generic(Node):
    provider = "generic"
    _icon_dir = "resource_images/generic"

    fontcolor = "#ffffff"
