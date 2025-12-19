from . import _GCP


class _Security(_GCP):
    _type = "security"
    _icon_dir = "resources/gcp/security"


class AccessContextManager(_Security):
    _icon = "access-context-manager.png"


class AssuredWorkloads(_Security):
    _icon = "assured-workloads.png"


class CertificateAuthorityService(_Security):
    _icon = "certificate-authority-service.png"


class CertificateManager(_Security):
    _icon = "certificate-manager.png"


class CloudAssetInventory(_Security):
    _icon = "cloud-asset-inventory.png"


class Iam(_Security):
    _icon = "iam.png"


class IAP(_Security):
    _icon = "iap.png"


class KeyManagementService(_Security):
    _icon = "key-management-service.png"


class ResourceManager(_Security):
    _icon = "resource-manager.png"


class SecretManager(_Security):
    _icon = "secret-manager.png"


class SecurityCommandCenter(_Security):
    _icon = "security-command-center.png"


class SecurityHealthAdvisor(_Security):
    _icon = "security-health-advisor.png"


class SecurityScanner(_Security):
    _icon = "security-scanner.png"


# Aliases

ACM = AccessContextManager
KMS = KeyManagementService
SCC = SecurityCommandCenter

# Terraform aliases
google_project_iam_binding = Iam
google_project_iam_member = Iam
google_service_account = Iam
google_service_account_key = Iam
google_kms_key_ring = KeyManagementService
google_kms_crypto_key = KeyManagementService
google_secret_manager_secret = SecretManager
google_secret_manager_secret_version = SecretManager
google_iap_web_iam_binding = IAP
google_certificate_manager_certificate = CertificateManager
