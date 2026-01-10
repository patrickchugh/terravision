"""
GCP Observability category - Cloud Monitoring, Cloud Logging, Cloud Trace.

Icon Resolution:
- All observability resources use category icon (2-color): resource_images/gcp/category/observability.png
"""

from . import _GCP


class _Observability(_GCP):
    _type = "observability"
    _icon_dir = "resource_images/gcp/category"
    _icon = "observability.png"


class Monitoring(_Observability):
    """Cloud Monitoring metrics and dashboards."""

    pass


class Logging(_Observability):
    """Cloud Logging log management."""

    pass


class Trace(_Observability):
    """Cloud Trace distributed tracing."""

    pass


class ErrorReporting(_Observability):
    """Error Reporting for exception tracking."""

    pass


class Debugger(_Observability):
    """Cloud Debugger production debugging."""

    pass


class Profiler(_Observability):
    """Cloud Profiler performance analysis."""

    pass


class ServiceHealth(_Observability):
    """Service Health Dashboard."""

    pass


class ManagedPrometheus(_Observability):
    """Managed Service for Prometheus."""

    pass


class ManagedGrafana(_Observability):
    """Managed Service for Grafana."""

    pass


# Aliases
CloudMonitoring = Monitoring
CloudLogging = Logging
CloudTrace = Trace
Stackdriver = Monitoring  # Legacy name

# Terraform resource aliases
google_monitoring_alert_policy = Monitoring
google_monitoring_dashboard = Monitoring
google_monitoring_uptime_check_config = Monitoring
google_monitoring_notification_channel = Monitoring
google_monitoring_metric_descriptor = Monitoring
google_monitoring_group = Monitoring
google_logging_project_sink = Logging
google_logging_project_bucket_config = Logging
google_logging_metric = Logging
google_logging_log_view = Logging
google_logging_folder_sink = Logging
google_logging_organization_sink = Logging
