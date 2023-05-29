from . import _OnPrem


class _Storage(_OnPrem):
    _type = "storage"
    _icon_dir = "resource_images/onprem/storage"


class CephOsd(_Storage):
    _icon = "ceph-osd.png"


class Ceph(_Storage):
    _icon = "ceph.png"


class Glusterfs(_Storage):
    _icon = "glusterfs.png"


# Aliases

CEPH = Ceph
CEPH_OSD = CephOsd
