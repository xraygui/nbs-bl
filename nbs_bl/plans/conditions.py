from ..help import add_to_condition_list
from bluesky.plan_stubs import rd
from bluesky.protocols import Readable


@add_to_condition_list
def is_signal_below(sig: Readable, val: float):
    """
    Check if a readable object is below a threshold value.

    Parameters
    ----------
    sig : Readable
        Any object that implements the Readable protocol (can be read with rd()).
    val : float
        The threshold value to wait for.

    Returns
    -------
    bool
        True when signal is below threshold.

    Raises
    ------
    """
    reading = yield from rd(sig)
    return reading < val


@add_to_condition_list
def is_signal_equals(sig: Readable, val: float):
    """
    Check if a readable object equals a target value.

    Parameters
    ----------
    sig : Readable
        Any object that implements the Readable protocol (can be read with rd()).
    val : float
        The target value to wait for.

    Returns
    -------
    bool
        True when signal equals target.

    Raises
    ------
    """
    reading = yield from rd(sig)
    return reading == val


@add_to_condition_list
def is_signal_above(sig: Readable, val: float):
    """
    Check if a readable object is above a threshold value.

    Parameters
    ----------
    sig : Readable
        Any object that implements the Readable protocol (can be read with rd()).
    val : float
        The threshold value to wait for.

    Returns
    -------
    bool
        True when signal is above threshold.

    Raises
    ------
    TimeoutError
        If timeout is reached before condition is met.
    """
    reading = yield from rd(sig)
    return reading > val
