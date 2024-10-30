from os.path import join
from importlib.util import find_spec
from .beamline import GLOBAL_BEAMLINE
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
        The directory from which to load configuration files.
        If not specified, uses the IPython startup directory.
    """
    if startup_dir is None:
        startup_dir = get_startup_dir()

    ip = get_ipython()
    ip.user_ns["get_status"] = get_status
    ip.user_ns["request_update"] = request_update

    GLOBAL_BEAMLINE.load_beamline(startup_dir, ip.user_ns)
    configure_modules()


def configure_modules():
    """
    Load and configure modules based on settings.
    """
    modules = GLOBAL_BEAMLINE.settings.get("modules", [])
    ip = get_ipython()

    for module_name in modules:
        module_path = find_spec(module_name).origin
        print(f"Trying to import {module_name} from {module_path}")
        ip.run_line_magic("run", module_path)
