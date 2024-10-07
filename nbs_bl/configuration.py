from os.path import join, exists

# from pkg_resources import iter_entry_points
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from .hw import _load_hardware
from .beamline import GLOBAL_BEAMLINE
from .settings import load_settings, GLOBAL_SETTINGS
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
    GLOBAL_SETTINGS["startup_dir"] = startup_dir
    settings_file = join(startup_dir, "beamline.toml")
    load_settings(settings_file)
    object_file = join(startup_dir, GLOBAL_SETTINGS["device_filename"])
    beamline_file = join(startup_dir, GLOBAL_SETTINGS["beamline_filename"])
    with open(beamline_file, "rb") as f:
        beamline_config = tomllib.load(f)
    ip = get_ipython()
    ip.user_ns["get_status"] = get_status
    ip.user_ns["request_update"] = request_update
    devices, groups, roles = _load_hardware(object_file, ip.user_ns)
    GLOBAL_BEAMLINE.load_devices(devices, groups, roles, beamline_config)
    devices2, groups2, roles2 = _load_hardware(
        object_file, ip.user_ns, load_pass=2, beamline=GLOBAL_BEAMLINE
    )
    GLOBAL_BEAMLINE.load_devices(devices2, groups2, roles2, beamline_config)
    # configure_beamline(beamline_file, devices, groups, roles)
    configure_modules()


def configure_modules():
    """
    Load and configure modules based on a list of names.

    Parameters
    ----------
    entry_points : list of str
        The list of entry point names to load and configure.
    """
    from importlib.util import find_spec

    modules = GLOBAL_SETTINGS["modules"]
    ip = get_ipython()

    for module_name in modules:
        module_path = find_spec(module_name).origin
        print(f"Trying to import {module_name} from {module_path}")
        ip.run_line_magic("run", module_path)
