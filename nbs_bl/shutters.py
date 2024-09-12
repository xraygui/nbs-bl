from .globalVars import GLOBAL_BEAMLINE
from .help import add_to_plan_list, add_to_func_list
from bluesky.plan_stubs import rd


@add_to_plan_list
def open_shutter():
    """Opens all default shutters, does not check any other shutters!"""
    shutter = GLOBAL_BEAMLINE.default_shutter
    if shutter is not None:
        yield from shutter.open()


@add_to_plan_list
def close_shutter():
    """Closes all default shutters"""
    shutter = GLOBAL_BEAMLINE.default_shutter
    if shutter is not None:
        yield from shutter.close()


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
