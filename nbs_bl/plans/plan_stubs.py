from ..beamline import GLOBAL_BEAMLINE
from ..help import add_to_plan_list, add_to_condition_list
import warnings
from bluesky import Msg
from bluesky.plan_stubs import rd, sleep, mv
import time
from typing import Optional
from bluesky.protocols import Readable
import typing
from .conditions import is_signal_below, is_signal_equals, is_signal_above

GLOBAL_EXPOSURE_TIME = 1.0


def call_obj(obj, method, *args, **kwargs):
    ret = yield Msg("call_obj", obj, *args, method=method, **kwargs)
    return ret


def sampleholder_move_sample_old(sampleholder, sample_id=None, **position):
    """
    Set and move a sample. Dangerous! Sample moves really need to go through
    Bluesky's mv plan, or else they won't be properly pause-able
    """
    yield from call_obj(sampleholder, "move_sample", sample_id, **position)


def sampleholder_move_sample(sampleholder, sample_id=None, **position):
    """
    Set and move a sample.
    """
    positions = yield from call_obj(
        sampleholder, "get_sample_position", sample_id, **position
    )
    print(f"Moving {sampleholder.name} to {positions}")
    yield from mv(sampleholder, positions)
    print("Done Moving ", sampleholder.name)


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

    all_dets = GLOBAL_BEAMLINE.detectors.active + extra_dets
    for d in all_dets:
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


@add_to_plan_list
def wait_for_condition(
    condition,
    condition_args: typing.List = None,
    condition_kwargs: typing.Dict = None,
    timeout: Optional[float] = None,
    sleep_time: float = 10,
):
    """
    Wait for a condition function to return True.

    Parameters
    ----------
    condition : str or callable
        A condition function that returns a boolean.
    condition_args : list, optional
        Arguments for the condition function.
    condition_kwargs : dict, optional
        Keyword arguments for the condition function.
    timeout : Optional[float], optional
        Maximum time to wait in seconds. If None, wait indefinitely.
    sleep_time : float, optional
        Time to sleep between checks in seconds. Default is 10.

    Returns
    -------
    bool
        True when condition returns True.

    Raises
    ------
    TimeoutError
        If timeout is reached before condition is met.
    """
    if condition_args is None:
        condition_args = []
    if condition_kwargs is None:
        condition_kwargs = {}

    start_time = time.time()
    while True:
        if timeout is not None and (time.time() - start_time > timeout):
            raise TimeoutError
        result = yield from condition(*condition_args, **condition_kwargs)
        if result:
            return True
        else:
            yield from sleep(sleep_time)


def wait_for_signal_below(
    sig: Readable, val: float, timeout: Optional[float] = None, sleep_time: float = 10
):
    """
    Wait for a readable object to go below a threshold value.

    Parameters
    ----------
    sig : Readable
        Any object that implements the Readable protocol (can be read with rd()).
    val : float
        The target value to wait for.
    timeout : Optional[float], optional
        Maximum time to wait in seconds. If None, wait indefinitely.
    sleep_time : float, optional
        Time to sleep between checks in seconds. Default is 10.

    Returns
    -------
    bool
        True when signal goes below threshold.

    Raises
    ------
    TimeoutError
        If timeout is reached before condition is met.
    """
    return wait_for_condition(
        is_signal_below, [sig, val], timeout=timeout, sleep_time=sleep_time
    )


def wait_for_signal_equals(
    sig: Readable, val: float, timeout: Optional[float] = None, sleep_time: float = 10
):
    """
    Wait for a readable object to equal a target value.

    Parameters
    ----------
    sig : Readable
        Any object that implements the Readable protocol (can be read with rd()).
    val : float
        The target value to wait for.
    timeout : Optional[float], optional
        Maximum time to wait in seconds. If None, wait indefinitely.
    sleep_time : float, optional
        Time to sleep between checks in seconds. Default is 10.

    Returns
    -------
    bool
        True when signal equals target value.

    Raises
    ------
    TimeoutError
        If timeout is reached before condition is met.
    """
    return wait_for_condition(
        is_signal_equals, [sig, val], timeout=timeout, sleep_time=sleep_time
    )


def wait_for_signal_above(
    sig: Readable, val: float, timeout: Optional[float] = None, sleep_time: float = 10
):
    """
    Wait for a readable object to go above a threshold value.

    Parameters
    ----------
    sig : Readable
        Any object that implements the Readable protocol (can be read with rd()).
    val : float
        The target value to wait for.
    timeout : Optional[float], optional
        Maximum time to wait in seconds. If None, wait indefinitely.
    sleep_time : float, optional
        Time to sleep between checks in seconds. Default is 10.

    Returns
    -------
    bool
        True when signal goes above threshold.

    Raises
    ------
    TimeoutError
        If timeout is reached before condition is met.
    """
    return wait_for_condition(
        is_signal_above, [sig, val], timeout=timeout, sleep_time=sleep_time
    )
