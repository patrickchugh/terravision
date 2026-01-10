"""
GCP Management Tools category - Cloud Console, Cloud Shell, Deployment Manager.

Icon Resolution:
- All management resources use category icon (2-color): resource_images/gcp/category/management.png
"""

from . import _GCP


class _Management(_GCP):
    _type = "management"
    _icon_dir = "resource_images/gcp/category"
    _icon = "management.png"


class CloudConsole(_Management):
    """Cloud Console web UI."""

    pass


class CloudShell(_Management):
    """Cloud Shell browser-based terminal."""

    pass


class DeploymentManager(_Management):
    """Deployment Manager IaC service."""

    pass


class CloudBuild(_Management):
    """Cloud Build CI/CD service."""

    pass


class ServiceUsage(_Management):
    """Service Usage API management."""

    pass


class OrgPolicy(_Management):
    """Organization Policy constraints."""

    pass


class ResourceManager(_Management):
    """Resource Manager for projects/folders."""

    pass


class Project(_Management):
    """Project management (legacy alias)."""

    pass


class Billing(_Management):
    """Cloud Billing."""

    pass


class Quotas(_Management):
    """Quotas management."""

    pass


class Support(_Management):
    """Cloud Support."""

    pass


class CloudAPI(_Management):
    """API Gateway and management."""

    pass


class ServiceManagement(_Management):
    """Service Management API."""

    pass


class PrivateCatalog(_Management):
    """Private Catalog for solutions."""

    pass


class CloudDebugger(_Management):
    """Cloud Debugger (deprecated)."""

    pass


class CloudProfiler(_Management):
    """Cloud Profiler for performance."""

    pass


# Terraform resource aliases
# Note: google_project is defined in groups.py as ProjectZone (Cluster) for zone rendering
# The Project class here is for project management icon, not project boundaries
google_folder = ResourceManager
google_organization = ResourceManager
google_project_service = ServiceUsage
google_cloudbuild_trigger = CloudBuild
google_cloudbuild_worker_pool = CloudBuild
google_org_policy_policy = OrgPolicy
google_deployment_manager_deployment = DeploymentManager
google_api_gateway_api = CloudAPI
google_api_gateway_gateway = CloudAPI
google_api_gateway_api_config = CloudAPI
google_service_directory_namespace = ServiceManagement
google_billing_account = Billing
