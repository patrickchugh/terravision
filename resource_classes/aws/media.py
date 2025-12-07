from . import _AWS


class _Media(_AWS):
    _type = "media"
    _icon_dir = "resource_images/aws/media"


class ElasticTranscoder(_Media):
    _icon = "elastic-transcoder.png"


class ElementalConductor(_Media):
    _icon = "elemental-conductor.png"


class ElementalDelta(_Media):
    _icon = "elemental-delta.png"


class ElementalLive(_Media):
    _icon = "elemental-live.png"


class ElementalMediaconnect(_Media):
    _icon = "elemental-mediaconnect.png"


class ElementalMediaconvert(_Media):
    _icon = "elemental-mediaconvert.png"


class ElementalMedialive(_Media):
    _icon = "elemental-medialive.png"


class ElementalMediapackage(_Media):
    _icon = "elemental-mediapackage.png"


class ElementalMediastore(_Media):
    _icon = "elemental-mediastore.png"


class ElementalMediatailor(_Media):
    _icon = "elemental-mediatailor.png"


class ElementalServer(_Media):
    _icon = "elemental-server.png"


# Aliases

# Terraform aliases
aws_elastictranscoder_pipeline = ElasticTranscoder
aws_elastictranscoder_preset = ElasticTranscoder
aws_media_convert_queue = ElementalMediaconvert
aws_media_live_channel = ElementalMedialive
aws_media_package_channel = ElementalMediapackage
aws_media_store_container = ElementalMediastore
