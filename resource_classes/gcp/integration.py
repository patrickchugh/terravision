"""
GCP Integration Services category - API Gateway, Apigee, Workflows, Application Integration.

Icon Resolution:
- Apigee uses unique icon (4-color): resource_images/gcp/unique/apigee.png
- Other integration resources use category icon (2-color): resource_images/gcp/category/integration.png
"""

from . import _GCP


class _Integration(_GCP):
    _type = "integration"
    _icon_dir = "resource_images/gcp/category"
    _icon = "integration.png"


class Apigee(_Integration):
    """Apigee API management platform - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "apigee.png"


class APIGateway(_Integration):
    """API Gateway for serverless APIs."""

    _icon = "integration.png"


class CloudEndpoints(_Integration):
    """Cloud Endpoints API management."""

    _icon = "integration.png"


class Workflows(_Integration):
    """Workflows orchestration service."""

    _icon = "integration.png"


class ApplicationIntegration(_Integration):
    """Application Integration iPaaS."""

    _icon = "integration.png"


class Connectors(_Integration):
    """Integration Connectors for SaaS."""

    _icon = "integration.png"


class PubSub(_Integration):
    """Pub/Sub messaging (also in Analytics)."""

    _icon = "integration.png"


class CloudTasks(_Integration):
    """Cloud Tasks async task execution."""

    _icon = "integration.png"


class CloudScheduler(_Integration):
    """Cloud Scheduler cron jobs."""

    _icon = "integration.png"


class Eventarc(_Integration):
    """Eventarc event routing."""

    _icon = "integration.png"


# Aliases
API = Apigee

# Terraform resource aliases
google_apigee_organization = Apigee
google_apigee_environment = Apigee
google_apigee_envgroup = Apigee
google_apigee_instance = Apigee
google_api_gateway_api = APIGateway
google_api_gateway_gateway = APIGateway
google_api_gateway_api_config = APIGateway
google_endpoints_service = CloudEndpoints
google_workflows_workflow = Workflows
google_integration_connectors_connection = Connectors
google_integration_connectors_endpoint_attachment = Connectors
