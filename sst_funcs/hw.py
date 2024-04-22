from .load import loadDeviceConfig as _loadDeviceConfig
from .globalVars import GLOBAL_HARDWARE

"""
ip = get_ipython()
startup_dir = ip.profile_dir.startup_dir
config_file = join(startup_dir, "devices.toml")
if exists(config_file):
    print(f"Attempting to load objects in {config_file}")
    device_dict = loadDeviceConfig(config_file, ip.user_ns)
    for key, dev in device_dict.items():
        globals()[key] = dev
else:
    print(f"{config_file} does not exist!")
"""


def _load_hardware(config_file, namespace=None):
    print(f"Attempting to load objects in {config_file}")
    device_dict = _loadDeviceConfig(config_file, namespace)
    for key, dev in device_dict.items():
        globals()[key] = dev
        GLOBAL_HARDWARE[key] = dev


def _alias_device(device_key, alias_key, namespace=None):
    device_names = device_key.split(".")
    device = GLOBAL_HARDWARE[device_names[0]]
    if len(device_names) > 1:
        for key in device_names[1:]:
            device = getattr(device, key)
    GLOBAL_HARDWARE[alias_key] = device
    globals()[alias_key] = device
    if namespace is not None:
        namespace[alias_key] = device
