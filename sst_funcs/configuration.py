import yaml
from copy import deepcopy
from importlib import import_module
from os.path import join, dirname
from .detectors import add_detector
from .motors import add_motor
from .shutters import add_shutter
from .mirrors import add_mirror
from .gatevalves import add_valve
from .manipulators import add_manipulator

GLOBAL_CONF_DB = {}

_group_load_map = {}
_group_load_map['detectors'] = add_detector
_group_load_map['motors'] = add_motor
_group_load_map['shutters'] = add_shutter
_group_load_map['mirrors'] = add_mirror
_group_load_map['gatevalves'] = add_valve
#_group_load_map['manipulators'] = add_manipulator

# configfile = join(dirname(__file__), "config.yaml")
# configdb = loadConfigDB(configfile)
def loadConfigDB(filename, saveGlobal=True):
    global GLOBAL_CONF_DB
    with open(filename) as f:
        db = yaml.safe_load(f)
    if saveGlobal:
        GLOBAL_CONF_DB = db
    return db


def getConfigDB(config=None):
    if isinstance(config, dict):
        db = config
    elif config is not None:
        db = loadConfigDB(config, saveGlobal=False)
    else:
        db = GLOBAL_CONF_DB
    return db


def simpleResolver(fullclassname):
    class_name = fullclassname.split(".")[-1]
    module_name = ".".join(fullclassname.split(".")[:-1])
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls


def getObjConfig(name, config=None):
    confdb = getConfigDB(config)
    for objdb in confdb.values():
        if name in objdb:
            objconf = deepcopy(objdb.get("_default", {}))
            objconf.update(objdb[name])
            return objconf
    return None


def getGroupConfig(group_name, config=None):
    objdb = getConfigDB(config)[group_name]

    devicedb = {}
    for name in objdb:
        if name == '_default':
            continue
        objconf = deepcopy(objdb.get("_default", {}))
        objconf.update(objdb[name])
        devicedb[name] = objconf
    return devicedb


def findAndLoadDevice(name, cls=None, config=None):
    device_info = getObjConfig(name, config=config)
    return instantiateDevice(name, device_info, cls)


"""
def instantiateDevice(device_info, cls=None, namespace=None):
    if cls is not None:
        device_info.pop("_target_")
        prefix = device_info.pop("prefix", "")
        return cls(prefix, **device_info)
    elif device_info.get('_target_', None) is not None:
        cls = simpleResolver(device_info.pop('_target_'))
        prefix = device_info.pop('prefix', '')
        return cls(prefix, **device_info)
    else:
        raise KeyError("Could not find '_target_' in {}".format(device_info))
"""


def instantiateDevice(device_key, device_info, cls=None,
                      namespace=None, add_to_global=None):
    if cls is not None:
        device_info.pop("_target_", None)
    elif device_info.get('_target_', None) is not None:
        cls = simpleResolver(device_info.pop('_target_'))
    else:
        raise KeyError("Could not find '_target_' in {}".format(device_info))

    prefix = device_info.pop("prefix", "")
    add_to_namespace = device_info.pop("_add_to_ns_", True)
    extra_info = device_info.pop("_extra_", {})
    device = cls(prefix, **device_info)

    if add_to_namespace and namespace is not None:
        namespace[device_key] = device
    if add_to_global is not None:
        f"Adding {device_key} to {add_to_global}"
        add_to_global(device, name=device_key, **extra_info)
    return device


def instantiateGroup(group_name, namespace=None, cls=None, config=None):
    group_config = getGroupConfig(group_name, config=config)
    add_to_global = _group_load_map.get(group_name, None)
    group_dict = {}
    for device_key, device_info in group_config.items():
        dev = instantiateDevice(device_key, device_info, cls,
                                namespace, add_to_global)
        group_dict[device_key] = dev
    return group_dict


def loadDeviceConfig(filename, namespace=None):
    db = loadConfigDB(filename)
    device_dict = {}
    for group in db:
        group_dict = instantiateGroup(group, namespace)
        device_dict.update(group_dict)
    return device_dict
