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


def load_xas(filename):
    with open(join(filename), "rb") as f:
        regions = tomllib.load(f)
        for key, value in regions.items():
            name = value.get("name", key)
            region = value.get("region")
            edge = value.get("edge", "")
            xas_func = _xas_factory(region, edge, name)
            add_to_xas_list(xas_func, key, name=name, edge=edge, region=region)


for region_file in settings.get("regions", []):
    filename = join(settings["startup_dir"], region_file)
    load_xas(filename)
