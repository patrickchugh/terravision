from . import _AWS


class _Satellite(_AWS):
    _type = "satellite"
    _icon_dir = "resource_images/aws/satellite"


class GroundStation(_Satellite):
    _icon = "ground-station.png"


# Aliases

# Terraform aliases
aws_groundstation_config = GroundStation
aws_groundstation_mission_profile = GroundStation
