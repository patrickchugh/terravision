"""
GCP AI & Machine Learning category - Vertex AI, AutoML, AI Platform.

Icon Resolution:
- Vertex AI uses unique icon (4-color): resource_images/gcp/unique/vertex-ai.png
- AI Hypercomputer uses unique icon (4-color): resource_images/gcp/unique/ai-hypercomputer.png
- Other AI/ML resources use category icon (2-color): resource_images/gcp/category/ai-ml.png
"""

from . import _GCP


class _AIML(_GCP):
    _type = "ai_ml"
    _icon_dir = "resource_images/gcp/category"
    _icon = "ai-ml.png"


class VertexAI(_AIML):
    """Vertex AI unified ML platform - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "vertex-ai.png"


class AIHypercomputer(_AIML):
    """AI Hypercomputer for training - has unique 4-color icon."""

    _icon_dir = "resource_images/gcp/unique"
    _icon = "ai-hypercomputer.png"


class AutoML(_AIML):
    """AutoML for custom models."""

    _icon = "ai-ml.png"


class AIPlatform(_AIML):
    """AI Platform (legacy Vertex AI predecessor)."""

    _icon = "ai-ml.png"


class NaturalLanguage(_AIML):
    """Natural Language API."""

    _icon = "ai-ml.png"


class Vision(_AIML):
    """Vision API."""

    _icon = "ai-ml.png"


class Translation(_AIML):
    """Translation API."""

    _icon = "ai-ml.png"


class SpeechToText(_AIML):
    """Speech-to-Text API."""

    _icon = "ai-ml.png"


class TextToSpeech(_AIML):
    """Text-to-Speech API."""

    _icon = "ai-ml.png"


class DialogflowCX(_AIML):
    """Dialogflow CX conversational AI."""

    _icon = "ai-ml.png"


class DocumentAI(_AIML):
    """Document AI for document processing."""

    _icon = "ai-ml.png"


class RecommendationsAI(_AIML):
    """Recommendations AI."""

    _icon = "ai-ml.png"


class TensorFlow(_AIML):
    """TensorFlow on GCP."""

    _icon = "ai-ml.png"


# Aliases
Vertex = VertexAI
ML = VertexAI

# Terraform resource aliases
google_vertex_ai_dataset = VertexAI
google_vertex_ai_featurestore = VertexAI
google_vertex_ai_endpoint = VertexAI
google_vertex_ai_model = VertexAI
google_vertex_ai_tensorboard = VertexAI
google_vertex_ai_metadata_store = VertexAI
google_ml_engine_model = AIPlatform
google_notebooks_instance = VertexAI
google_notebooks_runtime = VertexAI
google_dialogflow_cx_agent = DialogflowCX
google_dialogflow_cx_flow = DialogflowCX
google_document_ai_processor = DocumentAI
