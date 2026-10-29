"""
Manipulator and sample bar calibration plans.

The plans read the bar's geometry from the manipulator's holder (a
``RectangularBar``): a 4-sided bar gets four side frames, a 2-sided plate
two. Distances are measured from the rotation axis, so run
``calibrate_beam_offset`` first; that is a property of the manipulator, not
the bar.

- ``calibrate_bar``: fits the whole bar as one rigid rectangle from edges
  around side 1, and writes every side's frame. Works for any holder.
- ``calibrate_bar_angle``: finds how far the bar is rotated on its mount
  from a V of edges around one face, and turns the side frames to match.
- ``calibrate_sides``: measures each face at two heights and finds corners
  from neighbouring faces. Only for regular bars with three or more sides.

Calibrations are saved in MANIPULATOR_CONFIG and restored at startup (see
``nbs_bl.manipulator_calibration``).
"""

import numpy as np
from bluesky.plan_stubs import mv, null
from bluesky.preprocessors import finalize_wrapper

from nbs_bl.geometry.calibration import (
    corner_y,
    edge_distance,
    face_corner_heights,
    face_distance,
    fit_rigid_bar,
    side_points,
)
from nbs_bl.help import add_to_plan_list
from nbs_bl.manipulator_calibration import (
    clear_sides,
    manipulator_config,
    restore_manipulator_calibration,
    save_rotation_center,
    save_side,
)
from nbs_bl.plans.edges import edge_direction, edge_near, find_x, find_z, manipulator
from nbs_bl.plans.plan_stubs import call_obj, clear_plan_status, update_plan_status
from nbs_bl.samples import move_sample, set_sample

# A fit worse than this (mm) means a bad edge or a bar that isn't the shape
# the holder says, so the plans stop rather than apply it. Generous for real
# motor jitter; the beam is about 1 mm across.
MAX_FIT_RMS = 0.15


def _holder():
    holder = manipulator().holder
    if not hasattr(holder, "faces"):
        raise TypeError(
            f"{type(holder).__name__} has no bar faces to calibrate"
        )
    return holder


def _axis_x():
    """manipx at which the rotation axis is in the beam"""
    return manipulator().rotation_center[0]


def _status(msg):
    """Show calibration progress in the GUI's running-plan status"""
    print(msg)
    yield from update_plan_status(msg)


def set_side(side_num):
    """Set the current sample to a side's origin, without moving"""
    yield from set_sample(f"side{side_num}")


def update_manipulator_side(side, *points):
    """Replace a side's (numbered from 1) frame with calibrated points, and save them"""
    manip = manipulator()
    yield from call_obj(manip.holder, "update_side", side - 1, *points)
    save_side(manip, side, points)


def set_manipulator_origin(*, x=None, y=None):
    """
    Set where the rotation axis is (manipx, manipy); with no arguments,
    load the saved one.
    """
    manip = manipulator()
    if x is None and y is None:
        restore_manipulator_calibration(manip)
        return
    center = list(manip.rotation_center[:2])
    for i, val in enumerate([x, y]):
        if val is not None:
            print(f"Setting rotation axis {'xy'[i]} to {val}")
            center[i] = val
    manip.set_rotation_center(*center)
    save_rotation_center(manip)


@add_to_plan_list
def load_saved_manipulator_calibration():
    """Apply the saved manipulator calibration"""
    restore_manipulator_calibration(manipulator())
    yield from null()


# ---------------------------------------------------------------------------
# Rotation axis


def find_beam_x_offset(side=1, rdiff=180):
    """manipx of the rotation axis, from a side's surface seen from both ways"""
    manip = manipulator()
    yield from set_side(side)
    # We want to move off the sample
    yield from move_sample(None, x=-1, y=5, r=5)
    x1 = yield from find_x()
    yield from move_sample(None, x=-1, y=5, r=5 + rdiff)
    x2 = yield from find_x(invert=True)
    yield from mv(manip.r, 0, manip.x, 0)
    return (x1 + x2) * 0.5


@add_to_plan_list
def calibrate_beam_offset(side=1, rdiff=180):
    """Find where the rotation axis is in x, from a side's surface at r and r + 180"""

    def inner():
        yield from _status("Beam offset: finding the rotation axis x position")
        x = yield from find_beam_x_offset(side, rdiff)
        set_manipulator_origin(x=x)
        yield from _status(f"Beam offset: rotation axis at x = {x:.3f}")
        return x

    return (yield from finalize_wrapper(inner(), clear_plan_status()))


# ---------------------------------------------------------------------------
# Edge measurements around a face


