from . import _AWS


class _Business(_AWS):
    _type = "business"
    _icon_dir = "resource_images/aws/business"


class AlexaForBusiness(_Business):
    _icon = "alexa-for-business.png"


class Chime(_Business):
    _icon = "chime.png"


class Workmail(_Business):
    _icon = "workmail.png"


# Aliases

A4B = AlexaForBusiness

# Terraform aliases
aws_chime_voice_connector = Chime
aws_workmail_organization = Workmail
aws_workmail_user = Workmail
