"""
Geometry for calibrating a bar on a 4-axis manipulator. Pure numpy, no motion.

Positions are in manipulator coordinates at r = 0, relative to the rotation
axis: the frame ``side_points`` writes and ``RectangularBar.update_side``
reads.

The bar's cross-section is a rectangle. ``a`` is its half-extent normal to
face 0 (side 1), ``b`` its half-extent normal to face 1. A square 4-sided bar
has a = b; a 2-sided plate has a = thickness / 2 and b = width / 2. Face f is
edge-on to the beam at a manipr offset of k + 90 f, where k is the bar's
rotation on its mount.

At a manipr offset r (degrees, from side 1's r = 0), an x edge scan finds the
bar's support in direction u(r) = (-cos r, sin r): the leading edge is at
distance C.u + a |cos(r - k)| + b |sin(r - k)| from the axis, and the
trailing edge (found by carrying on through the bar) at -C.u + (the same).
C is the bar centre, linear in z when the bar is tilted.
"""

import numpy as np

from .linalg import vec


def _rot2(degrees, v):
    t = np.radians(degrees)
    c, s = np.cos(t), np.sin(t)
    v = np.asarray(v, dtype=float)
    return np.stack([c * v[..., 0] - s * v[..., 1], s * v[..., 0] + c * v[..., 1]], -1)


def side_points(x1, y1, x3, y3, z1, z3, r1, center=(0, 0, 0)):
    """
    Side calibration points in manipulator coordinates.

    Parameters
    ----------
    x1, x3 : float
        Distances of the side's surface from the rotation axis at z1 and z3,
        with the side edge-on to the beam at manipr = r1.
    y1, y3 : float
        Distances of the side's origin corner (shared with the next face)
        from the axis, along the surface, at z1 and z3.
    z1, z3 : float
        manipz of the two points; z1 should be at the bar end.
    r1 : float
        manipr (degrees) at which the side is edge-on.
    center : array-like
        The manipulator's rotation center.

    Returns
    -------
    tuple of np.ndarray
        p1 (side origin), p2 (further along the bar), p3 (along the surface),
        as ``RectangularBar.update_side`` expects.
    """
    center = np.asarray(center, dtype=float)
    local = np.array([(-x1, y1, z1), (-x3, y3, z3), (-x1, y1 - 1, z1)], dtype=float)
    xy = _rot2(-r1, local[:, :2])
    return tuple(vec(p[0], p[1], q[2]) + center for p, q in zip(xy, local))


def corner_y(x1, r1, x2, r2, nsides=4):
    """
    Position of a side's origin corner along its surface, for a regular polygon.

    x1 is the side's surface distance from the axis, x2 the next side's.
    Only valid for regular polygons with three or more sides.
    """
    if nsides < 3:
        raise ValueError(f"corner_y needs a regular polygon, not {nsides} sides")
    x1 = np.abs(x1)
    x2 = np.abs(x2)
    # interior angle for a regular polygon
    ia = np.radians(180.0 * (nsides - 2) / nsides)
    phi1 = np.arctan(np.sin(ia) / (x2 / x1 + np.cos(ia)))
    return x1 / np.tan(phi1)


def _columns(rows, k, zref, tilt, square):
    """Design matrix for the linear parameters at mount angle k (degrees)."""
    cols = []
    for r, z, trailing, _ in rows:
        rr, kk = np.radians(r), np.radians(r - k)
        sign = -1.0 if trailing else 1.0
        ux, uy = -np.cos(rr), np.sin(rr)
        row = [sign * ux, sign * uy]
        if tilt:
            row += [sign * ux * (z - zref), sign * uy * (z - zref)]
        if square:
            row.append(abs(np.cos(kk)) + abs(np.sin(kk)))
        else:
            row += [abs(np.cos(kk)), abs(np.sin(kk))]
        cols.append(row)
    return np.array(cols)


