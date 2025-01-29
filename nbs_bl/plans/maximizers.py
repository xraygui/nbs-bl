from bluesky_live.bluesky_run import BlueskyRun, DocumentCache
import bluesky.preprocessors as bpp
from .preprocessors import run_return_decorator
from bluesky.plan_stubs import mv, mvr, trigger_and_read
from bluesky.plans import count
import numpy as np

from nbs_bl.plans.flyscan_base import fly_scan
from bluesky.preprocessors import finalize_wrapper
import bluesky.plan_stubs as bps
from nbs_bl.hw import Shutter_control, Shutter_enable
from .scan_decorators import wrap_plan_name


@wrap_plan_name
def fly_max(
    detectors,
    motor,
    *args,
    max_channel=None,
    invert=False,
    end_on_max=True,
    md=None,
    **kwargs,
):
    r"""
    plan: tune a motor to the maximum of signal(motor)

    Initially, traverse the range from start to stop with
    the number of points specified.  Repeat with progressively
    smaller step size until the minimum step size is reached.
    Rescans will be centered on the signal maximum
    with original scan range reduced by ``step_factor``.

    Set ``snake=True`` if your positions are reproducible
    moving from either direction.  This will not
    decrease the number of traversals required to reach convergence.
    Snake motion reduces the total time spent on motion
    to reset the positioner.  For some positioners, such as
    those with hysteresis, snake scanning may not be appropriate.
    For such positioners, always approach the positions from the
    same direction.

    Note:  if there are multiple maxima, this function may find a smaller one
    unless the initial number of steps is large enough.

    Parameters
    ----------
    detectors : Signal
        list of 'readable' objects
    motor : object
        any 'settable' object (motor, temp controller, etc.)
    start : float
        start of range
    stop : float
        end of range, note: start < stop
    velocities : list of floats
        list of speeds to set motor to during run.
    max_channel : list of strings
        detector fields whose output is to maximize. If not given, the first detector is used.
        (the first will be maximized, but secondardy maxes will be recorded during the scans for the first -
        if the maxima are not in the same range this will not be useful)
    md : dict, optional
        metadata
    **kwargs : dict, optional
        additional arguments to pass to fly_scan

    """
    if max_channel is None:
        max_channel = [detectors[0].name]
    _md = {
        "maximizer_args": {
            "plan": "fly_scan",
            "max_channel": max_channel,
            "end_on_max": end_on_max,
            "invert": invert,
        },
        "hints": {},
    }
    _md.update(md or {})

    dc = DocumentCache()

    @bpp.subs_decorator(dc)
    def inner_maximizer():
        yield from fly_scan(detectors, motor, *args, md=_md, **kwargs)
        run = BlueskyRun(dc)
        table = run.primary.read()
        motor_name = motor.name
        max_info = {}
        move_list = []

        for detname in max_channel:
            if invert:
                idx = int(table[detname].argmin())
                print(f"Minimum found at step {idx} for detector {detname}")
            else:
                idx = int(table[detname].argmax())
                print(f"Maximum found at step {idx} for detector {detname}")
            max_info[detname] = {"idx": idx, "value": table[detname][idx]}
            max_val = float(table[motor_name][idx])
            max_info[detname][motor_name] = max_val
            move_list.extend([motor, max_val])
        if end_on_max:
            print("going to found motor positions")
            yield from mv(*move_list)
        return max_info

    return (yield from inner_maximizer())


@wrap_plan_name
def find_max(
    plan,
    dets,
    *args,
    max_channel=None,
    invert=False,
    end_on_max=True,
    md=None,
    **kwargs,
):
    """
    invert turns find_max into find_min
    """
    dc = DocumentCache()

    md = md or {}

    _md = {
        "maximizer_args": {
            "plan": plan.__name__,
            "max_channel": max_channel,
            "invert": invert,
            "end_on_max": end_on_max,
        },
    }
    _md.update(md)

    @bpp.subs_decorator(dc)
    def inner_maximizer():
        yield from plan(dets, *args, md=_md, **kwargs)
        run = BlueskyRun(dc)
        table = run.primary.read()
        motor_names = run.metadata["start"]["motors"]
        motors = [m for m in args if getattr(m, "name", None) in motor_names]
        if max_channel is None:
            detname = dets[0].name
        else:
            detname = max_channel
        if invert:
            max_idx = int(table[detname].argmin())
            print(f"Minimum found at step {max_idx} for detector {detname}")
        else:
            max_idx = int(table[detname].argmax())
            print(f"Maximum found at step {max_idx} for detector {detname}")
        ret = []
        for m in motors:
            max_val = float(table[m.name][max_idx])
            print(f"setting {m.name} to {max_val}")
            ret.append([m, max_val])
        if end_on_max:
            print("going to found motor positions")
            flat_list = [item for sublist in ret for item in sublist]
            yield from mv(*flat_list)
        return ret

    return (yield from inner_maximizer())


def find_min(plan, dets, *args):
    return (yield from find_max(plan, dets, *args, invert=True))


