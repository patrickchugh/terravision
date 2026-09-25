from . import _AWS


class _Management(_AWS):
    _type = "management"
    _icon_dir = "resource_images/aws/management"


class Cloudformation(_Management):
    _icon = "cloudformation.png"


class Cloudtrail(_Management):
    _icon = "cloudtrail.png"


class Cloudwatch(_Management):
    _icon = "cloudwatch.png"


class Codeguru(_Management):
    _icon = "codeguru.png"


class CommandLineInterface(_Management):
    _icon = "command-line-interface.png"


class Config(_Management):
    _icon = "config.png"


class ControlTower(_Management):
    _icon = "control-tower.png"


class LicenseManager(_Management):
    _icon = "license-manager.png"


class ManagedServices(_Management):
    _icon = "managed-services.png"


class ManagementConsole(_Management):
    _icon = "management-console.png"


class Opsworks(_Management):
    _icon = "opsworks.png"


class Organizations(_Management):
    _icon = "organizations.png"


class ServiceCatalog(_Management):
    _icon = "service-catalog.png"


class SystemsManagerParameterStore(_Management):
    _icon = "systems-manager-parameter-store.png"


class SystemsManager(_Management):
    _icon = "systems-manager.png"


class TrustedAdvisor(_Management):
    _icon = "trusted-advisor.png"


class WellArchitectedTool(_Management):
    _icon = "well-architected-tool.png"


class CloudWatchAlarm(_Management):
    _icon = "cloudwatch-alarm.png"


# Aliases

SSM = SystemsManager
ParameterStore = SystemsManagerParameterStore

# Terraform aliases


class ManagedGrafana(_Management):
    _icon = "amazon-managed-grafana.png"


class ManagedPrometheus(_Management):
    _icon = "amazon-managed-prometheus.png"


class ManagedWorkflowsApacheAirflow(_Management):
    _icon = "amazon-managed-workflows-apache-airflow.png"


class DevopsGuru(_Management):
    _icon = "amazon-devops-guru.png"


class Chatbot(_Management):
    _icon = "chatbot.png"


class SystemsManagerAppConfig(_Management):
    _icon = "systems-manager-app-config.png"


aws_cloudformation_stack = Cloudformation
aws_cloudformation_stack_set = Cloudformation
aws_cloudtrail = Cloudtrail
aws_cloudwatch_log = Cloudwatch
aws_cloudwatch = Cloudwatch
aws_cloudwatch_composite_alarm = Cloudwatch
aws_cloudwatch_dashboard = Cloudwatch
aws_cloudwatch_log_destination = Cloudwatch
aws_cloudwatch_log_destination_policy = Cloudwatch
aws_cloudwatch_log_group = Cloudwatch
aws_cloudwatch_log_metric_filter = Cloudwatch
aws_cloudwatch_log_resource_policy = Cloudwatch
aws_cloudwatch_log_stream = Cloudwatch
aws_cloudwatch_log_subscription_filter = Cloudwatch
aws_cloudwatch_metric_alarm = Cloudwatch
aws_cloudwatch_query_definition = Cloudwatch
aws_config_configuration_recorder = Config
aws_config_config_rule = Config
aws_controltower_control = ControlTower
aws_licensemanager_license_configuration = LicenseManager
aws_opsworks_stack = Opsworks
aws_opsworks_application = Opsworks
aws_organizations_organization = Organizations
aws_organizations_account = Organizations
aws_organizations_organizational_unit = Organizations
aws_servicecatalog_portfolio = ServiceCatalog
aws_servicecatalog_product = ServiceCatalog
aws_ssm_document = SystemsManager
aws_ssm_patch_baseline = SystemsManager
aws_ssm_maintenance_window = SystemsManager
aws_ssm_association = SystemsManager
aws_ssm_parameter = SystemsManagerParameterStore
aws_cloudwatch_metric_alarm = CloudWatchAlarm

# Current aws resource types linked to existing icons
aws_grafana_workspace = ManagedGrafana
aws_prometheus_workspace = ManagedPrometheus
aws_prometheus_scraper = ManagedPrometheus
aws_mwaa_environment = ManagedWorkflowsApacheAirflow
aws_devopsguru_resource_collection = DevopsGuru
aws_chatbot_slack_channel_configuration = Chatbot
aws_appconfig_application = SystemsManagerAppConfig
aws_ssmincidents_response_plan = SystemsManager
aws_ssmcontacts_contact = SystemsManager
aws_servicecatalogappregistry_application = ServiceCatalog
aws_synthetics_canary = Cloudwatch
aws_rum_app_monitor = Cloudwatch
aws_internetmonitor_monitor = Cloudwatch
