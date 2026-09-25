"""
GCP DevOps category - Cloud Build, Cloud Deploy, Artifact Registry.

Icon Resolution:
- All DevOps resources use category icon (2-color): resource_images/gcp/category/devops.png
"""

from . import _GCP


class _DevOps(_GCP):
    _type = "devops"
    _icon_dir = "resource_images/gcp/category"
    _icon = "devops.png"


class CloudBuild(_DevOps):
    """Cloud Build CI/CD pipelines."""

    pass


class CloudDeploy(_DevOps):
    """Cloud Deploy continuous delivery."""

    pass


class ArtifactRegistry(_DevOps):
    """Artifact Registry for packages and containers."""

    pass


class ContainerAnalysis(_DevOps):
    """Container Analysis vulnerability scanning."""

    pass


class BinaryAuthorization(_DevOps):
    """Binary Authorization deploy-time security."""

    pass


class SourceRepositories(_DevOps):
    """Cloud Source Repositories Git hosting."""

    pass


class ContainerSecurityVulnerabilities(_DevOps):
    """Container vulnerability scanning."""

    pass


# Aliases
Build = CloudBuild
Deploy = CloudDeploy
Artifacts = ArtifactRegistry

# Terraform resource aliases


class DeveloperConnect(_DevOps):
    """Developer Connect source-control connections."""

    _icon = "devops.png"


google_cloudbuild_trigger = CloudBuild
google_cloudbuild_worker_pool = CloudBuild
google_clouddeploy_delivery_pipeline = CloudDeploy
google_clouddeploy_target = CloudDeploy
google_artifact_registry_repository = ArtifactRegistry
google_artifact_registry_repository_iam_member = ArtifactRegistry
google_sourcerepo_repository = SourceRepositories
google_binary_authorization_policy = BinaryAuthorization
google_binary_authorization_attestor = BinaryAuthorization

# Current google resource types linked to existing icons
google_cloudbuildv2_connection = CloudBuild
google_cloudbuildv2_repository = CloudBuild
google_developer_connect_connection = DeveloperConnect
google_secure_source_manager_instance = SourceRepositories
