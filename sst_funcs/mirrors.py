from .globalVars import GLOBAL_MIRRORS


def add_mirror(dev, name=None, **kwargs):
    if name is None:
        name = dev.name
    GLOBAL_MIRRORS[name] = dev
    return name