class _EdgeLog:
    """Measured edges around one face, with predictions for the next one."""

    def __init__(self, r0, half_extents, square):
        self.r0 = r0
        self.half_extents = half_extents
        self.square = square
        self.x0 = _axis_x()
        self.rows = []
        # manipx = x0 + lead_sign * d for a leading edge, x0 - lead_sign * d
        # for a trailing one (the axis is inside the bar)
        self.lead_sign = None

    def add(self, r, z, trailing, x):
        if self.lead_sign is None:
            below = 1 if x < self.x0 else -1
            self.lead_sign = below if trailing else -below
        d = abs(x - self.x0)
        self.rows.append((r - self.r0, z, trailing, d))
        print(
            f"Edge at r = {r - self.r0:+.2f}, z = {z:.2f}"
            f"{' (trailing)' if trailing else ''}: x = {x:.4f}, d = {d:.4f}"
        )

    def fit(self, **kwargs):
        return fit_rigid_bar(
            self.rows, half_extents=self.half_extents, square=self.square, **kwargs
        )

    def predict(self, r, z, trailing):
        """
        Expected manipx of an edge, from the edges so far with the size fixed.

        The mount angle is only fitted once there are edges on both sides of
        r0; before that k = 0, and the first edge on the other arm of the V
        can be off by about 2 b sin(k). Tilt is left out: it is only fitted
        well once all the edges are in.
        """
        rows = self.rows
        if len(rows) >= 2:
            rs = np.array([row[0] for row in rows])
            both_arms = len(rows) >= 3 and (rs < 0).any() and (rs > 0).any()
            fit = self.fit(k=None if both_arms else 0.0, tilt=False)
        else:
            # The nominal bar at k = 0, shifted along the scan to match the one edge
            a, b = self.half_extents
            fit = {"k": 0.0, "a": a, "b": b, "cx": 0.0, "cy": 0.0,
                   "tx": 0.0, "ty": 0.0, "zref": z}
            r1, z1, tr1, d1 = rows[0]
            shift = d1 - edge_distance(fit, r1, z1, tr1)
            fit["cx"] = (shift if tr1 else -shift) / np.cos(np.radians(r1))
        d = edge_distance(fit, r - self.r0, z, trailing)
        sign = -self.lead_sign if trailing else self.lead_sign
        return self.x0 + sign * d

    def measure(self, r, z, trailing=False):
        """Move to r and z and find the edge, using a prediction once one exists."""
        manip = manipulator()
        if self.rows:
            x_pred = self.predict(r, z, trailing)
            step = edge_direction(trailing)
            # Rotate, climb and move x together
            yield from mv(manip.r, r, manip.z, z, manip.x, x_pred - 0.6 * step)
            x = yield from edge_near(x_pred, trailing)
        else:
            yield from mv(manip.r, r, manip.z, z)
            x = yield from find_x(invert=trailing)
        self.add(r, z, trailing, x)
        return x


def _go_to_face(side, z):
    """Move side's surface into the beam at height z, square as calibrated."""
    manip = manipulator()
    yield from set_side(side)
    yield from mv(manip.z, z)
    y = manip.sy.position
    yield from move_sample(None, x=0, y=y, z=0, r=0)
    return manip.r.position


def _side_points_from_frames():
    """Current side frames as side_points-style points (r = 0 coords)."""
    corners = [(0, 0, 0), (0, 1, 0), (1, 0, 0)]
    return [
        [frame.to_global(np.array(c, dtype=float)) for c in corners]
        for frame in _holder().side_frames
    ]


def _rotate_about_axis(p, degrees):
    centre = manipulator().rotation_center
    v = np.asarray(p, dtype=float) - centre
    t = np.radians(degrees)
    c, s = np.cos(t), np.sin(t)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1], v[2]]) + centre


def _print_fit(fit, title):
    print(
        f"{title}: k = {fit['k']:+.3f} deg, size = {2 * fit['a']:.4f} x "
        f"{2 * fit['b']:.4f} mm, centre = ({fit['cx']:+.4f}, {fit['cy']:+.4f}) mm, "
        f"tilt = ({1000 * fit['tx']:+.3f}, {1000 * fit['ty']:+.3f}) mrad, "
        f"rms = {1000 * fit['rms']:.1f} um"
    )
    print("  residuals (um): " + ", ".join(f"{1000 * v:+.1f}" for v in fit["residuals"]))


def _check_fit(fit):
    if fit["at_limit"]:
        raise ValueError("Mount angle is outside the scanned angles; not applying it")
    if fit["rms"] > MAX_FIT_RMS:
        raise ValueError(
            f"Fit rms {1000 * fit['rms']:.0f} um is over {1000 * MAX_FIT_RMS:.0f} um;"
            " not applying it. Check the edges above for a bad scan, or that the"
            " holder's size matches the bar."
        )


def _find_bar_end(findz):
    manip = manipulator()
    if findz:
        yield from _status("Calibration: finding the bar end (z)")
        yield from mv(manip.r, 0, manip.x, 0)
        return (yield from find_z())
    return manip.z.position


