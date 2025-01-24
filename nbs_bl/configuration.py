from os.path import join
from importlib.util import find_spec
from .beamline import GLOBAL_BEAMLINE
from .queueserver import request_update, get_status
import pkg_resources


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


def load_plans(startup_dir):
    """
    Load all plans using registered entry points.

    Parameters
    ----------
    startup_dir : str
        Directory containing plan configuration files
    """
    plan_settings = GLOBAL_BEAMLINE.settings.get("plans", {})
    print(f"Loading plans from {startup_dir}")
    # Iterate through all registered plan loaders
    for entry_point in pkg_resources.iter_entry_points(group="nbs_bl.plan_loaders"):
        plan_type = entry_point.name
        print(f"Loading {plan_type} plans")
        plan_files = plan_settings.get(plan_type, [])

        if not plan_files:
            print(f"No {plan_type} plans found")
            continue
        print(f"Loading {plan_type} plans from {plan_files}")
        # Load the plan loader function
        plan_loader = entry_point.load()

        # Load each plan file for this plan type
        for plan_file in plan_files:
            full_path = join(startup_dir, plan_file)
            try:
                plan_loader(full_path)
                print(f"Loaded {plan_type} plans from {plan_file}")
            except Exception as e:
                print(f"Error loading {plan_type} plans from {plan_file}: {str(e)}")


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
    load_plans(startup_dir)  # Load plans after beamline configuration
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
