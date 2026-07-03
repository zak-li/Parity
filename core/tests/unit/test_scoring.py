from __future__ import annotations

import numpy as np
import pytest

from core.models import scoring


def test_percentiles_returns_expected_keys_and_values():
    values = np.arange(1, 101, dtype="float64")
    result = scoring.percentiles(values, points=(10, 50, 90))
    assert set(result) == {"P10", "P50", "P90"}
    assert result["P50"] == pytest.approx(50.5, rel=0.02)


def test_percentiles_single_point():
    values = np.arange(1, 101, dtype="float64")
    result = scoring.percentiles(values, points=(50,))
    assert set(result) == {"P50"}


def test_probability_below_threshold():
    values = np.array([0.1, 0.2, -0.1, -0.5, 0.05])
    assert scoring.probability_below_threshold(values, 0.0) == pytest.approx(2 / 5)


def test_cvar_averages_worst_tail():
    values = np.array([-10.0, -9.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert scoring.conditional_value_at_risk(values, alpha=0.2) == pytest.approx(-9.5)


def test_cvar_takes_ceil_of_alpha_fraction():
    values = np.array([5.0, 1.0, 3.0, 2.0, 4.0])
    assert scoring.conditional_value_at_risk(values, 0.2) == pytest.approx(1.0)
    assert scoring.conditional_value_at_risk(values, 0.4) == pytest.approx(1.5)


def test_cvar_rejects_empty_array():
    with pytest.raises(ValueError):
        scoring.conditional_value_at_risk(np.array([]))


def test_vulnerability_score_zero_when_no_risk():
    assert scoring.vulnerability_score(0.0, 0.3, 0.3) == 0


def test_vulnerability_score_hundred_when_full_risk():
    assert scoring.vulnerability_score(1.0, 0.3, -0.3) == 100


def test_vulnerability_score_handles_non_positive_budgeted_margin():
    score_bad = scoring.vulnerability_score(0.5, -0.1, -0.5)
    score_neutral = scoring.vulnerability_score(0.5, -0.1, 0.0)
    assert score_bad > score_neutral
