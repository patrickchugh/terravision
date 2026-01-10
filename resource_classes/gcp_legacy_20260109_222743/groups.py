import sys
import os
from pathlib import Path
from resource_classes import Cluster

defaultdir = "LR"
base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent


class GCPGroup(Cluster):
    def __init__(self, label="Google Cloud", **kwargs):
        gcp_graph_attrs = {
            "style": "solid",
            "pencolor": "#4285F4",
            "margin": "100",
            "ordering": "in",
            "penwidth": "2",
            "center": "true",
            "labeljust": "l",
            "_shift": "1",
            "_cloudgroup": "1",
        }
        gcp_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0"><TR><TD><img src="{base_path}/resource_images/gcp/gcp.png"/></TD><TD>{label}</TD></TR></TABLE>>'
        super().__init__(gcp_label, defaultdir, gcp_graph_attrs)
