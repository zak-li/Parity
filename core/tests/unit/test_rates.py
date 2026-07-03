from __future__ import annotations

import numpy as np
import pytest

from core.models.exceptions import SimulationError
from core.models.rates import cip_drift, forward_points, theoretical_forward_rate


def test_cip_drift_is_rate_differential():
    assert cip_drift(0.03, 0.05) == pytest.approx(-0.02)
    assert cip_drift(0.05, 0.02) == pytest.approx(0.03)


def test_zero_differential_forward_equals_spot():
    assert theoretical_forward_rate(10.0, 0.04, 0.04, 0.5) == pytest.approx(10.0)


def test_forward_matches_covered_interest_parity():
    spot, rd, rf, t = 10.0, 0.03, 0.05, 0.5
    expected = spot * np.exp((rd - rf) * t)
    assert theoretical_forward_rate(spot, rd, rf, t) == pytest.approx(expected)


def test_higher_domestic_rate_pushes_forward_above_spot():
    assert theoretical_forward_rate(10.0, 0.06, 0.02, 1.0) > 10.0


def test_forward_points_sign():
    assert forward_points(10.0, 9.8) == pytest.approx(-0.2)
    assert forward_points(10.0, 10.3) == pytest.approx(0.3)


@pytest.mark.parametrize(
    "spot,rd,rf,t",
    [(0, 0.03, 0.05, 0.5), (-1, 0.03, 0.05, 0.5), (10.0, 0.03, 0.05, 0), (10.0, 0.03, 0.05, -1)],
)
def test_rejects_invalid_inputs(spot, rd, rf, t):
    with pytest.raises(SimulationError):
        theoretical_forward_rate(spot, rd, rf, t)


def test_rejects_non_finite_rates():
    with pytest.raises(SimulationError):
        cip_drift(float("nan"), 0.05)
