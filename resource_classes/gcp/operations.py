from . import _GCP


class _Operations(_GCP):
    _type = "operations"
    _icon_dir = "resources/gcp/operations"


class Logging(_Operations):
    _icon = "logging.png"


class Monitoring(_Operations):
    _icon = "monitoring.png"


# Aliases

# Terraform aliases
google_logging_project_sink = Logging
google_logging_folder_sink = Logging
google_monitoring_alert_policy = Monitoring
google_monitoring_notification_channel = Monitoring
google_monitoring_uptime_check_config = Monitoring