def find_max_deriv(plan, dets, *args, max_channel=None):
    dc = DocumentCache()

    @bpp.subs_decorator(dc)
    def inner_maximizer():
        yield from plan(dets, *args)
        run = BlueskyRun(dc)
        table = run.primary.read()
        motor_names = run.metadata["start"]["motors"]
        motors = [m for m in args if getattr(m, "name", None) in motor_names]
        if len(motors) > 1:
            print(
                "Derivative with multiple motors unsupported, \
            taking first motor"
            )

        if max_channel is None:
            detname = dets[0].name
        else:
            detname = max_channel
        motname = motors[0].name
        max_idx = np.argmax(np.abs(np.gradient(table[detname], table[motname])))
        print(f"Maximum derivative found at step {max_idx} for detector {detname}")
        ret = []
        for m in motors:
            max_val = float(table[m.name][max_idx])
            print(f"setting {m.name} to {max_val}")
            ret.append([m, max_val])
            yield from mv(m, max_val)
        return ret

    return (yield from inner_maximizer())


def find_halfmax(plan, dets, *args, max_channel=None, **kwargs):
    """
    For a plan and detector that goes from low to high, find
    the motor value where the detector is half of the maximum
    value
    """
    dc = DocumentCache()

    @bpp.subs_decorator(dc)
    def inner_maximizer():
        yield from plan(dets, *args, **kwargs)
        run = BlueskyRun(dc)
        table = run.primary.read()
        motor_names = run.metadata["start"]["motors"]
        motors = [m for m in args if getattr(m, "name", None) in motor_names]
        if max_channel is None:
            detname = dets[0].name
        else:
            detname = max_channel
        max_val = float(table[detname].max())
        halftable = table[detname] - max_val / 2.0
        half_idx = 0
        for n, v in enumerate(halftable.data):
            if v > 0:
                half_idx = n
                break
        ret = []
        for m in motors:
            mot_val = float(table[m.name][half_idx])
            print(f"setting {m.name} to {mot_val}")
            ret.append([m, mot_val])
            yield from mv(m, mot_val)
        return ret

    return (yield from inner_maximizer())


def halfmax_adaptive(
    dets, motor, step: float = 5, precision: float = 1, maxct=None, max_channel=None
):
    if max_channel is None:
        detname = dets[0].name
    else:
        detname = max_channel

    def ct():
        ret = yield from trigger_and_read(dets)
        return ret[detname]["value"]

    @bpp.stage_decorator(dets)
    @run_return_decorator()
    def halfmax_inner(step, maxct=None):
        if maxct is None:
            maxct = yield from ct()
        current = maxct
        while np.abs(step) > precision / 2.0:
            yield from mvr(motor, -1 * step)
            current = yield from ct()
            while current > maxct / 2.0:
                yield from mvr(motor, step)
                current = yield from ct()
            step = step / 2.0
            if np.abs(step) > precision / 2.0:
                print(f"{detname} halfmax at {motor.name}:{motor.position}")
                print(f"Value: {current}, Max: {maxct}, reducing step to {step}")

        print(f"{detname} halfmax at {motor.name}:{motor.position}")
        print(f"Value: {current}, Max: {maxct}, " f"precision: {precision} reached")
        return motor.position

    return (yield from halfmax_inner(step, maxct))


def threshold_adaptive(
    dets, motor, threshold, step: float = 2, limit: int = 15, max_channel=None
):
    """
    Attempt to get a detector over a threshold by moving a motor
    """

    if max_channel is None:
        detname = dets[0].name
    else:
        detname = max_channel

    def ct():
        ret = yield from trigger_and_read(dets)
        return ret[detname]["value"]

    @bpp.stage_decorator(dets)
    @run_return_decorator()
    def inner_threshold():
        pos = motor.position
        maxpos = pos

        n = 0
        current = yield from ct()

        if current > threshold:
            mincurrent = current
            minpos = motor.position
            print(
                f"Starting above threshold of {detname}, try to get below {threshold} by moving {motor.name} with starting position {pos} and step -{step}"
            )
            while current > threshold and n < limit:
                yield from mvr(motor, -1 * step)
                current = yield from ct()
                if current < mincurrent:
                    mincurrent = current
                    minpos = motor.position
                n += 1
            if current < threshold:
                pass
            else:
                raise ValueError(
                    f"Detector {detname} did not fall below {threshold} after"
                    f" {limit} moves of {motor.name} with -{step} step "
                    f"size. Minimum value was {mincurrent} at {minpos}."
                    f"Check if {motor.name} is going the right direction,"
                    f" and if {detname} is on."
                )

        print(
            f"Searching for threshold value {threshold} of {detname} for {motor.name} with starting position {pos} and step {step}"
        )
        maxcurrent = current
        while current < threshold and n < limit:
            yield from mvr(motor, step)
            current = yield from ct()
            if current > maxcurrent:
                maxcurrent = current
                maxpos = motor.position
            n += 1
        if current > threshold:
            return motor.position
        else:
            raise ValueError(
                f"Detector {detname} did not exceed {threshold} after"
                f" {limit} moves of {motor.name} with {step} step "
                f"size. Maximum value was {maxcurrent} at {maxpos}."
                f"Check if {motor.name} is going the right direction,"
                f" and if {detname} is on."
            )

    return (yield from inner_threshold())
