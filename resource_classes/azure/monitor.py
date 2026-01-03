from . import _Azure


class _Monitor(_Azure):
    _type = "monitor"
    _icon_dir = "resource_images/azure/monitor"


class ActivityLog(_Monitor):
    _icon = "activity-log.png"


class ApplicationInsights(_Monitor):
    _icon = "application-insights.png"


class AutoScale(_Monitor):
    _icon = "auto-scale.png"


class AzureMonitorsForSAPSolutions(_Monitor):
    _icon = "azure-monitors-for-sap-solutions.png"


class AzureWorkbooks(_Monitor):
    _icon = "azure-workbooks.png"


class ChangeAnalysis(_Monitor):
    _icon = "change-analysis.png"


class DiagnosticsSettings(_Monitor):
    _icon = "diagnostics-settings.png"


class LogAnalyticsWorkspaces(_Monitor):
    _icon = "log-analytics-workspaces.png"


class Logs(_Monitor):
    _icon = "logs.png"


class Metrics(_Monitor):
    _icon = "metrics.png"


class Monitor(_Monitor):
    _icon = "monitor.png"


class NetworkWatcher(_Monitor):
    _icon = "network-watcher.png"


# Aliases

# Terraform aliases
azurerm_monitor_action_group = Monitor
azurerm_monitor_activity_log_alert = ActivityLog
azurerm_monitor_metric_alert = Metrics
azurerm_application_insights = ApplicationInsights
azurerm_monitor_autoscale_setting = AutoScale
azurerm_log_analytics_workspace = LogAnalyticsWorkspaces
azurerm_monitor_diagnostic_setting = DiagnosticsSettings
azurerm_network_watcher = NetworkWatcher
