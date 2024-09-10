from ..utils import merge_func
from ..plans.preprocessors import wrap_metadata


def _make_gscan_points(*args, shift: float = 0):
    if len(args) < 3:
        raise TypeError(
            f"gscan requires at least estart, estop, and delta, received {args}"
        )
    if len(args) % 2 == 0:
        raise TypeError(
            "gscan received an even number of arguments. Either a step or a step-size is missing"
        )
    start = float(args[0])
    points = [start + shift]
    for stop, step in zip(args[1::2], args[2::2]):
        nextpoint = points[-1] + step
        while nextpoint < stop - step / 2.0 + shift:
            points.append(nextpoint)
            nextpoint += step
        points.append(stop + shift)
    return points
