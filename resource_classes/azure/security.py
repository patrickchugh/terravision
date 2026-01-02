from . import _Azure


class _Security(_Azure):
    _type = "security"
    _icon_dir = "resource_images/azure/security"


class ApplicationSecurityGroups(_Security):
    _icon = "application-security-groups.png"


class AzureADAuthenticationMethods(_Security):
    _icon = "azure-ad-authentication-methods.png"


class AzureADIdentityProtection(_Security):
    _icon = "azure-ad-identity-protection.png"


class AzureADPrivlegedIdentityManagement(_Security):
    _icon = "azure-ad-privleged-identity-management.png"


class AzureADRiskySignins(_Security):
    _icon = "azure-ad-risky-signins.png"


class AzureADRiskyUsers(_Security):
    _icon = "azure-ad-risky-users.png"


class AzureInformationProtection(_Security):
    _icon = "azure-information-protection.png"


class AzureSentinel(_Security):
    _icon = "azure-sentinel.png"


class ConditionalAccess(_Security):
    _icon = "conditional-access.png"


class Defender(_Security):
    _icon = "defender.png"


class Detonation(_Security):
    _icon = "detonation.png"


class ExtendedSecurityUpdates(_Security):
    _icon = "extended-security-updates.png"


class Extendedsecurityupdates(_Security):
    _icon = "extendedsecurityupdates.png"


class IdentitySecureScore(_Security):
    _icon = "identity-secure-score.png"


class KeyVaults(_Security):
    _icon = "key-vaults.png"


class MicrosoftDefenderEasm(_Security):
    _icon = "microsoft-defender-easm.png"


class MicrosoftDefenderForCloud(_Security):
    _icon = "microsoft-defender-for-cloud.png"


class MicrosoftDefenderForIot(_Security):
    _icon = "microsoft-defender-for-iot.png"


class MultifactorAuthentication(_Security):
    _icon = "multifactor-authentication.png"


class SecurityCenter(_Security):
    _icon = "security-center.png"


class Sentinel(_Security):
    _icon = "sentinel.png"


class UserSettings(_Security):
    _icon = "user-settings.png"


# Aliases

# Terraform aliases
azurerm_application_security_group = ApplicationSecurityGroups
azurerm_sentinel_alert_rule = AzureSentinel
azurerm_sentinel_data_connector = AzureSentinel
azurerm_security_center_contact = SecurityCenter
azurerm_security_center_subscription_pricing = SecurityCenter
azurerm_key_vault = KeyVaults
azurerm_key_vault_key = KeyVaults
azurerm_key_vault_secret = KeyVaults
