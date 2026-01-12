"""
Azure cluster group classes for TerraVision diagrams.

Each cluster class supports two types of labels:
1. Bottom label nodes (positioned via gvpr post-processing):
   - Set via label_text, label_icon, label_position attributes
   - Positioned at cluster corners (bottom-left, bottom-right, etc.)

2. Top badge label (optional, positioned by graphviz cluster label):
   - Set via badge_label parameter
   - Appears at top of cluster (graphviz default positioning)
   - Can be text, icon, HTML table, or blank
   - Leave as None (default) for no badge

Example usage:
    # No top badge (default)
    rg = ResourceGroupCluster(label="Production")

    # With top badge icon only
    rg = ResourceGroupCluster(
        label="Production",
        badge_label='<<img src="/path/to/shield.png"/>>'
    )

    # With top badge text
    rg = ResourceGroupCluster(
        label="Production",
        badge_label="<SECURE>"
    )

    # With top badge icon + text
    rg = ResourceGroupCluster(
        label="Production",
        badge_label='<<TABLE BORDER="0"><TR><TD><img src="/path/to/shield.png"/></TD><TD>Compliant</TD></TR></TABLE>>'
    )
"""

import sys
import os
from pathlib import Path
from resource_classes import Cluster

defaultdir = "LR"
base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent


class AZUREGroup(Cluster):
    def __init__(self, label="", badge_label=None, **kwargs):
        azure_graph_attrs = {
            "style": "invis",  # No border
            "margin": "100",
            "ordering": "in",
            "center": "true",
            "labeljust": "l",
            "_shift": "1",
            "_cloudgroup": "1",
        }
        # Store label info for creating separate label node at bottom
        self.label_text = label
        self.label_icon = f"{base_path}/resource_images/azure/azure.png"
        self.label_position = "bottom-left"  # Position at bottom-left
        self.label_icon_first = True  # Icon before text

        # Optional top badge label (graphviz cluster label at top)
        # Can be text, icon, HTML table, or blank (None/empty string)
        cluster_label = badge_label if badge_label else ""

        super().__init__(cluster_label, defaultdir, azure_graph_attrs)


class ResourceGroupCluster(Cluster):
    def __init__(self, label="Resource Group", badge_label=None, **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "30",
            "pencolor": "#0078D4",
            "penwidth": "1",
            "rank": "same",
        }
        # Store label info for creating separate label node at bottom
        self.label_text = label
        self.label_icon = (
            f"{base_path}/resource_images/azure/general/resource-groups.png"
        )
        self.label_position = "bottom-left"  # Position for label node

        # Optional top badge label (graphviz cluster label at top)
        cluster_label = badge_label if badge_label else ""

        super().__init__(cluster_label, defaultdir, graph_attrs)


class VNetGroup(Cluster):
    def __init__(self, label="Virtual Network", badge_label=None, **kwargs):
        graph_attrs = {
            "style": "filled,dashed",  # Light blue fill with dotted dark blue border
            "fillcolor": "#E8F4FC",  # Light blue background
            "margin": "40",
            "pencolor": "#0078D4",  # Dark blue border
            "penwidth": "1.5",
            "rank": "same",
        }
        # Store label info for creating separate label node at bottom
        # Note: Native labelloc/labeljust don't work with neato for nested subgraphs,
        # so we use gvpr post-processing to position the label node
        self.label_text = label
        self.label_icon = (
            f"{base_path}/resource_images/azure/network/virtual-networks.png"
        )
        self.label_position = "bottom-right"  # Position for label node
        self.label_icon_first = False  # Icon after text for right alignment

        # Optional top badge label (graphviz cluster label at top)
        cluster_label = badge_label if badge_label else ""

        super().__init__(cluster_label, defaultdir, graph_attrs)


class SubnetGroup(Cluster):
    def __init__(self, label="Subnet", badge_label=None, **kwargs):
        graph_attrs = {
            "style": "filled",  # White fill with grey border (like Azure Architecture Center)
            "fillcolor": "#FFFFFF",
            "margin": "20",
            "pencolor": "#CCCCCC",  # Grey border
            "penwidth": "1",
        }
        # Store label info for creating separate label node at bottom
        self.label_text = label
        self.label_icon = f"{base_path}/resource_images/azure/networking/subnet.png"
        self.label_position = (
            "bottom-left"  # Position at bottom-left like Resource Group
        )
        self.label_icon_first = True  # Icon before text

        # Optional top badge label (graphviz cluster label at top)
        cluster_label = badge_label if badge_label else ""

        super().__init__(cluster_label, defaultdir, graph_attrs)


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


class AvailabilityZone(Cluster):
    def __init__(self, label="Zone 1", badge_label=None, **kwargs):
        graph_attrs = {
            "style": "rounded,filled",  # Rounded rectangle with fill
            "fillcolor": "#FAFAFA",  # Off-white/light gray
            "margin": "30",
            "pencolor": "#FFB900",  # Azure yellow/orange
            "penwidth": "2",
            "labeljust": "c",
            "labelloc": "b",  # Label at bottom
            "_shift": "0",
        }
        # Store label info for creating separate label node at bottom
        self.label_text = label
        self.label_icon = None  # No icon for zones
        self.label_position = "bottom-center"  # Center label at bottom

        # Optional top badge label (graphviz cluster label at top)
        cluster_label = badge_label if badge_label else ""

        super().__init__(cluster_label, defaultdir, graph_attrs)


class VMSSGroup(Cluster):
    def __init__(self, label="VM Scale Set", **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "30",
            "pencolor": "#0078D4",
            "penwidth": "1",
            "labeljust": "c",
        }
        vmss_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/azure/compute/vm-scale-sets.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(vmss_label, defaultdir, graph_attrs)


class SharedServicesGroup(Cluster):
    def __init__(self, label="Shared Services", **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "40",
            "pencolor": "#605E5C",
            "penwidth": "1",
        }
        super().__init__(label, defaultdir, graph_attrs)


# Aliases for Terraform resource type names
azurerm_resource_group = ResourceGroupCluster
azurerm_virtual_network = VNetGroup
azurerm_subnet = SubnetGroup
tv_azurerm_zone = AvailabilityZone  # Virtual zones for VMSS instances
azurerm_virtual_machine_scale_set = VMSSGroup
azurerm_group = SharedServicesGroup
