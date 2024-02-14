from .globalVars import GLOBAL_GATEVALVES

def add_valve(det, name=None):
    if name is None:
        name = det.name
    GLOBAL_GATEVALVES[name] = det
    return name
