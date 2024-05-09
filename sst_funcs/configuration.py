from os.path import join

# from pkg_resources import iter_entry_points
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from .hw import _load_hardware, _alias_device
from .globalVars import (
    GLOBAL_HARDWARE,
    GLOBAL_SUPPLEMENTAL_DATA,
    GLOBAL_ALIGNMENT_DETECTOR,
    GLOBAL_ENERGY,
    GLOBAL_MANIPULATOR,
)
from .settings import settings
from .detectors import add_detector, add_detector_set
from .motors import add_motor
from .shutters import add_shutter
from .gatevalves import add_valve
from .mirrors import add_mirror
from .queueserver import request_update, get_status

def get_startup_dir():
    """
    Get the IPython startup directory.

    Returns
    -------
    str
        The path to the IPython startup directory.
    """
    ip = get_ipython()
    startup_dir = ip.profile_dir.startup_dir
    return startup_dir


def load_and_configure_everything(startup_dir=None):
    """
    Load and configure all necessary hardware and settings for the beamline.

    Parameters
    ----------
    startup_dir : str, optional
        The directory from which to load configuration files. If not specified, uses the IPython startup directory.
    """
    if startup_dir is None:
        startup_dir = get_startup_dir()
    settings.startup_dir = startup_dir
    settings_file = join(startup_dir, "settings.toml")
    load_settings(settings_file)
    object_file = join(startup_dir, settings.device_filename)
    ip = get_ipython()
    ip.user_ns['get_status'] = get_status
    ip.user_ns['request_update'] = request_update
    _load_hardware(object_file, ip.user_ns)
    beamline_file = join(startup_dir, settings.beamline_filename)
    configure_beamline(beamline_file, object_file)
    configure_modules()


def load_settings(settings_file):
    """
    Load settings from a TOML file.

    Parameters
    ----------
    settings_file : str
        The path to the settings file.

    Returns
    -------
    dict
        The settings loaded from the file.
    """
    # Things that are currently in ucal configuration/settings
    with open(settings_file, "rb") as f:
        settings_dict = tomllib.load(f)
    for key in settings_dict:
        setattr(settings, key, settings_dict[key])


def auto_add_devices_to_groups(beamline_config, devices):
    for obj_key, obj_dict in devices.items():
        if "_group" in obj_dict:
            gkey = obj_dict["_group"]
            if gkey not in beamline_config:
                beamline_config[gkey] = {}
            group = beamline_config[gkey]
            if "devices" not in group:
                group["devices"] = []
            if obj_key not in group["devices"] and obj_key not in group.get(
                "exclude", []
            ):
                group["devices"].append(obj_key)
    return beamline_config


def configure_beamline(beamline_file, object_file, namespace=None):
    """
    Configure the beamline using settings from TOML files.

    Parameters
    ----------
    beamline_file : str
        The path to the beamline configuration file.
    object_file : str
        The path to the object configuration file.
    """
    with open(object_file, "rb") as f:
        devices = tomllib.load(f)
    with open(beamline_file, "rb") as f:
        beamline_config = tomllib.load(f)
    auto_add_devices_to_groups(beamline_config, devices)

    configure_detectors(beamline_config.get("detectors", {}))
    configure_motors(beamline_config.get("motors", {}))
    configure_shutters(beamline_config.get("shutters", {}))
    configure_mirrors(beamline_config.get("mirrors", {}))
    configure_gatevalves(beamline_config.get("gatevalves", {}))
    configure_energy(beamline_config.get("energy", {}))
    configure_manipulators(beamline_config.get("manipulators", {}))
    configure_alias(beamline_config.get("alias", {}), namespace)


def _configure_base(config_dict, add_device=None, add_to_baseline=False):
    devices = config_dict.get("devices", [])
    configuration = config_dict.get("configuration", {})
    for device in devices:
        dev = GLOBAL_HARDWARE[device]
        if add_device is not None:
            add_device(dev, name=device, **configuration.get(device, {}))
        if add_to_baseline:
            if dev not in GLOBAL_SUPPLEMENTAL_DATA.baseline:
                GLOBAL_SUPPLEMENTAL_DATA.baseline.append(dev)


def configure_alias(alias_dict, namespace=None):
    for alias_key, device_key in alias_dict.items():
        _alias_device(device_key, alias_key, namespace)


def configure_detectors(config_dict):
    _configure_base(config_dict, add_detector)
    groups = config_dict.get("groups", {})
    for key, val in groups.items():
        add_detector_set(key, **val)
    alignment = config_dict.get("alignment", {})
    for key, val in alignment.items():
        dev = GLOBAL_HARDWARE[val]
        GLOBAL_ALIGNMENT_DETECTOR[key] = dev
    if "indirect" in GLOBAL_ALIGNMENT_DETECTOR:
        GLOBAL_ALIGNMENT_DETECTOR["default"] = GLOBAL_ALIGNMENT_DETECTOR["indirect"]
    elif "direct" in GLOBAL_ALIGNMENT_DETECTOR:
        GLOBAL_ALIGNMENT_DETECTOR["default"] = GLOBAL_ALIGNMENT_DETECTOR["direct"]


def configure_motors(config_dict):
    _configure_base(config_dict, add_motor, True)


def configure_gatevalves(config_dict):
    _configure_base(config_dict, add_valve, False)


def configure_shutters(config_dict):
    _configure_base(config_dict, add_shutter, True)


def configure_mirrors(config_dict):
    _configure_base(config_dict, add_mirror, True)

def get_device(device_name):
    device_parts = device_name.split('.')
    device = GLOBAL_HARDWARE[device_parts[0]]
    for subdev in device_parts[1:]:
        device = getattr(device, subdev)
    return device
    
def configure_energy(config_dict):
    energy_key = config_dict.get("energy")
    energy = get_device(energy_key)
    GLOBAL_ENERGY["energy"] = energy
    if energy not in GLOBAL_SUPPLEMENTAL_DATA.baseline:
        GLOBAL_SUPPLEMENTAL_DATA.baseline.append(energy)
    slit_key = config_dict.get("slit")
    GLOBAL_ENERGY["slit"] = get_device(slit_key)


def configure_manipulators(config_dict):
    for name, device_key in config_dict.items():
        GLOBAL_MANIPULATOR[name] = device_key


def configure_modules():
    """
    Load and configure modules based on a list of names.

    Parameters
    ----------
    entry_points : list of str
        The list of entry point names to load and configure.
    """
    from importlib.util import find_spec
    """
    with open(beamline_file, "rb") as f:
        beamline_config = tomllib.load(f)
    modules = beamline_config.get("modules", [])
    """
    modules = settings.modules
    ip = get_ipython()

    for module_name in modules:
        print(f"Running import_module command")
        # module = import_module(module_name)
        module_path = find_spec(module_name).origin
        print(f"Trying to import {module_name} from {module_path}")
        ip.run_line_magic("run", module_path)
