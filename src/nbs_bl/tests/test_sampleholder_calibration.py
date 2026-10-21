import numpy as np
import pytest
from ophyd import Component as Cpt
from ophyd.positioner import SoftPositioner

from ..devices.sampleholders import Manipulator4AxBase
from ..geometry.affine import Frame
from ..geometry.bars import Standard4SidedBar


class SoftManipulator(Manipulator4AxBase):
    x = Cpt(SoftPositioner, init_pos=0)
    y = Cpt(SoftPositioner, init_pos=0)
    z = Cpt(SoftPositioner, init_pos=0)
    r = Cpt(SoftPositioner, init_pos=0)


SAMPLES = {
    "s1": {
        "name": "s1",
        "position": {"side": "1", "coordinates": (-5, 15, 5, 25), "thickness": 0},
    },
    "s4": {
        "name": "s4",
        "position": {"side": "1", "coordinates": (-5, 105, 5, 115), "thickness": 0},
    },
}


@pytest.fixture
def manipulator():
    m = SoftManipulator(
        name="manip",
        attachment_point=(0, 0, 464),
        holder=Standard4SidedBar(24.5, 215),
        use_redis=False,
    )
    m.load_sample_dict(SAMPLES)
    return m


def true_bar(attachment_point):
    manip_frame = Frame(origin=np.zeros(3))
    bar = Standard4SidedBar(24.5, 215)
    bar.attach_manipulator(manip_frame.make_child_frame(origin=attachment_point))
    return bar


def side_points(bar, side_index):
    """Calibration points (origin, +y, +x) of a side in manipulator coordinates."""
    side = bar.side_frames[side_index]
    return [side.to_global(p) for p in ((0, 0, 0), (0, 90, 0), (1, 0, 0))]


def sample_center(manipulator, sample_id):
    return manipulator.sample_frames[sample_id].to_global((0, 0, 0))


def test_frame_update_moves_children():
    parent = Frame(origin=(0, 0, 0))
    child = parent.make_child_frame(origin=(1, 2, 3))
    parent.update((0, 1, 0), (-1, 0, 0), (0, 0, 1), origin=(10, 0, 0))
    np.testing.assert_allclose(child.to_global((0, 0, 0)), (8, 1, 3))
    np.testing.assert_allclose(parent.from_global((8, 1, 3)), (1, 2, 3))


def test_update_side_with_nominal_points_changes_nothing(manipulator):
    before = sample_center(manipulator, "s4")
    bar = manipulator.holder
    manipulator.holder.update_side(0, *side_points(bar, 0))
    np.testing.assert_allclose(sample_center(manipulator, "s4"), before, atol=1e-9)


def test_update_side_moves_existing_samples(manipulator):
    # The real bar is mounted 2 mm lower, and off by 0.5 mm in x and y
    truth = true_bar((0.5, -0.5, 462))
    for side in range(4):
        manipulator.holder.update_side(side, *side_points(truth, side))
    for sample_id, sample in SAMPLES.items():
        expected = truth.make_sample_frame(sample["position"]).to_global((0, 0, 0))
        np.testing.assert_allclose(
            sample_center(manipulator, sample_id), expected, atol=1e-9
        )
    # Side 2 is untouched by side 1's samples, but must follow its own points
    np.testing.assert_allclose(
        manipulator.holder.side_frames[1].to_global((0, 0, 0)),
        truth.side_frames[1].to_global((0, 0, 0)),
        atol=1e-9,
    )


def test_rotation_center(manipulator):
    manipulator.set_sample("s1")
    at_zero = manipulator.forward(manipulator.PseudoPosition(0, 0, 0, 0))
    manipulator.set_rotation_center(1.5, -0.5)
    np.testing.assert_allclose(manipulator.rotation_center, (1.5, -0.5, 0))
    # Grazing incidence on side 1 is r=0, so nothing changes there
    shifted = manipulator.forward(manipulator.PseudoPosition(0, 0, 0, 0))
    np.testing.assert_allclose(tuple(shifted), tuple(at_zero), atol=1e-9)
    # At other angles the sample pivots about the rotation center
    for r in (10, 90, 200):
        rp = manipulator.forward(manipulator.PseudoPosition(1, 2, 0, r))
        pp = manipulator.inverse(rp)
        np.testing.assert_allclose(tuple(pp), (1, 2, 0, r), atol=1e-9)
        c = np.array((1.5, -0.5))
        p0 = np.array(at_zero[:2]) + np.array((0, -1))  # sx=1 is -y on side 1
        radius = np.linalg.norm(np.array(rp[:2]) - c)
        np.testing.assert_allclose(radius, np.linalg.norm(p0 - c), atol=1e-9)


def test_shift_sample(manipulator):
    before = manipulator.get_sample_position("s4", y=7)
    expected = manipulator.forward(manipulator.PseudoPosition(*before))
    manipulator.shift_sample("s4", dy=7)
    assert manipulator.samples["s4"]["position"]["coordinates"] == (-5, 112, 5, 122)
    assert manipulator.current_sample["position"]["coordinates"] == (-5, 112, 5, 122)
    after = manipulator.get_sample_position("s4")
    moved = manipulator.forward(manipulator.PseudoPosition(*after))
    np.testing.assert_allclose(tuple(moved), tuple(expected), atol=1e-9)


def test_shift_absolute_sample(manipulator):
    manipulator.add_sample(
        "abs", "abs", {"coordinates": [1, 2, 3, 4]}, origin="absolute"
    )
    manipulator.shift_sample("abs", dx=1, dy=-1)
    assert manipulator.samples["abs"]["position"]["coordinates"] == [2, 1, 3, 4]
    assert manipulator.sample_frames["abs"]["coordinates"] == [2, 1, 3, 4]


def test_recenter_sample_here(manipulator):
    # s4 is really 7 mm further along the bar; the beam is on its true center
    manipulator.set_sample("s4")
    true_center = manipulator.forward(manipulator.PseudoPosition(0, 7, 0, 0))
    for motor, value in zip(
        (manipulator.x, manipulator.y, manipulator.z, manipulator.r), true_center
    ):
        motor.set(value)
    manipulator.set_sample("s1")
    dx, dy = manipulator.recenter_sample_here("s4")
    np.testing.assert_allclose((dx, dy), (0, 7), atol=1e-9)
    assert manipulator.current_sample["sample_id"] == "s1"
    np.testing.assert_allclose(
        manipulator.samples["s4"]["position"]["coordinates"], (-5, 112, 5, 122)
    )
    manipulator.set_sample("s4")
    sx, sy, _, _ = manipulator.inverse(manipulator.real_position)
    np.testing.assert_allclose((sx, sy), (0, 0), atol=1e-9)
