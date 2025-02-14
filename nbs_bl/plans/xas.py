# from ..settings import settings
from ..plans.scans import nbs_gscan
from ..utils import merge_func
from ..plans.preprocessors import wrap_metadata
from .plan_stubs import set_roi, clear_one_roi
from ..help import _add_to_import_list, add_to_func_list
from ..queueserver import GLOBAL_USER_STATUS
from ..status import StatusDict
from ..beamline import GLOBAL_BEAMLINE

# from ..settings import GLOBAL_SETTINGS as settings
from os.path import join

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

GLOBAL_XAS_PLANS = GLOBAL_USER_STATUS.request_status_dict("XAS_PLANS", use_redis=True)
GLOBAL_XAS_PLANS.clear()


def add_to_xas_list(f, key, **plan_info):
    """
    A function decorator that will add the plan to the built-in list
    """
    _add_to_import_list(f, "xas")
    GLOBAL_XAS_PLANS[key] = {}
    GLOBAL_XAS_PLANS[key].update(plan_info)
    return f


def _wrap_xas(element, edge):
    def decorator(func):
        return wrap_metadata({"element": element, "edge": edge, "scantype": "xas"})(
            func
        )

    return decorator


# Needs to have Element, Edge, Ref Element,
def _xas_factory(energy_grid, element, edge, key):
    @_wrap_xas(element, edge)
    @wrap_metadata({"plan_name": key})
    @merge_func(nbs_gscan, omit_params=["motor", "args"])
    def inner(**kwargs):
        """Parameters
        ----------
        repeat : int
            Number of times to repeat the scan
        **kwargs :
            Arguments to be passed to tes_gscan

        """
        eref_sample = kwargs.pop("eref_sample", None)
        if eref_sample is None:
            eref_sample = element
        yield from set_roi("pfy", energy_grid[0], energy_grid[-2])
        yield from nbs_gscan(
            GLOBAL_BEAMLINE.energy, *energy_grid, eref_sample=eref_sample, **kwargs
        )
        yield from clear_one_roi("pfy")

    d = f"Perform an in-place xas scan for {element} with energy pattern {energy_grid} \n"
    inner.__doc__ = d + inner.__doc__

    inner.__qualname__ = key
    inner.__name__ = key
    inner._edge = edge
    inner._short_doc = (
        f"Do XAS for {element} from {energy_grid[0]} to {energy_grid[-2]}"
    )
    return inner


@add_to_func_list
def load_xas(filename):
    """Load XAS plans from a TOML file and inject them into the IPython user namespace.

    Parameters
    ----------
    filename : str
        Path to the TOML file containing XAS plan definitions
    """
    try:
        # Get IPython's user namespace
        ip = get_ipython()
        user_ns = ip.user_ns
    except (NameError, AttributeError):
        # Not running in IPython, just return the generated functions
        user_ns = None

    generated_plans = {}
    with open(filename, "rb") as f:
        regions = tomllib.load(f)
        for key, value in regions.items():
            name = value.get("name", key)
            region = value.get("region")
            element = value.get("element", "")
            edge = value.get("edge", "")
            xas_func = _xas_factory(region, element, edge, key)
            add_to_xas_list(
                xas_func, key, name=name, element=element, edge=edge, region=region
            )

            # Store the function
            generated_plans[key] = xas_func

            # If we're in IPython, inject into user namespace
            if user_ns is not None:
                user_ns[key] = xas_func

    # Return the generated plans dictionary in case it's needed
    return generated_plans
