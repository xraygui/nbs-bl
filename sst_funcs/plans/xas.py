from sst_funcs.settings import settings
from sst_funcs.plans.scans import nbs_gscan
from sst_funcs.plans.scan_decorators import _wrap_xas
from sst_funcs.utils import merge_func
from sst_funcs.plans.preprocessors import wrap_metadata
from sst_funcs.help import add_to_scan_list, add_to_xas_list
from sst_funcs.globalVars import GLOBAL_ENERGY, GLOBAL_XAS_PLANS
from os.path import join
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


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
        yield from nbs_gscan(GLOBAL_ENERGY['energy'], *energy_grid, **kwargs)

    d = f"Perform an in-place xas scan for {edge} with energy pattern {energy_grid} \n"
    inner.__doc__ = d + inner.__doc__

    inner.__qualname__ = name
    inner.__name__ = name
    inner._edge = edge
    inner._short_doc = f"Do XAS for {edge} from {energy_grid[0]} to {energy_grid[-2]}"
    return inner

for region_file in settings.regions:
    with open(join(settings.startup_dir, region_file), 'rb') as f:
        regions = tomllib.load(f)
        for e, region in regions.items():
            name = f"{settings.beamline_prefix}_{e.lower()}_xas"
            xas_func = _xas_factory(region, e, name)
            add_to_xas_list(xas_func)
            GLOBAL_XAS_PLANS[e] = name
