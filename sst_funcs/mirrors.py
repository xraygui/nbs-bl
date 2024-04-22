from .globalVars import GLOBAL_MIRRORS, GLOBAL_HARDWARE


def configure_mirrors(config_dict):
    include = config_dict.get("include", [])
    configuration = config_dict.get("configuration", {})
    for device in include:
        det = GLOBAL_HARDWARE[device]
        add_mirror(det, name=device, **configuration.get(device, {}))


def add_mirror(dev, name=None, **kwargs):
    if name is None:
        name = dev.name
    GLOBAL_MIRRORS[name] = dev
    return name
