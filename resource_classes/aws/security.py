from . import _AWS


class _Security(_AWS):
    _type = "security"
    _icon_dir = "resource_images/aws/security"


class Artifact(_Security):
    _icon = "artifact.png"


class CertificateManager(_Security):
    _icon = "certificate-manager.png"


class CloudDirectory(_Security):
    _icon = "cloud-directory.png"


class Cloudhsm(_Security):
    _icon = "cloudhsm.png"


class Cognito(_Security):
    _icon = "cognito.png"


class Detective(_Security):
    _icon = "detective.png"


class DirectoryService(_Security):
    _icon = "directory-service.png"


class FirewallManager(_Security):
    _icon = "firewall-manager.png"


class Guardduty(_Security):
    _icon = "guardduty.png"


class IdentityAndAccessManagementIamAccessAnalyzer(_Security):
    _icon = "identity-and-access-management-iam-access-analyzer.png"


class IdentityAndAccessManagementIamAWSSts(_Security):
    _icon = "identity-and-access-management-iam-aws-sts.png"


class IdentityAndAccessManagementIamPermissions(_Security):
    _icon = "identity-and-access-management-iam-permissions.png"


class IdentityAndAccessManagementIamRole(_Security):
    _icon = "identity-and-access-management-iam-role.png"


class IdentityAndAccessManagementIam(_Security):
    _icon = "identity-and-access-management-iam.png"


class Inspector(_Security):
    _icon = "inspector.png"


class KeyManagementService(_Security):
    _icon = "key-management-service.png"


class Macie(_Security):
    _icon = "macie.png"


class ResourceAccessManager(_Security):
    _icon = "resource-access-manager.png"


class SecretsManager(_Security):
    _icon = "secrets-manager.png"


class SecurityHub(_Security):
    _icon = "security-hub.png"


class SecurityIdentityAndCompliance(_Security):
    _icon = "security-identity-and-compliance.png"


class Shield(_Security):
    _icon = "shield.png"


class SingleSignOn(_Security):
    _icon = "single-sign-on.png"


class WAF(_Security):
    _icon = "waf.png"


# Aliases

ACM = CertificateManager
CloudHSM = Cloudhsm
DS = DirectoryService
FMS = FirewallManager
IAMAccessAnalyzer = IdentityAndAccessManagementIamAccessAnalyzer
IAMAWSSts = IdentityAndAccessManagementIamAWSSts
IAMPermissions = IdentityAndAccessManagementIamPermissions
IAMRole = IdentityAndAccessManagementIamRole
IAM = IdentityAndAccessManagementIam
KMS = KeyManagementService
RAM = ResourceAccessManager

# Terraform aliases
aws_acm_certificate = CertificateManager
aws_acm_certificate_validation = CertificateManager
aws_acm = CertificateManager
aws_cloudhsm_v2_cluster = CloudHSM
aws_cloudhsm_v2_hsm = CloudHSM
aws_cognito_identity_pool = Cognito
aws_cognito_user_pool = Cognito
aws_cognito_user_pool_client = Cognito
aws_detective_graph = Detective
aws_directory_service_directory = DirectoryService
aws_fms_admin_account = FirewallManager
aws_fms_policy = FirewallManager
aws_guardduty_detector = Guardduty
aws_guardduty_member = Guardduty
aws_iam_access_analyzer = IAMAccessAnalyzer
aws_iam_role = IdentityAndAccessManagementIamRole
aws_iam_user = IdentityAndAccessManagementIam
aws_iam_group = IdentityAndAccessManagementIam
aws_iam_policy = IAMPermissions
aws_iam_role_policy_attachment = IAMPermissions
aws_iam_role_policy = IAMPermissions
aws_iam_policy_attachment = IAMPermissions
aws_inspector_assessment_target = Inspector
aws_inspector_assessment_template = Inspector
aws_inspector2_enabler = Inspector
aws_kms_alias = KeyManagementService
aws_kms_grant = KeyManagementService
aws_kms_key = KeyManagementService
aws_macie2_account = Macie
aws_macie_member_account_association = Macie
aws_macie_s3_bucket_association = Macie
aws_ram_principal_association = ResourceAccessManager
aws_ram_resource_association = ResourceAccessManager
aws_ram_resource_share = ResourceAccessManager
aws_secretsmanager_secret = SecretsManager
aws_secretsmanager_secret_version = SecretsManager
aws_securityhub_account = SecurityHub
aws_securityhub_standards_subscription = SecurityHub
aws_shield_protection = Shield
aws_shield_protection_group = Shield
aws_ssoadmin_account_assignment = SingleSignOn
aws_ssoadmin_permission_set = SingleSignOn
aws_wafv2_web_acl = WAF
aws_wafv2_ip_set = WAF
aws_waf_web_acl = WAF
aws_waf_rule = WAF
aws_waf_rule_group = WAF
aws_wafregional_web_acl = WAF
aws_wafregional_rule_group = WAF
