import pytest
import numpy as np
from sst_base.frames import Panel
from sst_base.linalg import vec


@pytest.fixture()
def unit_panel():
    p1 = vec(1, 0, 0)
    p2 = vec(1, 0, 1)
    p3 = vec(-1, 0, 0)
    height = 10
    width = 2
    panel = Panel(p1, p2, p3, width=width, height=height)
    return panel


@pytest.fixture()
def rotated_panel():
    p1 = vec(0, 0, 0)
    p2 = vec(0, 0, 1)
    p3 = vec(0, 1, 0)
    height = 10
    width = 2
    panel = Panel(p1, p2, p3, width=width, height=height)
    return panel


def test_panel_position(unit_panel):
    coords = np.array(unit_panel.beam_to_frame(0, 0, 0, 0))
    assert np.all(coords == np.array([1, 0, 0, 90]))
    coords = np.array(unit_panel.beam_to_frame(0, 0, 1, 0))
    assert np.all(coords == np.array([1, -1, 0, 90]))
    coords = np.array(unit_panel.beam_to_frame(1, 0, 1, 0))
    assert np.all(coords == np.array([2, -1, 0, 90]))


def test_panel_distance_sign_convention(unit_panel):
    """
    Tests that the distance is positive when the beam is outside the
    panel, and negative when the beam is inside the panel
    """
    assert np.isclose(unit_panel.distance_to_beam(0, 0, 0, 0), 0)
    assert unit_panel.distance_to_beam(0, 0, 1, 0) > 0
    assert unit_panel.distance_to_beam(0, 0, -1, 0) < 0


def test_panel_distance_from_edge(unit_panel):
    assert np.isclose(unit_panel.distance_to_beam(0, 0, 0, 0), 0)
    assert np.isclose(unit_panel.distance_to_beam(0, 0, 1, 0), 1)
    assert np.isclose(unit_panel.distance_to_beam(0, 0, -0.5, 0), -0.5)
    assert np.isclose(unit_panel.distance_to_beam(0, 0, -1, 0), -1)
    assert np.isclose(unit_panel.distance_to_beam(0, 0, -2, 0), -1)
    assert np.isclose(unit_panel.distance_to_beam(0, 0, -3, 0), -1)


def test_panel_distance_from_corner(unit_panel):
    assert np.isclose(unit_panel.distance_to_beam(-1, 0, 0, 0), 0)
    assert np.isclose(unit_panel.distance_to_beam(-2, 0, -1, 0), 1)
    assert np.isclose(unit_panel.distance_to_beam(-2, 0, 0, 0), 1)
    assert np.isclose(unit_panel.distance_to_beam(-2, 0, 1, 0), np.sqrt(2))
    assert np.isclose(unit_panel.distance_to_beam(-1, 0, 1, 0), 1)


def test_edge_on_panel_distance(rotated_panel):
    assert np.isclose(rotated_panel.distance_to_beam(0, 0, 0, 0), 0)
    assert np.isclose(rotated_panel.distance_to_beam(0, 0, -1, 0), 0)
    assert np.isclose(rotated_panel.distance_to_beam(0, 0, 1, 0), 1)
    assert np.isclose(rotated_panel.distance_to_beam(1, 0, 1, 0), np.sqrt(2))
