from . import _Generic


class _Virtualization(_Generic):
    _type = "virtualization"
    _icon_dir = "resource_images/generic/virtualization"


class Virtualbox(_Virtualization):
    _icon = "virtualbox.png"


class Vmware(_Virtualization):
    _icon = "vmware.png"


class XEN(_Virtualization):
    _icon = "xen.png"


# Aliases
