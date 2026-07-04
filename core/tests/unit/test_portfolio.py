from __future__ import annotations

import numpy as np
import pytest

from core.models.exceptions import InvalidOrderError
from core.models.portfolio import (
    PortfolioPosition,
    net_exposures,
    simulate_portfolio,
)


def _position(
    currency, amount=100_000.0, revenue=1_150_000.0, sigma=0.15, drift=-0.02, horizon=0.5
):
    return PortfolioPosition(
        label=f"pos_{currency}",
        foreign_currency=currency,
        amount_foreign=amount,
        revenue_domestic=revenue,
        spot=10.0,
        sigma_annual=sigma,
        drift_annual=drift,
        horizon_years=horizon,
    )


def test_net_exposures_aggregates_per_currency():
    positions = [_position("USD"), _position("USD", amount=50_000.0), _position("EUR")]
    exposures = net_exposures(positions)
    assert exposures["USD"] == pytest.approx(150_000.0)
    assert exposures["EUR"] == pytest.approx(100_000.0)


def test_simulate_portfolio_basic_consistency():
    positions = [_position("USD"), _position("EUR")]
    corr = np.array([[1.0, 0.3], [0.3, 1.0]])
    result = simulate_portfolio(positions, corr, ["EUR", "USD"], n_sims=20_000, seed=1)

    assert 0 <= result.vulnerability_score <= 100
    assert result.total_revenue_domestic == pytest.approx(2_300_000.0)
    ordered = [result.margin_pct_percentiles[f"P{p}"] for p in (5, 10, 25, 50, 75, 90, 95)]
    assert ordered == sorted(ordered)


def test_diversification_reduces_tail_risk_versus_perfect_correlation():
    positions = [_position("USD"), _position("EUR")]
    low = simulate_portfolio(
        positions, np.array([[1.0, 0.0], [0.0, 1.0]]), ["EUR", "USD"], 40_000, 2
    )
    high = simulate_portfolio(
        positions, np.array([[1.0, 0.99], [0.99, 1.0]]), ["EUR", "USD"], 40_000, 2
    )

    assert low.cvar_margin_pct > high.cvar_margin_pct
    assert low.diversification_benefit_pct > high.diversification_benefit_pct


def test_shared_currency_positions_are_perfectly_correlated():
    positions = [_position("USD"), _position("USD")]
    result = simulate_portfolio(positions, np.array([[1.0]]), ["USD"], 20_000, 3)
    assert np.isfinite(result.cvar_margin_pct)


def test_rejects_empty_portfolio():
    with pytest.raises(InvalidOrderError):
        simulate_portfolio([], np.array([[1.0]]), ["USD"], 20_000, 1)


def test_rejects_mismatched_correlation_matrix():
    with pytest.raises(InvalidOrderError):
        simulate_portfolio(
            [_position("USD")], np.array([[1.0, 0.0], [0.0, 1.0]]), ["USD"], 20_000, 1
        )


def test_rejects_invalid_n_sims():
    with pytest.raises(InvalidOrderError):
        simulate_portfolio([_position("USD")], np.array([[1.0]]), ["USD"], 10, 1)


def test_non_psd_correlation_falls_back_to_eigen_clipping():
    positions = [_position("USD"), _position("EUR"), _position("GBP")]
    non_psd = np.array(
        [
            [1.0, 0.9, -0.9],
            [0.9, 1.0, 0.9],
            [-0.9, 0.9, 1.0],
        ]
    )
    assert np.min(np.linalg.eigvalsh(non_psd)) < 0

    result = simulate_portfolio(positions, non_psd, ["EUR", "GBP", "USD"], 20_000, 4)
    assert np.isfinite(result.cvar_margin_pct)
    assert 0 <= result.vulnerability_score <= 100
