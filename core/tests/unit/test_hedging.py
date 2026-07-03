from __future__ import annotations

import numpy as np
import pytest

from core.models.hedging import HedgeAnalysis, evaluate_hedge, optimal_hedge_ratio


def _build(revenue, amount, forward, rates, alpha=0.05):
    margin_pct = 1.0 - (amount / revenue) * rates
    return evaluate_hedge(
        revenue=revenue,
        amount_foreign=amount,
        forward_rate=forward,
        simulated_rates=rates,
        simulated_margin_pct=margin_pct,
        alpha=alpha,
        spot_rate=forward,
    )


def test_hedged_margin_equals_full_hedge_reconstruction():
    rng = np.random.default_rng(0)
    revenue, amount, forward = 1_000_000.0, 100_000.0, 8.5
    rates = 8.5 * np.exp(rng.normal(0, 0.1, 50_000))
    analysis = _build(revenue, amount, forward, rates)

    reconstructed = 1.0 - (amount / revenue) * forward
    assert analysis.hedged_margin_pct == pytest.approx(reconstructed)


def test_full_hedge_optimal_when_volatility_dominates():
    rng = np.random.default_rng(1)
    revenue, amount, forward = 1_000_000.0, 100_000.0, 9.0
    rates = 9.0 * np.exp(rng.normal(0, 0.4, 50_000))
    analysis = _build(revenue, amount, forward, rates)

    assert analysis.optimal_hedge_ratio == pytest.approx(1.0)
    assert analysis.cvar_improvement_pct > 0
    assert analysis.optimal_hedge_cvar_margin_pct >= analysis.unhedged_cvar_margin_pct


def test_probability_unhedged_beats_hedge_is_share_below_forward():
    rates = np.array([8.0, 8.5, 9.0, 9.5, 10.0])
    analysis = _build(1_000_000.0, 100_000.0, 9.0, rates)
    assert analysis.probability_unhedged_beats_hedge == pytest.approx(2 / 5)


def test_forward_points_reflects_spot_reference():
    rates = np.array([8.0, 9.0, 10.0])
    analysis = evaluate_hedge(
        revenue=1_000_000.0,
        amount_foreign=100_000.0,
        forward_rate=9.2,
        simulated_rates=rates,
        simulated_margin_pct=1.0 - (100_000.0 / 1_000_000.0) * rates,
        spot_rate=9.0,
    )
    assert analysis.forward_points == pytest.approx(0.2)


def test_optimal_hedge_ratio_returns_value_in_unit_interval():
    rng = np.random.default_rng(2)
    unhedged = rng.normal(0.1, 0.05, 10_000)
    effect = rng.normal(0.0, 0.05, 10_000)
    ratio, cvar = optimal_hedge_ratio(unhedged, effect, alpha=0.05, grid_step=0.05)
    assert 0.0 <= ratio <= 1.0
    assert np.isfinite(cvar)


def test_returns_hedge_analysis_dataclass():
    rates = np.array([8.0, 9.0, 10.0])
    result = _build(1_000_000.0, 100_000.0, 9.0, rates)
    assert isinstance(result, HedgeAnalysis)
