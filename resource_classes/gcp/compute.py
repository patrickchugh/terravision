from . import _GCP


class _Compute(_GCP):
    _type = "compute"
    _icon_dir = "resources/gcp/compute"


class AppEngine(_Compute):
    _icon = "app-engine.png"


class BinaryAuthorization(_Compute):
    _icon = "binary-authorization.png"


class ComputeEngine(_Compute):
    _icon = "compute-engine.png"


class ContainerOptimizedOS(_Compute):
    _icon = "container-optimized-os.png"


class Functions(_Compute):
    _icon = "functions.png"


class GKEOnPrem(_Compute):
    _icon = "gke-on-prem.png"


class GPU(_Compute):
    _icon = "gpu.png"


class KubernetesEngine(_Compute):
    _icon = "kubernetes-engine.png"


class OSConfigurationManagement(_Compute):
    _icon = "os-configuration-management.png"


class OSInventoryManagement(_Compute):
    _icon = "os-inventory-management.png"


class OSPatchManagement(_Compute):
    _icon = "os-patch-management.png"


class Run(_Compute):
    _icon = "run.png"


# Aliases

GAE = AppEngine
GCE = ComputeEngine
GCF = Functions
GKE = KubernetesEngine
CloudRun = Run

# Terraform aliases
google_app_engine_application = AppEngine
google_compute_instance = ComputeEngine
google_compute_instance_template = ComputeEngine
google_compute_instance_group = ComputeEngine
google_compute_instance_group_manager = ComputeEngine
google_cloudfunctions_function = Functions
google_cloudfunctions2_function = Functions
google_container_cluster = KubernetesEngine
google_container_node_pool = KubernetesEngine
google_cloud_run_service = Run
google_cloud_run_v2_service = Run
