from .scan_decorators import sst_builtin_scan_wrapper
from sst_funcs.help import add_to_scan_list
import bluesky.plans as bp

_scan_list = [bp.count, bp.scan, bp.rel_scan, bp.list_scan, bp.rel_list_scan, bp.list_grid_scan,
              bp.rel_list_grid_scan, bp.log_scan, bp.rel_log_scan, bp.grid_scan, bp.rel_grid_scan,
              bp.scan_nd, bp.spiral, bp.spiral_fermat, bp.spiral_square, bp.rel_spiral,
              bp.rel_spiral_fermat, bp.rel_spiral_square]

for _scan in _scan_list:
    add_to_scan_list(sst_builtin_scan_wrapper(_scan))
