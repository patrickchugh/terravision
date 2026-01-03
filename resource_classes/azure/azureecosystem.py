from . import _Azure


class _Azureecosystem(_Azure):
    _type = "azureecosystem"
    _icon_dir = "resource_images/azure/azureecosystem"


class Applens(_Azureecosystem):
    _icon = "applens.png"


class AzureHybridCenter(_Azureecosystem):
    _icon = "azure-hybrid-center.png"


class CollaborativeService(_Azureecosystem):
    _icon = "collaborative-service.png"


# Aliases
