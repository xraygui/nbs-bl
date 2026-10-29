"""
Edge finding for manipulator alignment.

The alignment detector comes from a beamline role: ``direct_alignment`` (a
drain current on the manipulator, high when the bar is in the beam) or
``indirect_alignment`` (a detector the bar shadows, low when the bar is in
the beam). It needs a threshold in ``bl.detectors.thresholds``.

Fly scans go over the edge both ways and average the two edges, which
cancels the lag between motor and detector readings.
"""

import numpy as np
from bluesky.plan_stubs import mv, mvr
from bluesky.plans import rel_scan

from nbs_bl.beamline import GLOBAL_BEAMLINE as bl
from nbs_bl.plans.flyscan_base import fly_scan
from nbs_bl.plans.maximizers import (
    find_halfmax,
    find_max,
    find_max_deriv,
    halfmax_adaptive,
    threshold_adaptive,
)


def manipulator():
    """The beamline's primary sample manipulator."""
    manip = bl.primary_sampleholder
    if manip is None:
        raise KeyError("No primary_sampleholder is configured")
    return manip


def alignment_detector():
    """Name of the detector used for alignment"""
    if hasattr(bl, "indirect_alignment"):
        return bl.indirect_alignment.name
    elif hasattr(bl, "direct_alignment"):
        return bl.direct_alignment.name
    raise KeyError("Neither indirect nor direct alignment detector found, not guessing!")


def alignment_is_direct():
    """True if the alignment signal is high when the sample is in the beam"""
    if hasattr(bl, "indirect_alignment"):
        return False
    elif hasattr(bl, "direct_alignment"):
        return True
    raise KeyError("Neither indirect nor direct alignment detector found, not guessing!")


def _threshold(detname):
    if detname not in bl.detectors.thresholds:
        raise KeyError(
            f"{detname} has no threshold value and cannot be used to find an edge"
        )
    return bl.detectors.thresholds[detname]


def edge_direction(trailing=False):
    """Direction (+1 or -1) to move manipx from low to high signal."""
    invert = trailing
    # The scan's step goes from low to high signal; with an indirect detector
    # that is from the bar towards the open beam.
    if not alignment_is_direct():
        invert = not invert
    return -1 if invert else 1


def find_edge(
    dets, motor, step, start, stop, points, max_channel=None, fly=True, two_way=True
):
    """
    Find the half-maximum edge of a signal along a motor.

    Parameters
    ----------
    dets : list
    motor : Ophyd motor
    step : float
        Step that takes the detector from low to high signal, used to find
        the threshold crossing first.
    start, stop : float
        Scan window relative to the threshold crossing.
    points : int
        Points in the scan.
    fly : bool
        Fly the window instead of stepping.
    two_way : bool
        For fly scans, fly back over the edge as well and average the edges.
    """
    detname = dets[0].name if max_channel is None else max_channel
    thres_pos = yield from threshold_adaptive(
        dets, motor, _threshold(detname), step=step, max_channel=max_channel
    )
    print(f"Found threshold {thres_pos} for {motor.name}, moving to {thres_pos + start}")
    yield from mv(motor, thres_pos + start)
    if fly:
        # Fly slowly enough to get about one reading per point; otherwise the
        # motor's own velocity is used and a fast motor gives only a few points.
        period = 0.2
        speed = abs(stop - start) / (points * period)
        ret = yield from find_halfmax(
            fly_scan,
            dets,
            motor,
            thres_pos + start,
            thres_pos + stop,
            speed,
            max_channel=max_channel,
            period=period,
        )
        if two_way:
            forward = ret[0][1]
            ret = yield from find_halfmax(
                fly_scan,
                dets,
                motor,
                thres_pos + stop,
                thres_pos + start,
                speed,
                max_channel=max_channel,
                period=period,
            )
            backward = ret[0][1]
            edge = 0.5 * (forward + backward)
            print(
                f"Fly edges for {motor.name}: {forward:.4f} forward, "
                f"{backward:.4f} back, lag {0.5 * (forward - backward):.4f}"
            )
            yield from mv(motor, edge)
            ret = [[motor, edge]]
    else:
        ret = yield from find_halfmax(
            rel_scan, dets, motor, 0, stop - start, points, max_channel=max_channel
        )
    print(f"Found halfmax {ret[0][1]} for {motor.name}")
    return ret[0][1]


