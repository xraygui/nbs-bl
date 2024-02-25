from os.path import join, exists
from .configuration import loadDeviceConfig

ip = get_ipython()
startup_dir = ip.profile_dir.startup_dir
config_file = join(startup_dir, "device_config.yaml")
if exists(config_file):
    print(f"Attempting to load objects in {config_file}")
    device_dict = loadDeviceConfig(config_file, ip.user_ns)
    for key, dev in device_dict.items():
        globals()[key] = dev
else:
    print(f"{config_file} does not exist!")
