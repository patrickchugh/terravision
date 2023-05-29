from . import _Generic


class _Os(_Generic):
    _type = "os"
    _icon_dir = "resource_images/generic/os"


class Android(_Os):
    _icon = "android.png"


class Centos(_Os):
    _icon = "centos.png"


class IOS(_Os):
    _icon = "ios.png"


class LinuxGeneral(_Os):
    _icon = "linux-general.png"


class Suse(_Os):
    _icon = "suse.png"


class Ubuntu(_Os):
    _icon = "ubuntu.png"


class Windows(_Os):
    _icon = "windows.png"


# Aliases
