import yaml
from copy import deepcopy
from importlib import import_module
from os.path import join, dirname

GLOBAL_CONF_DB = {}


# configfile = join(dirname(__file__), "config.yaml")
# configdb = loadConfigDB(configfile)
def loadConfigDB(filename):
    global GLOBAL_CONF_DB
    with open(filename) as f:
        db = yaml.safe_load(f)
    GLOBAL_CONF_DB = db
    return db


def getConfigDB():
    return GLOBAL_CONF_DB


def simpleResolver(fullclassname):
    class_name = fullclassname.split(".")[-1]
    module_name = ".".join(fullclassname.split(".")[:-1])
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls


def getObjConfig(name):
    confdb = getConfigDB()
    for objdb in confdb.values():
        if name in objdb:
            objconf = deepcopy(objdb.get("_default", {}))
            objconf.update(objdb[name])
            return objconf
    return None


def getGroupConfig(group_name):
    objdb = getConfigDB()[group_name]
    devicedb = {}
    for name in objdb:
        if name == '_default':
            continue
        objconf = deepcopy(objdb.get("_default", {}))
        objconf.update(objdb[name])
        devicedb[name] = objconf
    return devicedb


def findAndLoadDevice(name, cls=None):
    device_info = getObjConfig(name)
    return instantiateDevice(device_info, cls)


def instantiateDevice(device_info, cls=None):
    if cls is not None:
        device_info.pop("_target_")
        prefix = device_info.pop("prefix", "")
        return cls(prefix, **device_info)
    elif device_info['_target_'] is not None:
        cls = simpleResolver(device_info.pop('_target_'))
        prefix = device_info.pop('prefix', '')
        return cls(prefix, **device_info)


def instantiateGroup(group_name, namedict, cls=None):
    group_config = getGroupConfig(group_name)
    for device_name, device_info in group_config.items():
        namedict[device_name] = instantiateDevice(device_info)
