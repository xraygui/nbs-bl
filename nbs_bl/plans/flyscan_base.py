from bluesky.protocols import Readable, Flyable
from bluesky.utils import get_hinted_fields
import bluesky.preprocessors as bpp
from bluesky.plan_stubs import trigger_and_read
from warnings import warn
from .plan_stubs import call_obj

from bluesky.utils import Msg, ensure_generator, short_uid as _short_uid, single_gen
from bluesky.preprocessors import plan_mutator
from typing import Optional


def flystream_during_wrapper(plan, flyers):
    """
    Kickoff and collect "flyer" (asynchronously collect) objects during runs.
    This is a preprocessor that insert messages immediately after a run is
    opened and before it is closed.
    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    flyers : collection
        objects that support the flyer interface
    Yields
    ------
    msg : Msg
        messages from plan with 'kickoff', 'wait' and 'collect' messages
        inserted
    See Also
    --------
    :func:`bluesky.plans.fly`
    """
    grp1 = _short_uid("flyers-kickoff")
    grp2 = _short_uid("flyers-complete")
    kickoff_msgs = [Msg("kickoff", flyer, group=grp1) for flyer in flyers]
    complete_msgs = [Msg("complete", flyer, group=grp2) for flyer in flyers]
    collect_msgs = [Msg("collect", flyer) for flyer in flyers]
    if flyers:
        # If there are any flyers, insert a 'wait' Msg after kickoff, complete
        kickoff_msgs += [Msg("wait", None, group=grp1)]
        complete_msgs += [Msg("wait", None, group=grp2)]

    def insert_after_open(msg):
        if msg.command == "open_run":

            def new_gen():
                yield from ensure_generator(kickoff_msgs)

            return single_gen(msg), new_gen()
        else:
            return None, None

    def insert_before_close(msg):
        if msg.command == "close_run":

            def new_gen():
                yield from ensure_generator(complete_msgs)
                yield from ensure_generator(collect_msgs)
                yield msg

            return new_gen(), None
        else:
            return None, None

    # Apply nested mutations.
    plan1 = plan_mutator(plan, insert_after_open)
    plan2 = plan_mutator(plan1, insert_before_close)
    return (yield from plan2)


def fly_scan(
    detectors,
    motor,
    start,
    stop,
    *args,
    md: Optional[dict] = None,
    period: Optional[float] = None,
    stream: bool = True,
    **kwargs,
):
    """
    Perform a fly scan over the specified motor range.

    Parameters
    ----------
    detectors : list
        List of detectors to use for the scan
    motor : ophyd.Device
        Motor to be scanned
    start : float
        Starting position of the scan
    stop : float
        Ending position of the scan
    *args : float, optional
        Additional scan parameters in groups of 3: start, stop, speed.
        For example:
        start1, stop1, speed1[, start2, stop2, speed2, ...]
        This allows for multiple trajectory segments in a single scan
    md : dict, optional
        Metadata dictionary to be included with the scan
    period : float, optional
        Time period between data points. If None, uses detector's default period
    stream : bool, optional
        If True, continuously stream data from detectors during the scan.
        If False, collect data only at specified points. Default is True

    Returns
    -------
    uid : str
        Unique identifier for the scan

    Notes
    -----
    When stream=True, detectors will continuously collect data during motor movement,
    providing higher time resolution but potentially more data volume.
    When stream=False, data is collected only at specific points, reducing data volume
    but potentially missing intermediate states.

    Examples
    --------
    # Simple scan with one trajectory, default motor speed
    >>> fly_scan([det], motor, 0, 10)

    # Multi-segment scan with different speeds
    >>> fly_scan([det], motor, 0, 10, 2, 10, 20, 5)
    # This will scan from 0->10 at speed 2, then 10->20 at speed 5
    """

    md = md or {}

    flyers = [d for d in detectors + [motor] if isinstance(d, Flyable)]
    readers = [d for d in detectors + [motor] if isinstance(d, Readable)]

    _md = {
        "detectors": [det.name for det in readers],
        "motors": [motor.name],
        "plan_args": {
            "detectors": list(map(repr, detectors)),
            "args": [repr(motor), start, stop] + [a for a in args],
        },
        "plan_name": "fly_scan",
        "hints": {},
    }
    _md.update(md or {})

    x_fields = get_hinted_fields(motor)
    default_dimensions = [(x_fields, "primary")]

    default_hints = {}
    if len(x_fields) > 0:
        default_hints.update(dimensions=default_dimensions)

    _md["hints"] = default_hints
    _md["hints"].update(md.get("hints", {}) or {})

    if period is not None:
        for d in readers:
            try:
                if hasattr(d, "set_exposure"):
                    yield from call_obj(d, "set_exposure", period)
            except RuntimeError as ex:
                warn(repr(ex), RuntimeWarning)

    yield from call_obj(motor, "preflight", start, stop, *args, **kwargs)

    @bpp.stage_decorator(readers)
    @bpp.run_decorator(md=_md)
    def inner_flyscan():
        status = yield from call_obj(motor, "fly")

        while not status.done:
            yield from trigger_and_read(readers)

        yield from call_obj(motor, "land")

    if stream:
        return (yield from flystream_during_wrapper(inner_flyscan(), flyers))
    else:
        return (yield from inner_flyscan())
