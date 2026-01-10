"""
GCP Agents category - Dialogflow, Agent Builder, Conversational AI.

Icon Resolution:
- All agents resources use category icon (2-color): resource_images/gcp/category/agents.png
"""

from . import _GCP


class _Agents(_GCP):
    _type = "agents"
    _icon_dir = "resource_images/gcp/category"
    _icon = "agents.png"


class DialogflowCX(_Agents):
    """Dialogflow CX for conversational AI."""

    pass


class DialogflowES(_Agents):
    """Dialogflow ES (Enterprise Edition)."""

    pass


class AgentBuilder(_Agents):
    """Vertex AI Agent Builder."""

    pass


class AgentAssist(_Agents):
    """Agent Assist for contact centers."""

    pass


class CCAI(_Agents):
    """Contact Center AI."""

    pass


# Aliases
Dialogflow = DialogflowCX

# Terraform resource aliases
google_dialogflow_cx_agent = DialogflowCX
google_dialogflow_cx_flow = DialogflowCX
google_dialogflow_cx_intent = DialogflowCX
google_dialogflow_cx_page = DialogflowCX
google_dialogflow_agent = DialogflowES
google_dialogflow_intent = DialogflowES
google_dialogflow_entity_type = DialogflowES