def fit_rigid_bar(rows, half_extents=None, square=True, kmax=10.0, k=None, tilt=None):
    """
    Fit the rigid-bar model to edge measurements.

    Parameters
    ----------
    rows : list of (r, z, trailing, d)
        manipr offset from side 1's r = 0 (degrees), manipz, whether the edge
        is the trailing one, and its distance from the rotation axis.
    half_extents : (float, float), optional
        Fix (a, b) instead of fitting them.
    square : bool
        Tie a = b (a square bar). Otherwise a and b are fitted separately,
        which needs edges near both face 0 and face 1.
    kmax : float
        Mount angles searched, in degrees either side of 0.
    k : float, optional
        Fix the mount angle instead of fitting it.
    tilt : bool, optional
        Fit a tilt (centre linear in z). By default, if the rows span more
        than 1 mm in z.

    Returns
    -------
    dict with k, a, b, cx, cy, tx, ty (tilt per mm of z), zref, rms,
    residuals (one per row, measured minus model) and at_limit.
    """
    d = np.array([row[3] for row in rows], dtype=float)
    zs = np.array([row[1] for row in rows], dtype=float)
    zref = float(zs.mean())
    if tilt is None:
        tilt = np.ptp(zs) > 1.0
    nsupport = 1 if square else 2

    def solve(k):
        A = _columns(rows, k, zref, tilt, square)
        y = d.copy()
        if half_extents is not None:
            fixed = [half_extents[0]] if square else list(half_extents)
            y -= A[:, -nsupport:] @ np.array(fixed, dtype=float)
            A = A[:, :-nsupport]
        p, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ p
        return float(resid @ resid), p, resid

    fixed_k = k is not None
    if not fixed_k:
        grid = np.arange(-kmax, kmax + 1e-9, 0.05)
        k = grid[int(np.argmin([solve(g)[0] for g in grid]))]
        # Golden-section refinement inside one grid step either side
        lo, hi = k - 0.05, k + 0.05
        g = (np.sqrt(5) - 1) / 2
        for _ in range(40):
            a, b = hi - g * (hi - lo), lo + g * (hi - lo)
            if solve(a)[0] < solve(b)[0]:
                hi = b
            else:
                lo = a
        k = 0.5 * (lo + hi)
    _, p, resid = solve(k)
    p = list(p)
    cx, cy = p.pop(0), p.pop(0)
    tx, ty = (p.pop(0), p.pop(0)) if tilt else (0.0, 0.0)
    if half_extents is not None:
        a, b = half_extents
    elif square:
        a = b = p.pop(0)
    else:
        a, b = p.pop(0), p.pop(0)
    return {
        "k": float(k),
        "a": float(a),
        "b": float(b),
        "cx": float(cx),
        "cy": float(cy),
        "tx": float(tx),
        "ty": float(ty),
        "zref": zref,
        "rms": float(np.sqrt(np.mean(resid**2))),
        "residuals": [float(v) for v in resid],
        "at_limit": not fixed_k and abs(k) > kmax - 0.1,
    }


def edge_distance(fit, r, z, trailing=False):
    """Model distance of an edge from the axis at manipr offset r and height z."""
    rr, kk = np.radians(r), np.radians(r - fit["k"])
    cx = fit["cx"] + fit["tx"] * (z - fit["zref"])
    cy = fit["cy"] + fit["ty"] * (z - fit["zref"])
    centre = -cx * np.cos(rr) + cy * np.sin(rr)
    if trailing:
        centre = -centre
    return centre + fit["a"] * abs(np.cos(kk)) + fit["b"] * abs(np.sin(kk))


def face_distance(fit, face, z):
    """Distance of a face (0-3 round the cross-section) from the axis at height z, seen edge-on."""
    return edge_distance(fit, fit["k"] + 90.0 * face, z)


def face_corner_heights(fit, z_end, faces=(0, 1, 2, 3), r0=0.0, beam_x=0.0):
    """
    Heights of the bar-end corners, correcting find_z for tilt.

    find_z (at manipr = 0, beam at beam_x from the axis) finds the lowest
    point of the end face along the beam's chord across it. The end face is
    square to the bar axis, so a tilted bar's corners sit at different
    heights. The fit's coordinates are turned by r0 (side 1's r = 0).

    Returns
    -------
    list of float
        The height of each face's origin corner, or None if the beam chord
        misses the bar end.
    """
    a, b, k = fit["a"], fit["b"], fit["k"]
    t = np.array([fit["tx"], fit["ty"]])
    reach = 3 * max(a, b)
    s = np.linspace(-reach, reach, 20001)
    chord = _rot2(r0, np.stack([np.full_like(s, beam_x), s], axis=1))
    ez = z_end
    for _ in range(3):
        centre = np.array(
            [fit["cx"] + t[0] * (ez - fit["zref"]), fit["cy"] + t[1] * (ez - fit["zref"])]
        )
        # The cross-section's face-0 axis is turned by -k
        local = _rot2(k, chord - centre)
        inside = (np.abs(local[:, 0]) <= a) & (np.abs(local[:, 1]) <= b)
        if not inside.any():
            return None
        # A point p on the end face is at height ez - t.(p - centre)
        ez = z_end + float(((chord[inside] - centre) @ t).max())
    corners = [(-a, b), (a, b), (a, -b), (-a, -b)]
    return [ez - float(_rot2(-k, corners[f]) @ t) for f in faces]
