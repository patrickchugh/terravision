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

# Terraform aliases
aws_connect_instance = Connect
aws_pinpoint_app = Pinpoint
aws_ses_configuration_set = SimpleEmailServiceSes
aws_ses_domain_identity = SimpleEmailServiceSes
aws_ses_email_identity = SimpleEmailServiceSes
