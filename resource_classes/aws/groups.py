import sys
import os
import shutil
from pathlib import Path
from resource_classes import Cluster

defaultdir = "LR"
base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent


def _icon_cell(icon: str, size: int) -> str:
    """A box label's icon, resource_images/aws/<icon> scaled into size points.

    A fixed cell, so the box lays out the same whatever the icon's pixel size:
    94 points is what a 120 px icon took at its natural size (Graphviz reads
    PNGs at 96 dpi, plus the cell's 2-point padding), 51 a 62 px subnet badge.
    """
    return (
        f'<TD FIXEDSIZE="TRUE" WIDTH="{size}" HEIGHT="{size}">'
        f'<IMG SCALE="TRUE" SRC="{base_path}/resource_images/aws/{icon}"/></TD>'
    )


class VPCgroup(Cluster):
    def __init__(self, label, **kwargs):
        vpc_graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "#8c4fff",
            "rank": "same",
        }
        vpc_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell("group/virtual-private-cloud-vpc.png", 94)}<TD>{label}</TD></TR></TABLE>>'
        super().__init__(vpc_label, defaultdir, vpc_graph_attrs)


class RegionGroup(Cluster):
    def __init__(self, label, **kwargs):
        region_graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "#00a4a6",
            "rank": "same",
        }
        region_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell("group/region.png", 94)}<TD>{label}</TD></TR></TABLE>>'
        super().__init__(region_label, defaultdir, region_graph_attrs)


class SubnetGroup(Cluster):
    def __init__(self, label, **kwargs):
        if "Public" in label:
            image = "group/public-subnet.png"
            border_col = "#248814"
        else:
            image = "group/private-subnet.png"
            border_col = "#147EBA"
        vpc_graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": border_col,
            "_shift": "1",
        }
        subnet_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell(image, 51)}<TD>{label}</TD></TR></TABLE>>'
        super().__init__(subnet_label, defaultdir, vpc_graph_attrs)


class SecurityGroup(Cluster):
    def __init__(self, label, **kwargs):
        vpc_graph_attrs = {"style": "solid", "margin": "50", "pencolor": "red"}
        super().__init__(label, defaultdir, vpc_graph_attrs)


class GenericAutoScalingGroup(Cluster):
    def __init__(self, label="AWS AutoScaling", **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "50",
            "color": "#deebf7",
            "pencolor": "pink",
            "labeljust": "c",
            "_shift": "0",
        }
        cluster_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell("group/auto-scaling-group.png", 94)}</TR><TR><TD>{label}</TD></TR></TABLE>>'
        super().__init__(cluster_label, defaultdir, graph_attrs)


class GenericGroup(Cluster):
    def __init__(self, label="Shared Services", **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "100",
            "pencolor": "black",
        }
        super().__init__(label, defaultdir, graph_attrs)


class AvailabilityZone(Cluster):
    def __init__(self, label="Availability Zone", **kwargs):
        graph_attrs = {
            "style": "dashed",
            "margin": "100",
            "pencolor": "#3399ff",
            "center": "true",
            "labeljust": "c",
            "_shift": "0",
        }
        cluster_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><FONT point-size="44" color="#3399ff">{label}</FONT></TD></TR></TABLE>>'
        super().__init__(cluster_label, defaultdir, graph_attrs)


class SecurityGroup(Cluster):
    def __init__(self, label="Security Group", **kwargs):
        graph_attrs = {
            "style": "solid",
            "margin": "50",
            "pencolor": "red",
            "center": "true",
            "labeljust": "c",
            "_shift": "0",
        }
        cluster_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><FONT color="red">{label}</FONT></TD></TR></TABLE>>'
        super().__init__(cluster_label, defaultdir, graph_attrs)


class AWSGroup(Cluster):
    def __init__(self, label="AWS Cloud", **kwargs):
        aws_graph_attrs = {
            "style": "solid",
            "pencolor": "black",
            "margin": "100",
            "ordering": "in",
            "penwidth": "2",
            "center": "true",
            "labeljust": "l",
            "_shift": "1",
            "_cloudgroup": "1",
        }
        aws_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell("group/cloud-logo.png", 94)}<TD>{label}</TD></TR></TABLE>>'
        super().__init__(aws_label, defaultdir, aws_graph_attrs)


class AWSAccount(Cluster):
    def __init__(self, label="AWS Account", **kwargs):
        aws_graph_attrs = {
            "style": "solid",
            "pencolor": "#e7157b",
            "margin": "100",
            "ordering": "in",
            "penwidth": "2",
            "center": "true",
            "labeljust": "l",
            "_shift": "1",
        }
        aws_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell("group/account.png", 94)}<TD>{label}</TD></TR></TABLE>>'
        super().__init__(aws_label, defaultdir, aws_graph_attrs)


class OnPrem(Cluster):
    def __init__(self, label="Corporate Datacenter", **kwargs):
        aws_graph_attrs = {
            "style": "solid",
            "pencolor": "black",
            "margin": "100",
            "ordering": "in",
            "center": "true",
            "labeljust": "l",
            "_shift": "1",
        }
        aws_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR>{_icon_cell("group/corporate-data-center.png", 90)}<TD>{label}</TD></TR></TABLE>>'
        super().__init__(aws_label, defaultdir, aws_graph_attrs)


aws_vpc = VPCgroup
aws_group = GenericGroup
aws_account = AWSAccount
aws_security_group = SecurityGroup
aws_subnet = SubnetGroup
aws_appautoscaling_target = GenericAutoScalingGroup
aws_autoscaling_group = GenericAutoScalingGroup
tv_aws_onprem = OnPrem
aws_az = AvailabilityZone
tv_aws_az = AvailabilityZone
tv_aws_region = RegionGroup
aws_region = RegionGroup
