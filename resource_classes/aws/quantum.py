from . import _AWS


class _Quantum(_AWS):
    _type = "quantum"
    _icon_dir = "resource_images/aws/quantum"


class Braket(_Quantum):
    _icon = "braket.png"


# Aliases

# Terraform aliases
aws_braket_job = Braket
