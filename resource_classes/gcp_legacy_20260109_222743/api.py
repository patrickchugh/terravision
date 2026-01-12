from . import _GCP


class _API(_GCP):
    _type = "api"
    _icon_dir = "resources/gcp/api"


class APIGateway(_API):
    _icon = "api-gateway.png"


class Apigee(_API):
    _icon = "apigee.png"


class Endpoints(_API):
    _icon = "endpoints.png"


# Aliases

# Terraform aliases
google_api_gateway_api = APIGateway
google_api_gateway_api_config = APIGateway
google_api_gateway_gateway = APIGateway
google_apigee_organization = Apigee
google_endpoints_service = Endpoints
