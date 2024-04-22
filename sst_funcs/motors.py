from ophyd import Device
from ophyd.utils.errors import DisconnectedError
from .help import add_to_func_list
from .printing import boxed_text
from .globalVars import GLOBAL_MOTORS, GLOBAL_MOTOR_DESCRIPTIONS, GLOBAL_HARDWARE


def add_motor(motor, description="", name=None):
    if name is None:
        name = motor.name
    GLOBAL_MOTORS[name] = motor
    GLOBAL_MOTOR_DESCRIPTIONS[name] = description


def remove_motor(motor_or_name):
    if hasattr(motor_or_name, "name"):
        name = motor_or_name.name
    else:
        name = motor_or_name
    if name not in GLOBAL_MOTORS:
        name = None
        for k, v in GLOBAL_MOTORS.items():
            if v == motor_or_name:
                name = k
                break
    if name is None:
        raise KeyError(f"Motor {motor_or_name} not found in global motors dictionary")

    del GLOBAL_MOTORS[name]
    del GLOBAL_MOTOR_DESCRIPTIONS[name]


def get_motor(dev_or_name):
    if isinstance(dev_or_name, Device):
        return dev_or_name
    elif dev_or_name in GLOBAL_MOTORS:
        return GLOBAL_MOTORS[dev_or_name]
    else:
        raise KeyError(f"Motor {dev_or_name} not found in GLOBAL_MOTORS")


@add_to_func_list
def list_motors(describe=False):
    """List the most important motors and their current positions"""

    title = "Motors"
    text = []
    for name, det in GLOBAL_MOTORS.items():
        try:
            position = det.position
        except DisconnectedError:
            position = "disconnected"
        text.append(f"{name}: {position}")
        if describe:
            text.append(f"    {GLOBAL_MOTOR_DESCRIPTIONS[name]}")
    boxed_text(title, text, "white")
