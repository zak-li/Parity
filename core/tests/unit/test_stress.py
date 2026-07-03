from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.models.exceptions import InsufficientDataError, SimulationError
from core.models.stress import (
    StressScenario,
    apply_scenarios,
    canonical_scenarios,
    historical_stress_scenario,
    margin_at_rate,
    reverse_stress_test,
    worst_adverse_move,
)


def test_margin_at_rate_matches_formula():
    margin_domestic, margin_pct = margin_at_rate(1_000_000.0, 100_000.0, 8.0)
    assert margin_domestic == pytest.approx(200_000.0)
    assert margin_pct == pytest.approx(0.2)


def test_margin_at_rate_rejects_non_positive_revenue():
    with pytest.raises(SimulationError):
        margin_at_rate(0.0, 100_000.0, 8.0)


def test_apply_scenarios_shocks_rate_and_measures_change():
    scenarios = (StressScenario("choc +10%", 0.10), StressScenario("choc -10%", -0.10))
    outcomes = apply_scenarios(1_150_000.0, 100_000.0, 10.0, budgeted_margin_pct=0.13, scenarios=scenarios)

    assert outcomes[0].shocked_rate == pytest.approx(11.0)
    assert outcomes[1].shocked_rate == pytest.approx(9.0)
    assert outcomes[0].margin_pct < outcomes[1].margin_pct
    assert outcomes[0].margin_pct_change < 0


def test_reverse_stress_finds_breaking_rate():
    result = reverse_stress_test(1_150_000.0, 100_000.0, 10.0, target_margin_pct=0.0)
    assert result.breaking_rate == pytest.approx(11.5)
    assert result.required_rate_move_pct == pytest.approx(0.15)


def test_reverse_stress_with_positive_target():
    result = reverse_stress_test(1_000_000.0, 100_000.0, 8.0, target_margin_pct=0.10)
    assert result.breaking_rate == pytest.approx(9.0)


def test_reverse_stress_rejects_invalid_inputs():
    with pytest.raises(SimulationError):
        reverse_stress_test(1_000_000.0, 0.0, 8.0)


def test_worst_adverse_move_detects_largest_upswing():
    dates = pd.bdate_range("2025-01-01", periods=60)
    values = np.linspace(10.0, 10.0, 60)
    values[30:] = 12.0
    series = pd.Series(values, index=dates)
    assert worst_adverse_move(series, horizon_days=20) == pytest.approx(0.2, abs=0.01)


def test_worst_adverse_move_requires_enough_history():
    dates = pd.bdate_range("2025-01-01", periods=10)
    series = pd.Series(np.linspace(10, 11, 10), index=dates)
    with pytest.raises(InsufficientDataError):
        worst_adverse_move(series, horizon_days=20)


def test_historical_stress_scenario_wraps_move():
    dates = pd.bdate_range("2025-01-01", periods=60)
    values = np.full(60, 10.0)
    values[30:] = 11.5
    series = pd.Series(values, index=dates)
    scenario = historical_stress_scenario(series, 20, "crise")
    assert scenario.name == "crise"
    assert scenario.rate_shock_pct == pytest.approx(0.15, abs=0.01)


def test_canonical_scenarios_are_configured():
    scenarios = canonical_scenarios()
    assert len(scenarios) >= 3
    assert any(s.rate_shock_pct > 0 for s in scenarios)
    assert any(s.rate_shock_pct < 0 for s in scenarios)