# ---------------------------------------------------------------------------
# Rigid-bar calibration


@add_to_plan_list
def calibrate_bar(findz=True, angles=(-8, -4, 0, 4, 8), lever=100, fit_size=True):
    """Calibrate every side of the bar from edges around side 1, fitting one rigid bar"""
    _holder()
    return (
        yield from finalize_wrapper(
            _calibrate_bar(findz, angles, lever, fit_size), clear_plan_status()
        )
    )


def _calibrate_bar(findz, angles, lever, fit_size):
    """
    Measures, all leading edges unless noted:
      z1 (5 mm above the bar end): side 1 at each angle (the V), then face 1
      (side 2 of a square bar, the edge of a plate)
      climb to z2 = z1 + lever, staying on face 1
      z2: face 1, then side 1 and its trailing edge
    The V fixes the mount angle, face 1 and side 1 the centre, the trailing
    edge the thickness across side 1, and the z2 edges the tilt both ways.
    The bar's size is fitted unless fit_size is False.
    """
    holder = _holder()
    angles = sorted(angles)
    z = yield from _find_bar_end(findz)
    bump = 5
    z1 = z + bump
    z2 = z1 + lever

    yield from _status("Rigid calibration: moving to side 1")
    r0 = yield from _go_to_face(1, z1)
    log = _EdgeLog(r0, holder.half_extents, holder.is_square)
    n_edges = len(angles) + 4
    count = 0

    def status(msg):
        nonlocal count
        count += 1
        return _status(f"Rigid calibration: edge {count} of {n_edges}, {msg}")

    for a in angles:
        yield from status(f"side 1 at r0 {a:+g} deg, z = {z1:.1f}")
        yield from log.measure(r0 + a, z1)
    # Measure the other faces edge-on, where an error in k matters least
    k = log.fit()["k"]
    yield from status(f"face 1, z = {z1:.1f}")
    yield from log.measure(r0 + k + 90, z1)
    yield from status(f"face 1, z = {z2:.1f}")
    yield from log.measure(r0 + k + 90, z2)
    yield from status(f"side 1, z = {z2:.1f}")
    yield from log.measure(r0 + k, z2)
    yield from status(f"side 1 trailing edge, z = {z2:.1f}")
    yield from log.measure(r0 + k, z2, trailing=True)

    fit = fit_rigid_bar(
        log.rows,
        half_extents=None if fit_size else holder.half_extents,
        square=holder.is_square,
        kmax=max(abs(angles[0]), abs(angles[-1])),
    )
    _print_fit(fit, "Rigid bar fit")
    _check_fit(fit)

    yield from _status(f"Rigid calibration: updating sides 1-{holder.sides}")
    corner_z = None
    if findz:
        beam_x = -_axis_x()  # manipx = 0 during find_z
        corner_z = face_corner_heights(fit, z, holder.faces, r0, beam_x)
    if corner_z is None:
        corner_z = [z] * holder.sides
    print(
        "Bar-end corner heights (tilt-corrected): "
        + ", ".join(f"{c:.3f}" for c in corner_z)
    )
    center = manipulator().rotation_center
    clear_sides()
    for i, face in enumerate(holder.faces):
        side = i + 1
        nxt = (face + 1) % 4
        za = corner_z[i]
        zb = za + lever
        x1 = face_distance(fit, face, za)
        y1 = face_distance(fit, nxt, za)
        x3 = face_distance(fit, face, zb)
        y3 = face_distance(fit, nxt, zb)
        r1 = r0 + fit["k"] + 90.0 * face
        print(
            f"Side {side}: x1={x1:.3f} y1={y1:.3f} x3={x3:.3f} y3={y3:.3f} "
            f"z1={za:.3f} z2={zb:.3f} r1={r1:.3f}"
        )
        points = side_points(x1, y1, x3, y3, za, zb, r1, center)
        yield from update_manipulator_side(side, *points)
    manipulator_config()["rigid_fit"] = {
        key: fit[key] for key in ("k", "a", "b", "cx", "cy", "tx", "ty", "zref", "rms")
    }
    yield from _status(
        f"Rigid calibration: done, k = {fit['k']:+.3f} deg, rms = {1000 * fit['rms']:.0f} um"
    )
    return fit


# ---------------------------------------------------------------------------
# Mount angle


@add_to_plan_list
def calibrate_bar_angle(side=1, angles=(-8, -4, 0, 4, 8), apply=True):
    """Find the bar's rotation on its mount from edges around one face, and correct the side frames"""
    _holder()
    return (
        yield from finalize_wrapper(
            _calibrate_bar_angle(side, angles, apply), clear_plan_status()
        )
    )


