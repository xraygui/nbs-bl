import numpy as np
from numbers import Number
from .scan_base import _make_gscan_points

"""
Time estimation functions for plan execution time calculation.

Usage Examples:
---------------
1. Basic time estimation:
   estimation_dict = {
       "estimator": "generic_estimate",
       "fixed": 10,
       "overhead": 0.5,
       "dwell": "dwell_time"
   }
   plan_args = {"dwell_time": 2.0, "points": 100}
   time = generic_estimate("my_plan", plan_args, estimation_dict)

2. With repeat functionality:
   estimation_dict = {
       "estimator": "generic_estimate", 
       "fixed": 10,
       "overhead": 0.5,
       "dwell": "dwell_time",
       "reset": 5.0  # 5 seconds between repeats
   }
   plan_args = {"dwell_time": 2.0, "points": 100, "repeat": 3}
   time = generic_estimate("my_plan", plan_args, estimation_dict)
   # Result: (base_time * 3) + (5.0 * 2) = base_time * 3 + 10.0
"""


def with_repeat(estimator_func):
    """
    Decorator to add repeat functionality to time estimators.

    This decorator handles the "repeat" parameter in plan_args and "reset" parameter
    in estimation_dict. It calculates the base plan time, multiplies by repeats,
    and adds reset time for each repeat except the last one.

    Parameters
    ----------
    estimator_func : callable
        The original time estimator function

    Returns
    -------
    callable
        Wrapped estimator function that handles repeats
    """

    def wrapper(plan_name, plan_args, estimation_dict):
        # Get repeat count and remove from plan_args to avoid confusion
        repeat_count = plan_args.get("repeat", 1)

        # Get reset time from estimation parameters
        reset_time = estimation_dict.get("reset_time", 0)

        # Calculate base plan time using original estimator
        base_time = estimator_func(plan_name, plan_args, estimation_dict)

        if base_time is None:
            return None

        # Calculate total time: base_time * repeats + reset_time * (repeats - 1)
        total_time = base_time * repeat_count + reset_time * (repeat_count - 1)

        return total_time

    return wrapper


def get_dwell(plan_args, estimation_dict):
    dwell = estimation_dict.get("dwell", "dwell")
    if isinstance(dwell, str):
        return plan_args.get(dwell, 0)
    else:
        return dwell


@with_repeat
def generic_estimate(plan_name, plan_args, estimation_dict):
    a = estimation_dict.get("fixed", 0)
    b = estimation_dict.get("overhead", 0)
    c = get_dwell(plan_args, estimation_dict)
    if "points" in estimation_dict:
        points = estimation_dict.get("points")
        if isinstance(points, str):
            if points == "args":
                n = len(plan_args.get("args", []))
            else:
                n = plan_args.get(points, 0)
        else:
            n = points
    else:
        n = 0
    return a + b * n + c * n


@with_repeat
def list_scan_estimate(plan_name, plan_args, estimation_dict):
    a = estimation_dict.get("fixed", 0)
    b = estimation_dict.get("overhead", 0)
    c = get_dwell(plan_args, estimation_dict)

    n = len(plan_args.get("args", ["", []])[1])
    return a + b * n + c * n


@with_repeat
def grid_scan_estimate(plan_name, plan_args, estimation_dict):
    a = estimation_dict.get("fixed", 0)
    b = estimation_dict.get("overhead", 0)
    c = get_dwell(plan_args, estimation_dict)

    args = plan_args.get("args")
    n_axes = len(args) // 4
    n_points = 1
    for i in range(n_axes):
        n_points *= args[i * 4 + 3]
    return a + b * n_points + c * n_points


@with_repeat
def list_grid_scan_estimate(plan_name, plan_args, estimation_dict):
    a = estimation_dict.get("fixed", 0)
    b = estimation_dict.get("overhead", 0)
    c = get_dwell(plan_args, estimation_dict)

    args = plan_args.get("args")
    n_axes = len(args) // 2
    n_points = 1
    for i in range(n_axes):
        n_points *= len(args[i * 2 + 1])
    return a + b * n_points + c * n_points


def _fly_scan_segments(plan_args):
    if "args" in plan_args:
        args = list(plan_args["args"])
        if args and not isinstance(args[0], Number):
            args = args[1:]
    else:
        return [(plan_args.get("start", 0), plan_args.get("stop", 0), plan_args.get("speed", 1))]

    if len(args) < 3:
        return None

    if len(args) % 3 == 0:
        return [tuple(args[i : i + 3]) for i in range(0, len(args), 3)]

    if (len(args) - 3) % 2 == 0:
        segments = [tuple(args[:3])]
        start = args[1]
        for stop, speed in zip(args[3::2], args[4::2]):
            segments.append((start, stop, speed))
            start = stop
        return segments

    return None


@with_repeat
def fly_scan_estimate(plan_name, plan_args, estimation_dict):
    segments = _fly_scan_segments(plan_args)
    if segments is None:
        return None
    a = estimation_dict.get("fixed", 0)
    return a + sum(np.abs((stop - start) / speed) for start, stop, speed in segments)


@with_repeat
def gscan_estimate(plan_name, plan_args, estimation_dict):
    if "region" in estimation_dict:
        region = estimation_dict.get("region")
    else:
        region = plan_args.get("args")
    if len(region) % 2 == 0:
        region = region[1:]  # First argument is motor name
    points = len(_make_gscan_points(*region))
    a = estimation_dict.get("fixed", 0)
    b = estimation_dict.get("overhead", 0)
    c = get_dwell(plan_args, estimation_dict)

    return a + b * points + c * points
