from bluesky.protocols import Readable, Flyable
from bluesky.utils import get_hinted_fields
import bluesky.preprocessors as bpp
from bluesky.plan_stubs import trigger_and_read
from warnings import warn
from .plan_stubs import call_obj

from bluesky.utils import Msg, ensure_generator, short_uid as _short_uid, single_gen
from bluesky.preprocessors import plan_mutator
from typing import Optional


def flystream_during_wrapper(plan, flyers, stream=False):
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
    collect_msgs = [Msg("collect", flyer, stream=stream) for flyer in flyers]
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
    period: Optional[float] = None
):
    """
    Flyscan one motor in a trajectory

    Parameters
    ----------
    detectors : list
        list of 'readable' or 'flyable' devices
    motor :
        a flyable motor
    *args :
        For a single trajectory, ``start, stop[, speed]``
        where speed is optional
        In general:
        .. code-block:: python

            start1, stop1, speed1[, start2, stop2, speed2, ...]

    md : dict, optional
        metadata
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

    yield from call_obj(motor, "preflight", start, stop, *args)

    @bpp.stage_decorator(readers)
    @bpp.run_decorator(md=_md)
    def inner_flyscan():
        status = yield from call_obj(motor, "fly")

        while not status.done:
            yield from trigger_and_read(readers)

        yield from call_obj(motor, "land")

    return (yield from flystream_during_wrapper(inner_flyscan(), flyers))
