# from ..settings import settings
from ..plans.scans import nbs_gscan
from ..plans.scan_decorators import _wrap_xas
from ..utils import merge_func
from ..plans.preprocessors import wrap_metadata
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


def add_to_xas_list(f, key, **plan_info):
    """
    A function decorator that will add the plan to the built-in list
    """
    _add_to_import_list(f, "xas")
    GLOBAL_XAS_PLANS[key] = {}
    GLOBAL_XAS_PLANS[key].update(plan_info)
    return f


def _xas_factory(energy_grid, edge, key):
    @_wrap_xas(edge)
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
            eref_sample = edge
        yield from nbs_gscan(
            GLOBAL_BEAMLINE.energy, *energy_grid, eref_sample=eref_sample, **kwargs
        )

    d = f"Perform an in-place xas scan for {edge} with energy pattern {energy_grid} \n"
    inner.__doc__ = d + inner.__doc__

    inner.__qualname__ = key
    inner.__name__ = key
    inner._edge = edge
    inner._short_doc = f"Do XAS for {edge} from {energy_grid[0]} to {energy_grid[-2]}"
    return inner


@add_to_func_list
def load_xas(filename):
    """
    Load XAS plans from a TOML file.

    Parameters
    ----------
    filename : str
        Path to the TOML file containing XAS plan definitions
    """
    with open(filename, "rb") as f:
        regions = tomllib.load(f)
        for key, value in regions.items():
            name = value.get("name", key)
            region = value.get("region")
            edge = value.get("edge", "")
            xas_func = _xas_factory(region, edge, name)
            add_to_xas_list(xas_func, key, name=name, edge=edge, region=region)
