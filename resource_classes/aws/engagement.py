from . import _AWS


class _Engagement(_AWS):
    _type = "engagement"
    _icon_dir = "resource_images/aws/engagement"


class Connect(_Engagement):
    _icon = "connect.png"


class Pinpoint(_Engagement):
    _icon = "pinpoint.png"


class SimpleEmailServiceSes(_Engagement):
    _icon = "simple-email-service-ses.png"


# Aliases

SES = SimpleEmailServiceSes

# Terraform Resource Mappings

aws_ses_configuration_set = SimpleEmailServiceSes
