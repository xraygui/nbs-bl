# from ..settings import settings
from ..plans.scans import nbs_gscan
from ..plans.scan_decorators import _wrap_xas
from ..utils import merge_func
from ..plans.preprocessors import wrap_metadata
from ..help import _add_to_import_list
from ..queueserver import add_status
from ..status import StatusDict
from ..beamline import GLOBAL_BEAMLINE
from ..settings import GLOBAL_SETTINGS as settings
from os.path import join

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

GLOBAL_XAS_PLANS = StatusDict()

add_status("XAS_PLANS", GLOBAL_XAS_PLANS)


def add_to_xas_list(f, name, edge):
    """
    A function decorator that will add the plan to the built-in list
    """
    _add_to_import_list(f, "xas")
    GLOBAL_XAS_PLANS[edge] = name
    return f


def _xas_factory(energy_grid, edge, name):
    @_wrap_xas(edge)
    @wrap_metadata({"plan_name": name})
    @merge_func(nbs_gscan, omit_params=["motor", "args"])
    def inner(**kwargs):
        """Parameters
        ----------
        repeat : int
            Number of times to repeat the scan
        **kwargs :
            Arguments to be passed to tes_gscan

        """
        yield from nbs_gscan(GLOBAL_BEAMLINE.energy, *energy_grid, **kwargs)

    d = f"Perform an in-place xas scan for {edge} with energy pattern {energy_grid} \n"
    inner.__doc__ = d + inner.__doc__

    inner.__qualname__ = name
    inner.__name__ = name
    inner._edge = edge
    inner._short_doc = f"Do XAS for {edge} from {energy_grid[0]} to {energy_grid[-2]}"
    return inner


def load_xas(filename):
    with open(join(filename), "rb") as f:
        regions = tomllib.load(f)
        for e, region in regions.items():
            name = f"nbs_{e.lower()}_xas"
            xas_func = _xas_factory(region, e, name)
            add_to_xas_list(xas_func, name, e)


for region_file in settings.get("regions", []):
    filename = join(settings["startup_dir"], region_file)
    load_xas(filename)
