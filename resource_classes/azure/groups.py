import sys
import os
from pathlib import Path
from resource_classes import Cluster

defaultdir = "LR"
try:
    base_path = sys._MEIPASS
except AttributeError:
    base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent


class ResourceGroupCluster(Cluster):
    def __init__(self, label, **kwargs):
        rg_graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "#0078D4",
            "rank": "same",
        }
        rg_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/general/resource-groups.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(rg_label, defaultdir, rg_graph_attrs)


class VNetGroup(Cluster):
    def __init__(self, label, **kwargs):
        vnet_graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "darkgreen",
            "rank": "same",
        }
        vnet_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/network/virtual-networks.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(vnet_label, defaultdir, vnet_graph_attrs)


class SubnetGroup(Cluster):
    def __init__(self, label, **kwargs):
        subnet_graph_attrs = {
            "style": "filled",
            "margin": "50",
            "color": "#deebf7",
            "pencolor": "",
            "_shift": "1",
        }
        subnet_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/network/subnets.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(subnet_label, defaultdir, subnet_graph_attrs)


class NetworkSecurityGroupCluster(Cluster):
    def __init__(self, label, **kwargs):
        nsg_graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "red",
            "center": "true",
            "labeljust": "c",
            "_shift": "0",
        }
        nsg_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><FONT color="red">{label}</FONT></TD></TR></TABLE>>'
        super().__init__(nsg_label, defaultdir, nsg_graph_attrs)


class GenericGroup(Cluster):
    def __init__(self, label="Shared Services", **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "100",
            "pencolor": "black",
        }
        super().__init__(label, defaultdir, graph_attrs)


class Azuregroup(Cluster):
    def __init__(self, label="Azure Cloud", **kwargs):
        azure_graph_attrs = {
            "style": "solid",
            "pencolor": "#0078D4",
            "margin": "100",
            "ordering": "in",
            "penwidth": "2",
            "center": "true",
            "labeljust": "l",
            "_shift": "1",
        }
        azure_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/azure.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(azure_label, defaultdir, azure_graph_attrs)


# Terraform resource type aliases
azurerm_resource_group = ResourceGroupCluster
azurerm_virtual_network = VNetGroup
azurerm_subnet = SubnetGroup
azurerm_network_security_group = NetworkSecurityGroupCluster