def _calibrate_bar_angle(side, angles, apply):
    """
    The leading edge traces a V as the face rotates through edge-on; the
    kink is where the face is edge-on. The bar's offset from the axis tilts
    both arms equally and does not move the kink. Uses the current z, which
    should be on the bar, and x edge scans only (an r scan at fixed x is not
    geometric with a drain-current detector).
    """
    holder = _holder()
    angles = sorted(angles)
    if angles[0] >= 0 or angles[-1] <= 0:
        raise ValueError("angles must include values either side of 0")
    face = holder.faces[side - 1]
    a, b = holder.half_extents
    # Seen from this face, the extents normal to it and to the next face
    extents = (a, b) if face % 2 == 0 else (b, a)
    z = manipulator().z.position
    yield from _status(f"Angle calibration: moving to side {side}")
    r0 = yield from _go_to_face(side, z)
    log = _EdgeLog(r0, extents, holder.is_square)
    for i, ang in enumerate(angles):
        yield from _status(
            f"Angle calibration: edge {i + 1} of {len(angles)} at r0 {ang:+g} deg"
        )
        yield from log.measure(r0 + ang, z)
    fit = fit_rigid_bar(
        log.rows,
        square=holder.is_square,
        half_extents=None if holder.is_square else extents,
        kmax=max(abs(angles[0]), abs(angles[-1])),
    )
    _print_fit(fit, f"Side {side} V fit")
    k = fit["k"]
    _check_fit(fit)
    if apply and abs(k) > 1e-4:
        # side_points rotates by -r1, so a face edge-on k later rotates its
        # points by -k
        for i, points in enumerate(_side_points_from_frames()):
            rotated = [_rotate_about_axis(p, -k) for p in points]
            yield from update_manipulator_side(i + 1, *rotated)
        print(f"Rotated all side frames by {k:+.3f} deg")
    yield from mv(manipulator().r, r0 + k)
    yield from _status(f"Angle calibration: bar is at {k:+.3f} deg")
    return k


# ---------------------------------------------------------------------------
# Face-by-face calibration (regular bars only)


@add_to_plan_list
def calibrate_sides(side_start=1, side_end=None, findz=True, preserve=False):
    """Calibrate sides side_start..side_end face by face, at two heights"""
    holder = _holder()
    if holder.sides < 3 or not holder.is_square:
        raise ValueError(
            f"calibrate_sides finds corners from neighbouring faces, which needs a "
            f"regular bar; this holder is {type(holder).__name__} with "
            f"{holder.sides} sides. Use calibrate_bar instead."
        )
    if side_end is None:
        side_end = holder.sides
    return (
        yield from finalize_wrapper(
            _calibrate_sides(side_start, side_end, holder.sides, findz, preserve),
            clear_plan_status(),
        )
    )


def _find_side_x(side, z, label=""):
    """Surface x distance from the rotation axis for one side at height z"""
    yield from _status(f"Calibration {label}: side {side} surface at z = {z:.1f}")
    yield from _go_to_face(side, z)
    x = yield from find_x()
    return np.abs(x - _axis_x()), manipulator().r.position


def _calibrate_sides(side_start, side_end, nsides, findz, preserve):
    """
    Measures every side at one height, then again at a second height in
    reverse, so the climb needs no rotation.
    """
    if not preserve:
        clear_sides()
    z = yield from _find_bar_end(findz)
    bump = 5
    z1 = z + bump
    z2 = z1 + 100

    # Each side needs the next side's surface too, for its corner
    order = list(range(side_start, side_end + 1))
    wraps = side_start == 1 and side_end == nsides
    if not wraps:
        order.append(side_end % nsides + 1)

    xr1, xr2 = {}, {}
    for side in order:
        xr1[side] = yield from _find_side_x(side, z1, "pass 1 of 2")
    # Pass 2 starts where pass 1 ended, so the climb to z2 needs no rotation
    for side in reversed(order):
        xr2[side] = yield from _find_side_x(side, z2, "pass 2 of 2")

    yield from _status(f"Calibration: updating sides {side_start}-{side_end}")
    center = manipulator().rotation_center
    for side in range(side_start, side_end + 1):
        nxt = side % nsides + 1
        x1, r1 = xr1[side]
        x2, r2 = xr1[nxt]
        x3, _ = xr2[side]
        x4, _ = xr2[nxt]
        y1 = corner_y(x1, r1, x2, r2, nsides)
        y3 = corner_y(x3, r1, x4, r2, nsides)
        print(
            f"Side {side}: x1={x1:.3f} y1={y1:.3f} x3={x3:.3f} y3={y3:.3f} "
            f"z1={z1:.3f} z2={z2:.3f} r1={r1:.3f}"
        )
        # x was measured at z1 and z2; label the points bump lower so p1
        # sits at the bar end.
        points = side_points(x1, y1, x3, y3, z1 - bump, z2 - bump, r1, center)
        yield from update_manipulator_side(side, *points)
    yield from _status(f"Calibration: sides {side_start}-{side_end} done")
