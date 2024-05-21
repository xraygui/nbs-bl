from .globalVars import GLOBAL_SHUTTERS, GLOBAL_DEFAULT_SHUTTER, GLOBAL_HARDWARE
from .help import add_to_plan_list
from bluesky.plan_stubs import rd


@add_to_plan_list
def open_shutter():
    """Opens all default shutters, does not check any other shutters!"""
    for s in GLOBAL_DEFAULT_SHUTTER:
        shutter = GLOBAL_SHUTTERS[s]
        yield from shutter.open()


@add_to_plan_list
def close_shutter():
    """Closes all default shutters"""
    for s in GLOBAL_DEFAULT_SHUTTER:
        shutter = GLOBAL_SHUTTERS[s]
        yield from shutter.close()


@add_to_plan_list
def is_shutter_open():
    states = []
    for s in GLOBAL_SHUTTERS.values():
        state = yield from rd(s.state)
        states.append(state == s.openval)
    return all(states)


def are_shutters_open():
    states = []
    for s in GLOBAL_SHUTTERS.values():
        state = yield from rd(s.state)
        states.append(state == s.openval)
    return all(states)


def add_shutter(shutter, name=None, default=False, **kwargs):
    if name is None:
        name = shutter.name
    GLOBAL_SHUTTERS[name] = shutter
    if default:
        GLOBAL_DEFAULT_SHUTTER.append(name)
    return name
