from sst_funcs.globalVars import GLOBAL_ACTIVE_DETECTORS
from sst_funcs.help import add_to_plan_list
import warnings
from bluesky import Msg

GLOBAL_EXPOSURE_TIME = 1.0


def call_obj(obj, method, *args, **kwargs):
    ret = yield Msg("call_obj", obj, *args, method=method, **kwargs)
    return ret


@add_to_plan_list
def set_exposure(time=None, extra_dets=[]):
    """Sets the exposure time for all active detectors"""
    global GLOBAL_EXPOSURE_TIME
    if time is not None:
        GLOBAL_EXPOSURE_TIME = time
    for d in GLOBAL_ACTIVE_DETECTORS:
        try:
            if hasattr(d, "set_exposure"):
                yield from call_obj(d, "set_exposure", GLOBAL_EXPOSURE_TIME)
        except RuntimeError as ex:
            warnings.warn(repr(ex), RuntimeWarning)
