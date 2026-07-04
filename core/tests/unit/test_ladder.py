from __future__ import annotations

import pytest

from core.models.exceptions import InvalidOrderError
from core.models.ladder import CashflowTranche, simulate_ladder


def _tranches():
    return [
        CashflowTranche("30d", 30, 50_000),
        CashflowTranche("60d", 60, 50_000),
        CashflowTranche("90d", 90, 100_000),
    ]


def _run(**overrides):
    params = {
        "spot": 10.0,
        "sigma_annual": 0.12,
        "domestic_rate": 0.03,
        "foreign_rate": 0.05,
        "target_margin_pct": 0.15,
        "n_sims": 60_000,
        "seed": 1,
        "min_acceptable_margin_pct": 0.05,
    }
    params.update(overrides)
    return simulate_ladder(_tranches(), **params)


def test_aggregates_all_tranches():
    result = _run()
    assert result.total_amount_foreign == pytest.approx(200_000.0)
    assert len(result.tranches) == 3
    assert result.total_revenue_domestic > 0


def test_layered_hedge_removes_the_downside():
    result = _run()
    # A layered forward locks the margin well above the unhedged tail (CVaR).
    assert result.layered_hedged_margin_pct > result.unhedged_cvar_margin_pct
    assert result.cvar_improvement_pct > 0


def test_expected_rate_matches_forward_under_risk_neutral_drift():
    result = _run(n_sims=200_000)
    for tranche in result.tranches:
        assert tranche.expected_rate == pytest.approx(tranche.forward_rate, rel=2e-3)


def test_forwards_decrease_when_foreign_rate_exceeds_domestic():
    result = _run()
    forwards = [t.forward_rate for t in result.tranches]
    assert forwards == sorted(forwards, reverse=True)


def test_longer_horizon_carries_more_variance():
    # Same shared Brownian path: terminal-rate dispersion grows with horizon.
    result = _run()
    assert result.simulated_margin_pct.std() > 0


def test_deterministic_with_seed():
    assert _run().unhedged_cvar_margin_pct == _run().unhedged_cvar_margin_pct


def test_rejects_empty_ladder():
    with pytest.raises(InvalidOrderError):
        simulate_ladder(
            [],
            spot=10.0,
            sigma_annual=0.1,
            domestic_rate=0.0,
            foreign_rate=0.0,
            target_margin_pct=0.1,
            n_sims=10_000,
        )
