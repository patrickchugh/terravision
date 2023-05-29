"""
AWS provides a set of services for Amazon Web Service provider.
"""

from resource_classes import Node


class _AWS(Node):
    _provider = "aws"
    _icon_dir = "resource_images/aws"

    fontcolor = "#ffffff"
