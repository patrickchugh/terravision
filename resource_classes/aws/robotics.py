from . import _AWS


class _Robotics(_AWS):
    _type = "robotics"
    _icon_dir = "resource_images/aws/robotics"


class RobomakerSimulator(_Robotics):
    _icon = "robomaker-simulator.png"


class Robomaker(_Robotics):
    _icon = "robomaker.png"


class Robotics(_Robotics):
    _icon = "robotics.png"


# Aliases

# Terraform aliases
aws_robomaker_robot_application = Robomaker
aws_robomaker_simulation_application = RobomakerSimulator
aws_robomaker_simulation_job = RobomakerSimulator