def _find_axis_edge(motor, invert, precision, fly):
    step = edge_direction(invert)
    start, stop = -2 * step, 2 * step
    points = int(np.abs(start - stop) / precision) + 1
    return (
        yield from find_edge(
            bl.detectors.active,
            motor,
            step,
            start,
            stop,
            points,
            max_channel=alignment_detector(),
            fly=fly,
        )
    )


def find_x(invert=False, precision=0.1, fly=True):
    """Find the bar's x edge. invert=True finds the trailing edge."""
    print("Finding x edge position")
    return (yield from _find_axis_edge(manipulator().x, invert, precision, fly))


def find_z(invert=False, precision=0.1, fly=True):
    """Find the bar end in z. The manipulator should start with the bar out of the beam."""
    print("Finding z edge position")
    return (yield from _find_axis_edge(manipulator().z, invert, precision, fly))


def edge_near(x_pred, trailing=False, precision=0.1):
    """
    Find an x edge expected near x_pred, with a narrower window than find_x.

    Starts just on the low-signal side, so the threshold search needs about
    one step, then flies a 2.5 mm window both ways. Falls back to find_x if
    the edge lands more than 1 mm from the prediction.
    """
    manipx = manipulator().x
    step = edge_direction(trailing)
    yield from mv(manipx, x_pred - 0.6 * step)
    start, stop = -1.5 * step, 1.0 * step
    points = int(abs(stop - start) / precision) + 1
    x = yield from find_edge(
        bl.detectors.active,
        manipx,
        step,
        start,
        stop,
        points,
        max_channel=alignment_detector(),
    )
    if abs(x - x_pred) > 1.0:
        print(f"Edge {x:.3f} is far from the predicted {x_pred:.3f}; rescanning")
        yield from mv(manipx, x_pred - 2 * step)
        x = yield from find_x(invert=trailing)
    return x


# Stepped scans, kept from ucal for manual alignment


def _scan_offset(motor, start, stop, step_size, finder, **kwargs):
    nsteps = int(np.abs(stop - start) / step_size) + 1
    ret = yield from finder(
        rel_scan,
        bl.detectors.active,
        motor,
        start,
        stop,
        nsteps,
        max_channel=alignment_detector(),
        **kwargs,
    )
    _, offset = ret[0]
    print(offset)
    return offset


def scan_z_offset(zstart, zstop, step_size):
    return (yield from _scan_offset(manipulator().z, zstart, zstop, step_size, find_max_deriv))


def scan_x_offset(xstart, xstop, step_size):
    return (yield from _scan_offset(manipulator().x, xstart, xstop, step_size, find_max_deriv))


def scan_r_offset(rstart, rstop, step_size):
    """Relative scan, find r that maximizes signal"""
    return (
        yield from _scan_offset(
            manipulator().r, rstart, rstop, step_size, find_max, invert=alignment_is_direct()
        )
    )


def scan_z_coarse():
    return (yield from scan_z_offset(-10, 10, 1))


def scan_z_medium():
    return (yield from scan_z_offset(-2, 2, 0.2))


def scan_z_fine():
    return (yield from scan_z_offset(-0.5, 0.5, 0.05))


def scan_r_coarse():
    return (yield from scan_r_offset(-10, 10, 1))


def scan_r_medium():
    return (yield from scan_r_offset(-2, 2, 0.1))


def scan_r_fine():
    return (yield from scan_r_offset(-0.5, 0.5, 0.05))


def scan_x_coarse():
    """Find x to within 1 mm, initial misalignment can be +- 7 mm"""
    return (yield from scan_x_offset(-7, 7, 1))


def scan_x_medium():
    """Find x to within 0.25 mm, initial misalignment can be +- 2 mm"""
    return (yield from scan_x_offset(-2, 2, 0.25))


def scan_x_fine():
    """Find x to within 0.05 mm, initial misalignment can be +- 0.5 mm"""
    return (yield from scan_x_offset(-0.5, 0.5, 0.05))


def find_edge_adaptive(dets, motor, step, precision, max_channel=None):
    """
    Find an edge with adaptive steps.

    step : float
        Step that takes the detector from low to high signal.
    precision : float
        Desired precision of the edge position.
    """
    detname = dets[0].name if max_channel is None else max_channel
    yield from threshold_adaptive(
        dets, motor, _threshold(detname), step=step, max_channel=max_channel
    )
    yield from mvr(motor, step)
    return (
        yield from halfmax_adaptive(
            dets, motor, -1 * step, precision=precision, max_channel=max_channel
        )
    )
