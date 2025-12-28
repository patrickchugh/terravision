from . import _AWS


class _Mobile(_AWS):
    _type = "mobile"
    _icon_dir = "resource_images/aws/mobile"


class Amplify(_Mobile):
    _icon = "amplify.png"


class APIGatewayEndpoint(_Mobile):
    _icon = "api-gateway-endpoint.png"


class APIGatewayRed(_Mobile):
    _icon = "api-gateway.png"


class Appsync(_Mobile):
    _icon = "appsync.png"


class DeviceFarm(_Mobile):
    _icon = "device-farm.png"


class Pinpoint(_Mobile):
    _icon = "pinpoint.png"


# Aliases

# Terraform aliases
aws_amplify_app = Amplify
aws_amplify_branch = Amplify
aws_api_gateway_rest_api = APIGatewayRed
aws_apigatewayv2_api = APIGatewayRed
aws_appsync_graphql_api = Appsync
aws_appsync_function = Appsync
aws_devicefarm_project = DeviceFarm
aws_pinpoint_app = Pinpoint
