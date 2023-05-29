from . import _OnPrem


class _Iac(_OnPrem):
    _type = "iac"
    _icon_dir = "resource_images/onprem/iac"


class Ansible(_Iac):
    _icon = "ansible.png"


class Atlantis(_Iac):
    _icon = "atlantis.png"


class Awx(_Iac):
    _icon = "awx.png"


class Terraform(_Iac):
    _icon = "terraform.png"


# Aliases
