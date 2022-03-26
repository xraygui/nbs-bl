from databroker.core import SingleRunCache
import bluesky.preprocessors as bpp
from .preprocessors import run_return_decorator
from bluesky.plan_stubs import mv, mvr, trigger_and_read
from bluesky.plans import count
import numpy as np


def find_max(plan, dets, *args, max_channel=None, invert=False):
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
            yield from mv(m, max_val)
        return ret
    return (yield from inner_maximizer())


def find_min(plan, dets, *args):
    return (yield from find_max(plan, dets, *args, invert=True))


def find_max_deriv(plan, dets, *args, max_channel=None):
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

        if max_channel is None:
            detname = dets[0].name
        else:
            detname = max_channel
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


def halfmax_adaptive(dets, motor, step=5, precision=1, maxct=None, max_channel=None):
    if max_channel is None:
        detname = dets[0].name
    else:
        detname = max_channel

    def ct():
        ret = yield from trigger_and_read(dets)
        return ret[detname]['value']

    @bpp.stage_decorator(dets)
    @run_return_decorator()
    def halfmax_inner(step, maxct=None):
        if maxct is None:
            maxct = yield from ct()
        current = maxct
        while np.abs(step) > precision/2.0:
            yield from mvr(motor, -1*step)
            current = yield from ct()
            while current > maxct/2.0:
                yield from mvr(motor, step)
                current = yield from ct()
            step = step/2.0
            if np.abs(step) > precision/2.0:
                print(f"{detname} halfmax at {motor.name}:{motor.position}")
                print(f"Value: {current}, Max: {maxct}, reducing step to {step}")

        print(f"{detname} halfmax at {motor.name}:{motor.position}")
        print(f"Value: {current}, Max: {maxct}, "
              f"precision: {precision} reached")
        return motor.position

    return (yield from halfmax_inner(step, maxct))


def threshold_adaptive(dets, motor, threshold, step=2, limit=15, max_channel=None):
    """
    Attempt to get a detector over a threshold by moving a motor
    """

    if max_channel is None:
        detname = dets[0].name
    else:
        detname = max_channel

    def ct():
        ret = yield from trigger_and_read(dets)
        return ret[detname]['value']

    @bpp.stage_decorator(dets)
    @run_return_decorator()
    def inner_threshold():
        pos = motor.position
        maxpos = pos

        n = 0
        current = yield from ct()
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
    return (yield from inner_threshold())
