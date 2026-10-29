import numpy as np
import pytest
from ophyd import Component as Cpt
from ophyd.positioner import SoftPositioner

from ..devices.sampleholders import Manipulator4AxBase
from ..geometry.affine import Frame
from ..geometry.bars import Standard2SidedBar, Standard4SidedBar
from ..geometry.calibration import (
    edge_distance,
    face_corner_heights,
    face_distance,
    fit_rigid_bar,
    side_points,
)


class SoftManipulator(Manipulator4AxBase):
    x = Cpt(SoftPositioner, init_pos=0)
    y = Cpt(SoftPositioner, init_pos=0)
    z = Cpt(SoftPositioner, init_pos=0)
    r = Cpt(SoftPositioner, init_pos=0)


def attached(holder, attachment_point=(0, 0, 464)):
    manip_frame = Frame(origin=np.zeros(3))
    holder.attach_manipulator(manip_frame.make_child_frame(origin=attachment_point))
    return holder


def frame_points(holder, side_index, lever=100):
    side = holder.side_frames[side_index]
    return [side.to_global(p) for p in ((0, 0, 0), (0, lever, 0), (1, 0, 0))]


def true_fit(k, a, b, cx=0.3, cy=-0.2, tx=0.0, ty=0.0, zref=300.0):
    return dict(k=k, a=a, b=b, cx=cx, cy=cy, tx=tx, ty=ty, zref=zref)


def rigid_rows(fit, z1, z2, angles=(-8, -4, 0, 4, 8)):
    """The edges rigid calibration measures, computed from a known bar."""
    k = fit["k"]
    spec = [(a, z1, False) for a in angles]
    spec += [(k + 90, z1, False), (k + 90, z2, False), (k, z2, False), (k, z2, True)]
    return [(r, z, tr, edge_distance(fit, r, z, tr)) for r, z, tr in spec]


@pytest.mark.parametrize(
    "truth, square",
    [
        (true_fit(1.3, 12.25, 12.25, tx=0.002, ty=-0.001), True),
        (true_fit(-2.0, 1.5, 7.5, tx=-0.001, ty=0.002), False),
    ],
    ids=["square", "plate"],
)
def test_fit_recovers_bar(truth, square):
    rows = rigid_rows(truth, 255, 355)
    fit = fit_rigid_bar(rows, square=square)
    for key in ("k", "a", "b", "tx", "ty"):
        assert fit[key] == pytest.approx(truth[key], abs=1e-6)
    zref = fit["zref"]
    cx = truth["cx"] + truth["tx"] * (zref - truth["zref"])
    assert fit["cx"] == pytest.approx(cx, abs=1e-6)
    assert fit["rms"] < 1e-6


def test_face_distance_uses_the_right_half_extent():
    fit = true_fit(0.0, 1.5, 7.5, cx=0, cy=0)
    assert [face_distance(fit, f, 0) for f in range(4)] == pytest.approx(
        [1.5, 7.5, 1.5, 7.5]
    )


@pytest.mark.parametrize(
    "holder",
    [Standard4SidedBar(24.5, 215), Standard2SidedBar(15, 3, 150)],
    ids=["square", "plate"],
)
def test_side_points_match_holder_frames(holder):
    attached(holder)
    a, b = holder.half_extents
    fit = true_fit(0.0, a, b, cx=0, cy=0)
    z_end = 464 - holder.length
    for i, face in enumerate(holder.faces):
        nxt = (face + 1) % 4
        x1 = face_distance(fit, face, z_end)
        y1 = face_distance(fit, nxt, z_end)
        points = side_points(x1, y1, x1, y1, z_end, z_end + 100, 90 * face)
        np.testing.assert_allclose(points, frame_points(holder, i), atol=1e-9)


def test_two_sided_bar_has_two_sides():
    bar = attached(Standard2SidedBar(15, 3, 150))
    assert bar.sides == 2
    assert bar.half_extents == (1.5, 7.5)
    side_md, side_frames = bar.get_geometry()
    assert list(side_md) == ["side1", "side2"]


def test_corner_heights_level_bar():
    fit = true_fit(0.5, 1.5, 7.5, cx=0, cy=0)
    assert face_corner_heights(fit, 314, faces=(0, 2)) == pytest.approx([314, 314])


def manipulator(holder):
    m = SoftManipulator(
        name="manip", attachment_point=(0, 0, 464), holder=holder, use_redis=False
    )
    return m


@pytest.mark.parametrize(
    "holder, expected",
    [
        (Standard4SidedBar(24.5, 215), [0, 90, 180, 270]),
        (Standard2SidedBar(15, 3, 150), [0, 180]),
    ],
    ids=["square", "plate"],
)
def test_side_grazing_angles(holder, expected):
    m = manipulator(holder)
    angles = []
    for n in range(holder.sides):
        m.set_sample(f"side{n + 1}")
        angles.append(m.sample_rotation_to_manip_rotation(0))
    assert angles == pytest.approx(expected, abs=1e-9)


def test_small_negative_rotation_keeps_sides_near_nominal():
    """Side frames edge-on 2 deg early give side 1 r = -2, not 358, and side 4 r = 268."""
    holder = Standard4SidedBar(24.5, 215)
    m = manipulator(holder)
    # Turning the points by +2 deg makes each side edge-on 2 deg earlier in r
    t = np.radians(2.0)
    c, s = np.cos(t), np.sin(t)
    for i in range(4):
        rotated = [np.array([c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]])
                   for p in frame_points(holder, i)]
        holder.update_side(i, *rotated)
    angles = []
    for n in range(4):
        m.set_sample(f"side{n + 1}")
        angles.append(m.sample_rotation_to_manip_rotation(0))
    assert angles == pytest.approx([-2, 88, 178, 268], abs=1e-9)
