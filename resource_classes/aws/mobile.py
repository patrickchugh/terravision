from . import _AWS


class _Mobile(_AWS):
    _type = "mobile"
    _icon_dir = "resource_images/aws/mobile"


class Amplify(_Mobile):
    _icon = "amplify.png"


class APIGatewayEndpoint(_Mobile):
    _icon = "api-gateway-endpoint.png"


# TODO: Make API Gateway a Group and specify icon variant e.g. mobile icon is red
class APIGatewayRed(_Mobile):
    _icon = "api-gateway.png"


class Appsync(_Mobile):
    _icon = "appsync.png"


class DeviceFarm(_Mobile):
    _icon = "device-farm.png"


class Pinpoint(_Mobile):
    _icon = "pinpoint.png"


# Aliases
aws_appsync_function = Appsync
aws_devicefarm_project = DeviceFarm
