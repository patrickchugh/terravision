from . import _Azure


class _Analytics(_Azure):
    _type = "analytics"
    _icon_dir = "resource_images/azure/analytics"


class AnalysisServices(_Analytics):
    _icon = "analysis-services.png"


class AzureDataExplorerClusters(_Analytics):
    _icon = "azure-data-explorer-clusters.png"


class AzureDatabricks(_Analytics):
    _icon = "azure-databricks.png"


class AzureSynapseAnalytics(_Analytics):
    _icon = "azure-synapse-analytics.png"


class AzureWorkbooks(_Analytics):
    _icon = "azure-workbooks.png"


class DataExplorerClusters(_Analytics):
    _icon = "data-explorer-clusters.png"


class DataFactories(_Analytics):
    _icon = "data-factories.png"


class DataLakeAnalytics(_Analytics):
    _icon = "data-lake-analytics.png"


class DataLakeStoreGen1(_Analytics):
    _icon = "data-lake-store-gen1.png"


class Databricks(_Analytics):
    _icon = "databricks.png"


class EndpointAnalytics(_Analytics):
    _icon = "endpoint-analytics.png"


class EventHubClusters(_Analytics):
    _icon = "event-hub-clusters.png"


class EventHubs(_Analytics):
    _icon = "event-hubs.png"


class HDInsightClusters(_Analytics):
    _icon = "hd-insight-clusters.png"


class LogAnalyticsWorkspaces(_Analytics):
    _icon = "log-analytics-workspaces.png"


class PowerBiEmbedded(_Analytics):
    _icon = "power-bi-embedded.png"


class PowerPlatform(_Analytics):
    _icon = "power-platform.png"


class PrivateLinkServices(_Analytics):
    _icon = "private-link-services.png"


class StreamAnalyticsJobs(_Analytics):
    _icon = "stream-analytics-jobs.png"


class SynapseAnalytics(_Analytics):
    _icon = "synapse-analytics.png"


# Aliases

# Terraform aliases
azurerm_analysis_services_server = AnalysisServices
azurerm_kusto_cluster = AzureDataExplorerClusters
azurerm_databricks_workspace = AzureDatabricks
azurerm_synapse_workspace = AzureSynapseAnalytics
azurerm_data_factory = DataFactories
azurerm_data_factory_pipeline = DataFactories
azurerm_eventhub_namespace = EventHubs
azurerm_eventhub = EventHubs
azurerm_hdinsight_hadoop_cluster = HDInsightClusters
azurerm_hdinsight_spark_cluster = HDInsightClusters
azurerm_log_analytics_workspace = LogAnalyticsWorkspaces
azurerm_powerbi_embedded = PowerBiEmbedded
azurerm_stream_analytics_job = StreamAnalyticsJobs
