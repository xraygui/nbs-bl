from .beamline import GLOBAL_BEAMLINE
from .help import add_to_plan_list, add_to_func_list
from bluesky.plan_stubs import rd


def _get_shutter(shutter):
    if shutter is None:
        return GLOBAL_BEAMLINE.default_shutter
    shutters = GLOBAL_BEAMLINE.shutters.devices
    if shutter not in shutters:
        raise ValueError(f"{shutter!r} is not a shutter; shutters are {sorted(shutters)}")
    return shutters[shutter]


@add_to_plan_list
def open_shutter(shutter: str = None):
    """
    Open a shutter.

    Parameters
    ----------
    shutter : str, optional
        Name of a device in the shutters group. Defaults to the default
        shutter. Other shutters are not checked.
    """
    device = _get_shutter(shutter)
    if device is not None:
        yield from device.open()


@add_to_plan_list
def close_shutter(shutter: str = None):
    """
    Close a shutter.

    Parameters
    ----------
    shutter : str, optional
        Name of a device in the shutters group. Defaults to the default
        shutter.
    """
    device = _get_shutter(shutter)
    if device is not None:
        yield from device.close()


@add_to_plan_list
def is_shutter_open():
    states = []
    for s in GLOBAL_BEAMLINE.shutters.values():
        state = yield from rd(s.state)
        states.append(state == s.openval)
    return all(states)


@add_to_func_list
def list_shutters():
    def textFunction(key, device):
        name = device.name
        state = "Open" if device.state.get() == device.openval else "Closed"
        text = f"{key}: {name}; {state}"
        return text

    GLOBAL_BEAMLINE.shutters.describe(textFunction=textFunction)
