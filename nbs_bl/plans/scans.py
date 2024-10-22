from .scan_decorators import nbs_builtin_scan_wrapper
from .scan_base import _make_gscan_points
from .flyscan_base import fly_scan
from ..help import add_to_scan_list
from ..utils import merge_func

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
    _newscan = nbs_builtin_scan_wrapper(_scan)
    _fixedname = f"nbs_{_scan.__name__}"
    _newscan.__name__ = _fixedname
    globals()[_fixedname] = _newscan
    add_to_scan_list(_newscan)


@add_to_scan_list
@merge_func(
    nbs_list_scan,
    omit_params=["points"],
    exclude_wrapper_args=False,
    use_func_name=False,
)
def nbs_gscan(motor, *args, extra_dets=[], shift: float = 0, **kwargs):
    """A variable step scan of a motor, the TES detector, and the basic beamline detectors.

    Other detectors may be added via extra_dets

    motor : The motor object to scan
    args : start, stop1, step1, stop2, step2, ...
    extra_dets : A list of detectors to add for just this scan
    """
    points = _make_gscan_points(*args, shift=shift)
    # Move motor to start position first
    yield from mv(motor, points[0])
    return (yield from nbs_list_scan(motor, points, extra_dets=extra_dets, **kwargs))
