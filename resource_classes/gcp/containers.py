"""
GCP Containers category - GKE, Artifact Registry, and container services.

Icon Resolution:
- GKE uses unique icon (4-color): resource_images/gcp/unique/gke.png
- Anthos uses unique icon (4-color): resource_images/gcp/unique/anthos.png
- Other container resources use category icon (2-color): resource_images/gcp/category/containers.png
"""

from . import _GCP


class _Containers(_GCP):
    _type = "containers"
    _icon_dir = "resource_images/gcp/category"
    _icon = "containers.png"


class KubernetesEngine(_Containers):
    """Google Kubernetes Engine - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "gke.png"


class Anthos(_Containers):
    """Anthos hybrid/multicloud platform - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "anthos.png"


class ArtifactRegistry(_Containers):
    """Artifact Registry for container images and packages."""

    _icon = "containers.png"


class ContainerRegistry(_Containers):
    """Container Registry (legacy, use Artifact Registry)."""

    _icon = "containers.png"


class BinaryAuthorization(_Containers):
    """Binary Authorization for container security."""

    _icon = "containers.png"


class ContainerOptimizedOS(_Containers):
    """Container-Optimized OS for VMs."""

    _icon = "containers.png"


class GKEOnPrem(_Containers):
    """GKE on-premises deployment."""

    _icon = "containers.png"


# Aliases
GKE = KubernetesEngine

# Terraform resource aliases
google_container_cluster = KubernetesEngine
google_container_node_pool = KubernetesEngine
google_gke_hub_membership = Anthos
google_gke_hub_feature = Anthos
google_artifact_registry_repository = ArtifactRegistry
google_container_registry = ContainerRegistry
google_binary_authorization_policy = BinaryAuthorization
