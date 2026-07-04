from __future__ import annotations

import numpy as np
import pytest

from core.models.portfolio import (
    PortfolioPosition,
    currency_risk_contributions,
    simulate_portfolio,
)
from core.models.scoring import conditional_value_at_risk


def _positions():
    return [
        PortfolioPosition("usd", "USD", 100_000, 130_000, 10.0, 0.08, -0.02, 0.25),
        PortfolioPosition("eur", "EUR", 100_000, 130_000, 10.0, 0.20, -0.02, 0.25),
    ]


def test_component_cvars_sum_to_portfolio_cvar():
    rng = np.random.default_rng(0)
    weights = np.array([0.5, 0.5])
    margins = np.stack([rng.normal(0.2, 0.05, 40_000), rng.normal(0.15, 0.13, 40_000)])
    portfolio = weights[0] * margins[0] + weights[1] * margins[1]
    contribs = currency_risk_contributions(["USD", "EUR"], weights, margins, portfolio, {})
    total = sum(c.component_cvar_margin_pct for c in contribs)
    assert total == pytest.approx(conditional_value_at_risk(portfolio), abs=1e-9)


def test_contribution_shares_sum_to_one_and_rank_by_risk():
    result = simulate_portfolio(_positions(), np.eye(2), ["EUR", "USD"], 60_000, seed=3)
    contribs = result.risk_contributions
    assert sum(c.contribution_pct for c in contribs) == pytest.approx(1.0, abs=1e-9)
    # The higher-volatility leg (EUR, 20%) must dominate the tail risk.
    assert contribs[0].currency == "EUR"
    assert contribs[0].contribution_pct > contribs[1].contribution_pct


def test_contributions_expose_net_exposure():
    result = simulate_portfolio(_positions(), np.eye(2), ["EUR", "USD"], 40_000, seed=1)
    by_currency = {c.currency: c for c in result.risk_contributions}
    assert by_currency["USD"].net_exposure == pytest.approx(100_000.0)
    assert by_currency["EUR"].net_exposure == pytest.approx(100_000.0)
