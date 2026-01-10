"""
GCP Security & Identity category - IAM, Secret Manager, KMS, Security Command Center.

Icon Resolution:
- Security Command Center uses unique icon (4-color): resource_images/gcp/unique/security-command-center.png
- Mandiant uses unique icon (4-color): resource_images/gcp/unique/mandiant.png
- SecOps uses unique icon (4-color): resource_images/gcp/unique/secops.png
- Threat Intelligence uses unique icon (4-color): resource_images/gcp/unique/threat-intelligence.png
- Other security resources use category icon (2-color): resource_images/gcp/category/security.png
"""

from . import _GCP


class _Security(_GCP):
    _type = "security"
    _icon_dir = "resource_images/gcp/category"
    _icon = "security.png"


class SecurityCommandCenter(_Security):
    """Security Command Center - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "security-command-center.png"


class Mandiant(_Security):
    """Mandiant threat intelligence - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "mandiant.png"


class SecOps(_Security):
    """Security Operations (Chronicle SIEM) - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "secops.png"


class ThreatIntelligence(_Security):
    """Threat Intelligence - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "threat-intelligence.png"


class IAM(_Security):
    """Identity and Access Management."""

    _icon = "security.png"


class Iam(_Security):
    """IAM (legacy alias)."""

    _icon = "security.png"


class ServiceAccount(_Security):
    """Service accounts for workload identity."""

    _icon = "security.png"


class SecretManager(_Security):
    """Secret Manager for secrets storage."""

    _icon = "security.png"


class KMS(_Security):
    """Cloud KMS key management."""

    _icon = "security.png"


class KeyManagementService(_Security):
    """KMS (legacy alias)."""

    _icon = "security.png"


class CertificateAuthority(_Security):
    """Certificate Authority Service."""

    _icon = "security.png"


class CertificateAuthorityService(_Security):
    """CA Service (legacy alias)."""

    _icon = "security.png"


class CertificateManager(_Security):
    """Certificate Manager."""

    _icon = "security.png"


class BeyondCorp(_Security):
    """BeyondCorp Enterprise zero trust."""

    _icon = "security.png"


class IdentityAwareProxy(_Security):
    """Identity-Aware Proxy."""

    _icon = "security.png"


class IAP(_Security):
    """IAP (legacy alias)."""

    _icon = "security.png"


class AccessContextManager(_Security):
    """Access Context Manager for VPC SC."""

    _icon = "security.png"


class AssetInventory(_Security):
    """Cloud Asset Inventory."""

    _icon = "security.png"


class CloudAssetInventory(_Security):
    """CAI (legacy alias)."""

    _icon = "security.png"


class DataLossPrevention(_Security):
    """Data Loss Prevention API."""

    _icon = "security.png"


class WebSecurityScanner(_Security):
    """Web Security Scanner."""

    _icon = "security.png"


class SecurityScanner(_Security):
    """Security Scanner (legacy alias)."""

    _icon = "security.png"


class SecurityHealthAdvisor(_Security):
    """Security Health Advisor."""

    _icon = "security.png"


class AssuredWorkloads(_Security):
    """Assured Workloads compliance."""

    _icon = "security.png"


class ResourceManager(_Security):
    """Resource Manager for projects/folders."""

    _icon = "security.png"


# Aliases
SCC = SecurityCommandCenter
ACM = AccessContextManager
Secrets = SecretManager

# Terraform resource aliases
google_service_account = ServiceAccount
google_service_account_key = ServiceAccount
google_project_iam_member = IAM
google_project_iam_binding = IAM
google_project_iam_policy = IAM
google_organization_iam_member = IAM
google_folder_iam_member = IAM
google_secret_manager_secret = SecretManager
google_secret_manager_secret_version = SecretManager
google_kms_key_ring = KMS
google_kms_crypto_key = KMS
google_kms_crypto_key_iam_member = KMS
google_privateca_certificate_authority = CertificateAuthority
google_privateca_certificate = CertificateAuthority
google_certificate_manager_certificate = CertificateManager
google_iap_client = IdentityAwareProxy
google_iap_web_iam_member = IdentityAwareProxy
google_iap_web_iam_binding = IdentityAwareProxy
google_access_context_manager_access_policy = AccessContextManager
google_access_context_manager_service_perimeter = AccessContextManager
google_cloud_asset_folder_feed = AssetInventory
google_data_loss_prevention_inspect_template = DataLossPrevention
google_data_loss_prevention_job_trigger = DataLossPrevention
google_scc_source = SecurityCommandCenter
google_scc_notification_config = SecurityCommandCenter
