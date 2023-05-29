from . import _OnPrem


class _Proxmox(_OnPrem):
    _type = "proxmox"
    _icon_dir = "resource_images/onprem/proxmox"


class Pve(_Proxmox):
    _icon = "pve.png"


# Aliases

ProxmoxVE = Pve
