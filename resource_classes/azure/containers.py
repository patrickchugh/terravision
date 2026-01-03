from . import _Azure


class _Containers(_Azure):
    _type = "containers"
    _icon_dir = "resource_images/azure/containers"


class AppServices(_Containers):
    _icon = "app-services.png"


class AzureRedHatOpenshift(_Containers):
    _icon = "azure-red-hat-openshift.png"


class BatchAccounts(_Containers):
    _icon = "batch-accounts.png"


class ContainerInstances(_Containers):
    _icon = "container-instances.png"


class ContainerRegistries(_Containers):
    _icon = "container-registries.png"


class KubernetesServices(_Containers):
    _icon = "kubernetes-services.png"


class ServiceFabricClusters(_Containers):
    _icon = "service-fabric-clusters.png"


# Aliases

# Terraform aliases
azurerm_container_app = AppServices
azurerm_container_group = ContainerInstances
azurerm_container_registry = ContainerRegistries
azurerm_kubernetes_cluster = KubernetesServices
azurerm_service_fabric_cluster = ServiceFabricClusters
azurerm_batch_account = BatchAccounts
