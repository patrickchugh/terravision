"""
GCP Compute category - VMs, instance groups, and compute resources.

Icon Resolution:
- Compute Engine uses unique icon (4-color): resource_images/gcp/unique/compute-engine.png
- Other compute resources use category icon (2-color): resource_images/gcp/category/compute.png
"""

from . import _GCP


class _Compute(_GCP):
    _type = "compute"
    _icon_dir = "resource_images/gcp/category"
    _icon = "compute.png"


class ComputeEngine(_Compute):
    """GCP Compute Engine VM instances - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "compute-engine.png"


class InstanceTemplate(_Compute):
    """Instance templates for VM creation."""

    _icon = "compute.png"


class InstanceGroup(_Compute):
    """Managed and unmanaged instance groups."""

    _icon = "compute.png"


class MachineImage(_Compute):
    """Machine images for VM cloning."""

    _icon = "compute.png"


class Snapshot(_Compute):
    """Disk snapshots."""

    _icon = "compute.png"


class Disk(_Compute):
    """Persistent disks."""

    _icon = "compute.png"


class Image(_Compute):
    """Custom OS images."""

    _icon = "compute.png"


class SoleTenantNode(_Compute):
    """Sole-tenant nodes for dedicated hardware."""

    _icon = "compute.png"


class Reservation(_Compute):
    """Capacity reservations."""

    _icon = "compute.png"


class CommitmentPlan(_Compute):
    """Committed use discounts."""

    _icon = "compute.png"


# Aliases
GCE = ComputeEngine
VM = ComputeEngine

# Terraform resource aliases
google_compute_instance = ComputeEngine
google_compute_instance_template = InstanceTemplate
google_compute_instance_group = InstanceGroup
google_compute_instance_group_manager = (
    InstanceGroup  # Renders as node, points to managed instances
)
google_compute_region_instance_group_manager = (
    InstanceGroup  # Renders as node, points to managed instances
)
google_compute_machine_image = MachineImage
google_compute_snapshot = Snapshot
google_compute_disk = Disk
google_compute_image = Image
google_compute_node_template = SoleTenantNode
google_compute_node_group = SoleTenantNode
google_compute_reservation = Reservation
google_compute_resource_policy = CommitmentPlan
