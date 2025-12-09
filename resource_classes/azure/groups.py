import sys
import os
from pathlib import Path
from resource_classes import Cluster

defaultdir = "LR"
try:
    base_path = sys._MEIPASS
except AttributeError:
    base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent


class AZUREGroup(Cluster):
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


class ResourceGroupCluster(Cluster):
    def __init__(self, label="Resource Group", **kwargs):
        graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "#0078D4",
            "rank": "same",
        }
        rg_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/general/resource-groups.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(rg_label, defaultdir, graph_attrs)


class VNetGroup(Cluster):
    def __init__(self, label="Virtual Network", **kwargs):
        graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "darkgreen",
            "rank": "same",
        }
        vnet_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/network/virtual-networks.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(vnet_label, defaultdir, graph_attrs)


class SubnetGroup(Cluster):
    def __init__(self, label="Subnet", **kwargs):
        graph_attrs = {
            "style": "filled",
            "margin": "50",
            "color": "#deebf7",
            "pencolor": "",
            "_shift": "1",
        }
        subnet_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/networking/subnet.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(subnet_label, defaultdir, graph_attrs)


class NSGGroup(Cluster):
    def __init__(self, label="Network Security Group", **kwargs):
        graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "red",
            "center": "true",
            "labeljust": "c",
            "_shift": "0",
        }
        nsg_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><FONT color="red">{label}</FONT></TD></TR></TABLE>>'
        super().__init__(nsg_label, defaultdir, graph_attrs)


# Aliases for Terraform resource type names
azurerm_resource_group = ResourceGroupCluster
azurerm_virtual_network = VNetGroup
azurerm_subnet = SubnetGroup
azurerm_network_security_group = NSGGroup
