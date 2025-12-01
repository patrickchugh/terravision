"""
DEPRECATED: This file provides backwards compatibility only.

All cloud provider configuration has been moved to modules/cloud_config/.
New code should import from:
  - modules.cloud_config.aws
  - modules.cloud_config.azure
  - modules.cloud_config.gcp

This file will be removed in a future version.
"""

# Import all AWS constants from the new location for backwards compatibility
from modules.cloud_config.aws import (
    CONSOLIDATED_NODES as AWS_CONSOLIDATED_NODES,
    GROUP_NODES as AWS_GROUP_NODES,
    EDGE_NODES as AWS_EDGE_NODES,
    OUTER_NODES as AWS_OUTER_NODES,
    DRAW_ORDER as AWS_DRAW_ORDER,
    AUTO_ANNOTATIONS as AWS_AUTO_ANNOTATIONS,
    NODE_VARIANTS as AWS_NODE_VARIANTS,
    REVERSE_ARROW_LIST as AWS_REVERSE_ARROW_LIST,
    FORCED_DEST as AWS_FORCED_DEST,
    FORCED_ORIGIN as AWS_FORCED_ORIGIN,
    IMPLIED_CONNECTIONS as AWS_IMPLIED_CONNECTIONS,
    SPECIAL_RESOURCES as AWS_SPECIAL_RESOURCES,
    SHARED_SERVICES as AWS_SHARED_SERVICES,
    ALWAYS_DRAW_LINE as AWS_ALWAYS_DRAW_LINE,
    NEVER_DRAW_LINE as AWS_NEVER_DRAW_LINE,
    DISCONNECT_LIST as AWS_DISCONNECT_LIST,
    ACRONYMS_LIST as AWS_ACRONYMS_LIST,
    NAME_REPLACEMENTS as AWS_NAME_REPLACEMENTS,
)
