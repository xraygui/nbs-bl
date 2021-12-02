from databroker.core import SingleRunCache
import bluesky.preprocessors as bpp
from bluesky.plan_stubs import mv, mvr
from bluesky.plans import count
import numpy as np


def find_max(plan, dets, *args, invert=False):
    """
    invert turns find_max into find_min
    """
    src = SingleRunCache()

    @bpp.subs_decorator(src.callback)
    def inner_maximizer():
        yield from plan(dets, *args)
        run = src.retrieve()
        table = run.primary.read()
        motor_names = run.metadata['start']['motors']
        motors = [m for m in args if getattr(m, 'name', None) in motor_names]
        detname = dets[0].name
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
            yield from mv(m, max_val)
        return ret
    return (yield from inner_maximizer())


def find_min(plan, dets, *args):
    return (yield from find_max(plan, dets, *args, invert=True))


def find_max_deriv(plan, dets, *args):
    src = SingleRunCache()

    @bpp.subs_decorator(src.callback)
    def inner_maximizer():
        yield from plan(dets, *args)
        run = src.retrieve()
        table = run.primary.read()
        motor_names = run.metadata['start']['motors']
        motors = [m for m in args if getattr(m, 'name', None) in motor_names]
        if len(motors) > 1:
            print("Derivative with multiple motors unsupported, \
            taking first motor")

        detname = dets[0].name
        motname = motors[0].name
        max_idx = np.argmax(np.abs(np.gradient(table[detname],
                                               table[motname])))
        print(f"Maximum derivative found at step {max_idx} for detector {detname}")
        ret = []
        for m in motors:
            max_val = float(table[m.name][max_idx])
            print(f"setting {m.name} to {max_val}")
            ret.append([m, max_val])
            yield from mv(m, max_val)
        return ret
    return (yield from inner_maximizer())


def halfmax_adaptive(dets, motor, step=5, precision=1, maxct=None):
    detname = dets[0].name

    def ct():
        src = SingleRunCache()

        @bpp.subs_decorator(src.callback)
        def inner_ct():
            yield from count(dets)
            run = src.retrieve()
            table = run.primary.read()
            return float(table[detname])
        return (yield from inner_ct())

    if maxct is None:
        maxct = yield from ct()
    current = maxct
    while current > maxct/2.0:
        yield from mvr(motor, step)
        current = yield from ct()
    if np.abs(step) > precision:
        print(f"{detname} halfmax at {motor.name}:{motor.position}")
        print(f"Value: {current}, Max: {maxct}, reducing step to {step/2.0}")
        yield from mvr(motor, -1*step)
        pos = yield from halfmax_adaptive(dets, motor, step=step/2.0,
                                          precision=precision, maxct=maxct)
    else:
        print(f"{detname} halfmax at {motor.name}:{motor.position}")
        print(f"Value: {current}, Max: {maxct}, "
              f"precision: {precision} reached")
        pos = motor.position
        yield from mv(motor, pos)
    return pos


def threshold_adaptive(dets, motor, threshold, step=2, limit=15):
    """
    Attempt to get a detector over a threshold by moving a motor\
    """
    detname = dets[0].name
    def ct():
        src = SingleRunCache()

        @bpp.subs_decorator(src.callback)
        def inner_ct():
            yield from count(dets)
            run = src.retrieve()
            table = run.primary.read()
            return float(table[detname])
        return (yield from inner_ct())

    pos = motor.position
    maxpos = pos
    current = yield from ct()
    n = 0
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
        raise ValueError(f"Detector {detname} did not exceed {threshold} after"
                         f" {limit} moves of {motor.name} with {step} step "
                         f"size. Maximum value was {maxcurrent} at {maxpos}."
                         f"Check if {motor.name} is going the right direction,"
                         f" and if {detname} is on.")
