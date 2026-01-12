"""
GCP Serverless Computing category - Cloud Run, Cloud Functions, App Engine.

Icon Resolution:
- Cloud Run uses unique icon (4-color): resource_images/gcp/unique/cloud-run.png
- Other serverless resources use category icon (2-color): resource_images/gcp/category/serverless.png
"""

from . import _GCP


class _Serverless(_GCP):
    _type = "serverless"
    _icon_dir = "resource_images/gcp/category"
    _icon = "serverless.png"


class CloudRun(_Serverless):
    """Cloud Run serverless containers - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "cloud-run.png"


class CloudFunctions(_Serverless):
    """Cloud Functions serverless functions."""

    _icon = "serverless.png"


class AppEngine(_Serverless):
    """App Engine PaaS platform."""

    _icon = "serverless.png"


class CloudTasks(_Serverless):
    """Cloud Tasks for asynchronous task execution."""

    _icon = "serverless.png"


class CloudScheduler(_Serverless):
    """Cloud Scheduler for cron jobs."""

    _icon = "serverless.png"


class Workflows(_Serverless):
    """Workflows for orchestration."""

    _icon = "serverless.png"


class Eventarc(_Serverless):
    """Eventarc for event routing."""

    _icon = "serverless.png"


# Aliases
Run = CloudRun
Functions = CloudFunctions
GCF = CloudFunctions
GAE = AppEngine

# Terraform resource aliases
google_cloud_run_service = CloudRun
google_cloud_run_v2_service = CloudRun
google_cloud_run_v2_job = CloudRun
google_cloudfunctions_function = CloudFunctions
google_cloudfunctions2_function = CloudFunctions
google_app_engine_application = AppEngine
google_app_engine_standard_app_version = AppEngine
google_app_engine_flexible_app_version = AppEngine
google_cloud_tasks_queue = CloudTasks
google_cloud_scheduler_job = CloudScheduler
google_workflows_workflow = Workflows
google_eventarc_trigger = Eventarc
