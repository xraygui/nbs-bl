from .scan_decorators import dynamic_scan_wrapper
from .scan_base import _make_gscan_points
from .flyscan_base import fly_scan
from ..help import add_to_scan_list, add_to_plan_time_dict
from ..utils import merge_func
from ..beamline import GLOBAL_BEAMLINE as bl

import bluesky.plans as bp
from bluesky.plan_stubs import mv

_scan_list = [
    bp.count,
    bp.scan,
    bp.rel_scan,
    bp.list_scan,
    bp.rel_list_scan,
    bp.list_grid_scan,
    bp.rel_list_grid_scan,
    bp.log_scan,
    bp.rel_log_scan,
    bp.grid_scan,
    bp.rel_grid_scan,
    bp.scan_nd,
    bp.spiral,
    bp.spiral_fermat,
    bp.spiral_square,
    bp.rel_spiral,
    bp.rel_spiral_fermat,
    bp.rel_spiral_square,
    fly_scan,
]

for _scan in _scan_list:
    _fixedname = f"nbs_{_scan.__name__}"
    _newscan = dynamic_scan_wrapper(_scan, func_name=_fixedname)
    # _newscan.__name__ = _fixedname
    globals()[_fixedname] = _newscan
    add_to_scan_list(_newscan)

add_to_plan_time_dict(
    nbs_count, "generic_estimate", fixed=0, overhead=0.05, dwell="dwell", points="num"
)
for _scan in [
    bp.scan,
    nbs_scan,
    bp.rel_scan,
    nbs_rel_scan,
    bp.log_scan,
    nbs_log_scan,
    bp.rel_log_scan,
    nbs_rel_log_scan,
]:
    add_to_plan_time_dict(
        _scan, "generic_estimate", fixed=5, overhead=0.5, dwell="dwell", points="num"
    )
for _scan in [bp.list_scan, nbs_list_scan, bp.rel_list_scan, nbs_rel_list_scan]:
    add_to_plan_time_dict(
        _scan, "list_scan_estimate", fixed=5, overhead=0.5, dwell="dwell"
    )
for _scan in [bp.grid_scan, nbs_grid_scan, bp.rel_grid_scan, nbs_rel_grid_scan]:
    add_to_plan_time_dict(
        _scan, "grid_scan_estimate", fixed=5, overhead=0.5, dwell="dwell"
    )

for _scan in [
    bp.list_grid_scan,
    nbs_list_grid_scan,
    bp.rel_list_grid_scan,
    nbs_rel_list_grid_scan,
]:
    add_to_plan_time_dict(
        _scan, "list_grid_scan_estimate", fixed=5, overhead=0.5, dwell="dwell"
    )


@add_to_scan_list
@merge_func(
    nbs_list_scan,
    omit_params=["points"],
    exclude_wrapper_args=False,
    use_func_name=False,
)
def nbs_gscan(motor, start: float, *args, extra_dets=[], shift: float = 0, **kwargs):
    """A variable step scan of a motor and the default detectors.

    Other detectors may be added via extra_dets

    Parameters
    ----------
    motor : Ophyd Device
        The motor object to scan
    start : float
        Starting position for the scan
    step : float, optional
        Step size for first region
    stop : float, optional
        First stopping position
    step2 : float, optional
        Step size for second region. Additional stop/step pairs can be provided
    stop2 : float, optional
        Second stopping position. Additional stop/step pairs can be provided
    *args : float, optional
        Additional stop/step pairs can be provided
    extra_dets : list
        A list of detectors to add for just this scan
    shift : float
        A value to shift all start/stop positions by

    Examples
    --------
    # Scan from 270 to 280 in steps of 1
    nbs_gscan(energy, 270, 1, 280)

    # Scan from 270 to 280 in steps of 1, then from 280 to 290 in steps of 0.25
    nbs_gscan(energy, 270, 1, 280, 0.25, 290)

    # Scan with multiple regions of different step sizes
    nbs_gscan(energy, 270, 1, 280, 0.5, 285, 0.1, 290)
    """
    points = _make_gscan_points(start, *args, shift=shift)
    # Move motor to start position first
    yield from mv(motor, points[0])
    return (yield from nbs_list_scan(motor, points, extra_dets=extra_dets, **kwargs))


@add_to_scan_list
@merge_func(nbs_gscan, use_func_name=False, omit_params=["motor"])
def nbs_energy_scan(*args, **kwargs):
    """A variable step scan of the energy and the default detectors.

    The energy motor is automatically included.Other detectors may be added via extra_dets.
    """
    motor = bl.energy
    return (yield from nbs_gscan(motor, *args, **kwargs))


for _scan in [nbs_gscan, nbs_energy_scan]:
    add_to_plan_time_dict(_scan, "gscan_estimate", fixed=5, overhead=0.5, dwell="dwell")

for _scan in [fly_scan, nbs_fly_scan]:
    add_to_plan_time_dict(_scan, "fly_scan_estimate", fixed=5)
