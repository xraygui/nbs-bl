from ..beamline import GLOBAL_BEAMLINE
from ..help import add_to_plan_list
import warnings
from bluesky import Msg
from bluesky.plan_stubs import rd, sleep
import time
from typing import Optional

GLOBAL_EXPOSURE_TIME = 1.0


def call_obj(obj, method, *args, **kwargs):
    ret = yield Msg("call_obj", obj, *args, method=method, **kwargs)
    return ret


def sampleholder_move_sample(sampleholder, sample_id=None, **position):
    """
    Set and move a sample.
    """
    yield from call_obj(sampleholder, "move_sample", sample_id, **position)


def sampleholder_set_sample(sampleholder, sample_id):
    """
    Set a sample without moving it
    """
    yield from call_obj(sampleholder, "set_sample", sample_id)


@add_to_plan_list
def set_exposure(time: Optional[float] = None, extra_dets=[]):
    """Sets the exposure time for all active detectors"""
    global GLOBAL_EXPOSURE_TIME
    if time is not None:
        GLOBAL_EXPOSURE_TIME = time
    for d in GLOBAL_BEAMLINE.detectors.active:
        try:
            if hasattr(d, "set_exposure"):
                yield from call_obj(d, "set_exposure", GLOBAL_EXPOSURE_TIME)
        except RuntimeError as ex:
            warnings.warn(repr(ex), RuntimeWarning)


@add_to_plan_list
def set_roi(label, llim, ulim):
    for d in GLOBAL_BEAMLINE.detectors.active:
        try:
            if hasattr(d, "set_roi"):
                yield from call_obj(d, "set_roi", label, llim, ulim)
        except RuntimeError as ex:
            warnings.warn(repr(ex), RuntimeWarning)


@add_to_plan_list
def clear_all_rois():
    for d in GLOBAL_BEAMLINE.detectors.active:
        try:
            if hasattr(d, "clear_all_rois"):
                yield from call_obj(d, "clear_all_rois")
        except RuntimeError as ex:
            warnings.warn(repr(ex), RuntimeWarning)


@add_to_plan_list
def clear_one_roi(label):
    for d in GLOBAL_BEAMLINE.detectors.active:
        try:
            if hasattr(d, "clear_roi"):
                yield from call_obj(d, "clear_roi", label)
        except RuntimeError as ex:
            warnings.warn(repr(ex), RuntimeWarning)


def wait_for_signal_below(
    sig, val, timeout: Optional[float] = None, sleep_time: float = 10
):
    start_time = time.time()
    while True:
        if timeout is not None and (time.time() - start_time > timeout):
            raise TimeoutError
        reading = yield from rd(sig)
        if reading < val:
            return True
        else:
            yield from sleep(sleep_time)


def wait_for_signal_equals(
    sig, val, timeout: Optional[float] = None, sleep_time: float = 10
):
    start_time = time.time()
    while True:
        if timeout is not None and (time.time() - start_time > timeout):
            raise TimeoutError
        reading = yield from rd(sig)
        if reading == val:
            return True
        else:
            yield from sleep(sleep_time)


def wait_for_signal_above(
    sig, val, timeout: Optional[float] = None, sleep_time: float = 10
):
    start_time = time.time()
    while True:
        if timeout is not None and (time.time() - start_time > timeout):
            raise TimeoutError
        reading = yield from rd(sig)
        if reading > val:
            return True
        else:
            yield from sleep(sleep_time)
