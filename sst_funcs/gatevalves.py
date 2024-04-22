from .globalVars import GLOBAL_GATEVALVES, GLOBAL_HARDWARE


def configure_valves(config_dict):
    include = config_dict.get("include", [])
    configuration = config_dict.get("configuration", {})
    for device in include:
        det = GLOBAL_HARDWARE[device]
        add_valve(det, name=device, **configuration.get(device, {}))


def add_valve(det, name=None):
    if name is None:
        name = det.name
    GLOBAL_GATEVALVES[name] = det
    return name
