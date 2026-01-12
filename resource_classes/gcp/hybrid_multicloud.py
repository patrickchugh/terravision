"""
GCP Hybrid & Multicloud category - Anthos, Distributed Cloud, GKE Enterprise.

Icon Resolution:
- Anthos uses unique icon (4-color): resource_images/gcp/unique/anthos.png
- Distributed Cloud uses unique icon (4-color): resource_images/gcp/unique/distributed-cloud.png
- Other hybrid resources use category icon (2-color): resource_images/gcp/category/hybrid-multicloud.png
"""

from . import _GCP


class _HybridMulticloud(_GCP):
    _type = "hybrid_multicloud"
    _icon_dir = "resource_images/gcp/category"
    _icon = "hybrid-multicloud.png"


class Anthos(_HybridMulticloud):
    """Anthos hybrid/multicloud platform - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "anthos.png"


class DistributedCloud(_HybridMulticloud):
    """Distributed Cloud edge computing - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "distributed-cloud.png"


class GKEEnterprise(_HybridMulticloud):
    """GKE Enterprise fleet management."""

    _icon = "hybrid-multicloud.png"


class AnthosServiceMesh(_HybridMulticloud):
    """Anthos Service Mesh (Istio-based)."""

    _icon = "hybrid-multicloud.png"


class AnthosConfigManagement(_HybridMulticloud):
    """Anthos Config Management GitOps."""

    _icon = "hybrid-multicloud.png"


class ConnectGateway(_HybridMulticloud):
    """Connect gateway for cluster access."""

    _icon = "hybrid-multicloud.png"


class EdgeTPU(_HybridMulticloud):
    """Edge TPU ML acceleration."""

    _icon = "hybrid-multicloud.png"


class DistributedCloudEdge(_HybridMulticloud):
    """Distributed Cloud Edge for 5G."""

    _icon = "hybrid-multicloud.png"


# Aliases
AnthosFleet = GKEEnterprise
ASM = AnthosServiceMesh
ACM = AnthosConfigManagement

# Terraform resource aliases
google_gke_hub_membership = Anthos
google_gke_hub_feature = Anthos
google_gke_hub_feature_membership = Anthos
google_gke_hub_fleet = GKEEnterprise
google_gke_hub_namespace = GKEEnterprise
google_gke_hub_scope = GKEEnterprise
