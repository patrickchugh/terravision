from . import _Azure


class _Mobile(_Azure):
    _type = "mobile"
    _icon_dir = "resource_images/azure/mobile"


class AppServiceMobile(_Mobile):
    _icon = "app-service-mobile.png"


class AppServices(_Mobile):
    _icon = "app-services.png"


class MobileEngagement(_Mobile):
    _icon = "mobile-engagement.png"


class NotificationHubs(_Mobile):
    _icon = "notification-hubs.png"


class PowerPlatform(_Mobile):
    _icon = "power-platform.png"


# Aliases

# Terraform aliases
azurerm_app_service_mobile = AppServiceMobile
azurerm_notification_hub = NotificationHubs
