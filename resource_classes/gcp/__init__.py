"""
GCP provides a set of services for Google Cloud Platform provider.

Icon Resolution (3-tier priority fallback):
1. Unique icons (4-color) - resource_images/gcp/unique/<icon>.png
2. Category icons (2-color) - resource_images/gcp/category/<icon>.png
3. Generic placeholder - resource_images/generic/generic.png

The _load_icon() method in resource_classes/__init__.py handles this fallback
automatically for all GCP resources.

"""

from resource_classes import Node
from typing import Dict


class _GCP(Node):
    _provider = "gcp"
    _icon_dir = (
        "resource_images/gcp/category"  # Default to category icons (2-color fallback)
    )

    fontcolor = "#2d3436"

    def __init__(self, label: str = "", **attrs: Dict):
        """GCP Node with label positioned to the right of icon using HTML table.

        For GCP resources, uses HTML-like labels to create a two-column layout
        with the icon on the left and label text on the right, styled like a record.

        :param label: Node label text
        :param attrs: Additional node attributes
        """
        # Generate node ID (from parent's _rand_id logic)
        import uuid

        self._id = f"{self._provider}.{self._type}.{self.__class__.__name__}.{uuid.uuid4().hex}"
        self.label = label

        # Get diagram and cluster context (required for all nodes)
        from resource_classes import getdiagram, getcluster

        self._diagram = getdiagram()
        if self._diagram is None:
            raise EnvironmentError("Global resource_classes context not set up")
        self._cluster = getcluster()

        # Extract custom TerraVision attributes (not passed to graphviz)
        is_outer_node = attrs.pop("outer_node", False)

        # Build attributes for GCP node with HTML table layout
        if self._icon:
            # Load icon path
            icon_path = self._load_icon()

            # Split label into service (bold) and resource name (regular)
            # Use the original Terraform resource name (tf_resource_name) to identify the split
            # The dot (.) in Terraform separates resource type from instance name
            # Examples:
            # google_compute_instance.web -> type: compute_instance, instance: web
            # google_compute_instance_template.template1 -> type: compute_instance_template, instance: template1

            # Get the Terraform resource name if available
            tf_resource_name = attrs.get("tf_resource_name", "")

            # Remove any newlines from label (pretty_name can insert soft breaks)
            label_clean = label.replace("\n", " ")

            # Try to split based on the dot in the Terraform resource name
            if tf_resource_name and "." in tf_resource_name:
                # Extract instance name from terraform resource (the LAST part after the last dot)
                # google_compute_instance_template.template1 -> template1
                # module.gce-lb-http.google_compute_global_address.default[0]~1 -> default[0]~1
                tf_instance_name = tf_resource_name.rsplit(".", 1)[-1].strip()

                # Remove array indices like [0], ["default"], etc.
                if "[" in tf_instance_name:
                    tf_instance_name = tf_instance_name.split("[")[0]

                # Remove numbered suffixes like ~1, ~2
                if "~" in tf_instance_name:
                    tf_instance_name = tf_instance_name.split("~")[0]

                # Convert instance name to title case to match pretty_name format
                # template1 -> Template1, my_bucket -> My Bucket, web-server -> Web Server
                # Replace both underscores and hyphens with spaces to match pretty_name behavior
                tf_instance_formatted = (
                    tf_instance_name.replace("_", " ").replace("-", " ").title()
                )

                # Find where this instance name appears in the label (case-insensitive)
                # This handles cases where pretty_name might add/remove words or use acronyms
                # Example: "http" -> "Http" (title) but pretty_name returns "HTTP" (acronym)
                label_lower = label_clean.lower()
                instance_lower = tf_instance_formatted.lower()

                if instance_lower in label_lower:
                    idx = label_lower.index(instance_lower)
                    service_part = label_clean[:idx].strip()
                    instance_part = label_clean[idx:].strip()

                    if service_part and instance_part:
                        formatted_label = f"<B>{service_part}</B><BR/>{instance_part}"
                    else:
                        # Couldn't split properly, bold entire label
                        formatted_label = f"<B>{label_clean}</B>"
                else:
                    # Instance name not found in label, bold entire label
                    formatted_label = f"<B>{label_clean}</B>"
            else:
                # No tf_resource_name or no dot, bold entire label
                formatted_label = f"<B>{label_clean}</B>"

            # Create HTML table styled to look like a record
            # Make table full width to match the width attribute
            # Increased dimensions: 360x140 points (was 252x94)
            # Use nested table for text to ensure both lines are left-aligned

            # Split formatted label into lines for explicit alignment control
            if "<BR/>" in formatted_label:
                # Two-line label: split on BR tag
                lines = formatted_label.split("<BR/>")
                text_table = f"""<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0">
      <TR><TD ALIGN="LEFT"><FONT FACE="Sans-Serif" POINT-SIZE="24">{lines[0]}</FONT></TD></TR>
      <TR><TD ALIGN="LEFT"><FONT FACE="Sans-Serif" POINT-SIZE="24">{lines[1]}</FONT></TD></TR>
    </TABLE>"""
            else:
                # Single-line label
                text_table = f"""<FONT FACE="Sans-Serif" POINT-SIZE="24">{formatted_label}</FONT>"""

            # Outer nodes have no border (already extracted from attrs above)
            border = "0" if is_outer_node else "1"
            color_attr = "" if is_outer_node else ' COLOR="#999999"'

            html_label = f"""<
<TABLE BORDER="{border}" CELLBORDER="0" CELLSPACING="0" CELLPADDING="8" WIDTH="360"{color_attr}>
  <TR>
    <TD FIXEDSIZE="TRUE" WIDTH="100" HEIGHT="100"><IMG SRC="{icon_path}"/></TD>
    <TD ALIGN="LEFT" VALIGN="MIDDLE">{text_table}</TD>
  </TR>
</TABLE>>"""

            # Also set fontsize at the node level
            node_fontsize = "24"

            # Set attributes for HTML-based node (no image attribute)
            # Use width to force spacing, no fixed height to let content determine it
            self._attrs = {
                "shape": "plaintext",
                "tf_resource_name": "unknown",
                "width": "5.0",  # 360 points / 72 dpi = 5.0 inches
                "label": html_label,
                "fontsize": node_fontsize,  # Set font size for the label
                "margin": "0",
            }
        else:
            # Fallback for nodes without icons - use parent's default logic
            super().__init__(label, **attrs)
            return

        # Apply any additional attributes passed in
        self._attrs.update(attrs)

        # Add node to diagram/cluster (only once!)
        if self._cluster:
            self._cluster.node(self._id, **self._attrs)
        else:
            self._diagram.node(self._id, **self._attrs)


class GCP(_GCP):
    _icon_dir = "resource_images/gcp"  # Root GCP icon stays in root
    _icon = "gcp.png"


# Import all category modules for easy access
from . import (
    compute,
    containers,
    serverless,
    databases,
    storage,
    networking,
    ai_ml,
    analytics,
    security,
    management,
    observability,
    devops,
    developer_tools,
    hybrid_multicloud,
    integration,
    migration,
    business_intelligence,
    agents,
    collaboration,
    media,
    maps,
    marketplace,
    mixed_reality,
    web_mobile,
    web3,
    groups,
    generic,
)
