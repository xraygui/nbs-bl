import numpy as np
from scipy.special import erf

from ..plans.maximizers import halfmax_position


def edge(x, center, width=1.0, low=0.0, high=500.0):
    return low + (high - low) * 0.5 * (1 + erf((x - center) / width))


def test_halfmax_interpolates_between_points():
    x = np.linspace(-14.25, -10.25, 29)
    y = edge(x, -12.25)
    assert abs(halfmax_position(x, y) - -12.25) < 0.01


def test_halfmax_uses_the_range_not_zero():
    x = np.linspace(0, 4, 21)
    y = edge(x, 1.87, low=300.0, high=800.0)
    assert abs(halfmax_position(x, y) - 1.87) < 0.01


def test_halfmax_descending_scan():
    x = np.linspace(2, -2, 41)
    y = edge(-x, -0.3)
    assert abs(halfmax_position(x, y) - 0.3) < 0.01


def test_halfmax_with_noise():
    rng = np.random.default_rng(0)
    x = np.linspace(-2, 2, 29)
    errors = []
    for _ in range(50):
        y = rng.poisson(edge(x, 0.4)).astype(float)
        errors.append(halfmax_position(x, y) - 0.4)
    # Noise on the plateaus biases min/max slightly; ~0.02 mm here
    assert abs(np.mean(errors)) < 0.03
    assert np.std(errors) < 0.05


def test_halfmax_step_edge():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([0.0, 0.0, 10.0, 10.0])
    assert abs(halfmax_position(x, y) - 1.5) < 1e-9
