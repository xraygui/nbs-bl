from ophyd.utils.errors import DisconnectedError
from .beamline import GLOBAL_BEAMLINE
from .help import add_to_func_list


@add_to_func_list
def list_motors(verbose=False):
    """List the most important motors and their current positions"""

    def textFunction(motors, key, device):
        name = device.name
        try:
            position = device.position
        except DisconnectedError:
            position = "disconnected"
        text = f"{name}: {position}"
        return text

    GLOBAL_BEAMLINE.motors.describe(verbose, textFunction)
