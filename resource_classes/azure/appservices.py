from . import _Azure


class _Appservices(_Azure):
    _type = "appservices"
    _icon_dir = "resource_images/azure/appservices"


class AppServiceCertificates(_Appservices):
    _icon = "app-service-certificates.png"


class AppServiceDomains(_Appservices):
    _icon = "app-service-domains.png"


class AppServiceEnvironments(_Appservices):
    _icon = "app-service-environments.png"


class AppServicePlans(_Appservices):
    _icon = "app-service-plans.png"


class AppServices(_Appservices):
    _icon = "app-services.png"


class CDNProfiles(_Appservices):
    _icon = "cdn-profiles.png"


class CognitiveSearch(_Appservices):
    _icon = "cognitive-search.png"


class NotificationHubs(_Appservices):
    _icon = "notification-hubs.png"


# Aliases

# Terraform aliases
azurerm_app_service = AppServices
azurerm_app_service_plan = AppServicePlans
azurerm_app_service_certificate = AppServiceCertificates
azurerm_app_service_environment = AppServiceEnvironments
azurerm_cdn_profile = CDNProfiles
azurerm_search_service = CognitiveSearch
azurerm_notification_hub = NotificationHubs
