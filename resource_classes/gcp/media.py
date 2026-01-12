"""
GCP Media Services category - Transcoder, Live Stream, Video Stitcher.

Icon Resolution:
- All media resources use category icon (2-color): resource_images/gcp/category/media.png
"""

from . import _GCP


class _Media(_GCP):
    _type = "media"
    _icon_dir = "resource_images/gcp/category"
    _icon = "media.png"


class TranscoderAPI(_Media):
    """Transcoder API for video encoding."""

    pass


class LiveStreamAPI(_Media):
    """Live Stream API for real-time video."""

    pass


class VideoStitcherAPI(_Media):
    """Video Stitcher API for ad insertion."""

    pass


class MediaCDN(_Media):
    """Media CDN for streaming delivery."""

    pass


class SpeechToText(_Media):
    """Speech-to-Text API."""

    pass


class TextToSpeech(_Media):
    """Text-to-Speech API."""

    pass


class VideoIntelligence(_Media):
    """Video Intelligence API."""

    pass


# Aliases
Transcoder = TranscoderAPI
LiveStream = LiveStreamAPI
VideoStitcher = VideoStitcherAPI

# Terraform resource aliases
google_video_transcoder_job = TranscoderAPI
google_video_transcoder_job_template = TranscoderAPI
