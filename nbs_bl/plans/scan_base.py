from ..utils import merge_func
from ..plans.preprocessors import wrap_metadata


def _make_gscan_points(*args, shift: float = 0):
    """
    Generate a sequence of energy scan points from a variable-length parameter list.

    Parameters should be passed in the following format:
        (estart1, delta1, estop1, delta2, estop2, ...)

    - Each segment defines a range starting from the given estart and ending at the estop,
      using the specified delta (step size).
    - Delta values must be positive. The function automatically determines the direction
      (increasing or decreasing) based on the estart and estop values.
    - A single energy value can be passed to return a single-point list.
    - Segments can be non-monotonic — i.e., you can mix increasing and decreasing ranges.
    - An optional `shift` parameter can be used to apply a constant offset to all values.

    Examples:
        _make_gscan_points(250)
            ➜ [250.0]

        _make_gscan_points(250, 5, 260)
            ➜ [250.0, 255.0, 260.0]

        _make_gscan_points(264, 2, 260, 5, 250)
            ➜ [264.0, 262.0, 260.0, 255.0, 250.0]

    Raises:
        TypeError if the number of arguments is incorrect
        ValueError if any delta is zero
    """
    
    if len(args) == 1:
        return [float(args[0]) + shift]
    if (len(args) - 1) % 2 != 0:
        raise TypeError(
            "gscan received an even number of arguments. Either a stop or a step-size is missing.  Expected format: (estart1, delta1, estop1, delta2, estop2, ...)"
        )
    points = []
    for i in range(1, len(args) - 1, 2):
        estart = float(args[i - 1]) + shift
        delta = abs(args[i]) ## Ensures delta is positive in case users input negative delta for reverse energy list.
        estop = float(args[i + 1]) + shift

        if delta == 0:
            raise ValueError("Step size (delta) cannot be zero.")

        step = delta if estop > estart else -delta

        if not points or points[-1] != estart:
            points.append(estart)

        next_point = estart + step
        while (step > 0 and next_point < estop - step / 2.0) or (step < 0 and next_point > estop - step / 2.0):
            points.append(next_point)
            next_point += step

        points.append(estop)

    return points
