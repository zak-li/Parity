from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import settings
from .enums import RiskLevel
from .exceptions import InvalidOrderError
from .scoring import (
    conditional_value_at_risk,
    percentiles,
    probability_below_threshold,
    vulnerability_score,
)


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    label: str
    foreign_currency: str
    amount_foreign: float
    revenue_domestic: float
    spot: float
    sigma_annual: float
    drift_annual: float
    horizon_years: float
    min_acceptable_margin_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    total_revenue_domestic: float
    total_budgeted_cost_domestic: float
    expected_cost_domestic: float
    budgeted_margin_pct: float
    expected_margin_pct: float
    margin_pct_percentiles: dict[str, float]
    cvar_margin_pct: float
    undiversified_cvar_margin_pct: float
    diversification_benefit_pct: float
    cvar_margin_domestic: float
    probability_below_threshold: float
    vulnerability_score: int
    risk_level: RiskLevel
    net_exposures: dict[str, float]
    simulated_margin_pct: np.ndarray = field(repr=False)


def net_exposures(positions: list[PortfolioPosition]) -> dict[str, float]:
    exposures: dict[str, float] = {}
    for position in positions:
        exposures[position.foreign_currency] = (
            exposures.get(position.foreign_currency, 0.0) + position.amount_foreign
        )
    return exposures


def _correlation_factor(correlation: np.ndarray) -> np.ndarray:
    dimension = correlation.shape[0]
    jittered = correlation + settings.CORRELATION_JITTER * np.eye(dimension)
    try:
        return np.linalg.cholesky(jittered)
    except np.linalg.LinAlgError:
        eigenvalues, eigenvectors = np.linalg.eigh(jittered)
        return eigenvectors * np.sqrt(np.clip(eigenvalues, 0.0, None))


def _correlated_normals(correlation: np.ndarray, n_sims: int, seed: int | None) -> np.ndarray:
    factor = _correlation_factor(correlation)
    rng = np.random.default_rng(seed)
    independent = rng.standard_normal((n_sims, correlation.shape[0]))
    return independent @ factor.T


def simulate_portfolio(
    positions: list[PortfolioPosition],
    correlation: np.ndarray,
    currencies: list[str],
    n_sims: int,
    seed: int | None = None,
) -> PortfolioResult:
    if not positions:
        raise InvalidOrderError("The portfolio must contain at least one position.")
    if not (settings.MIN_N_SIMULATIONS <= n_sims <= settings.MAX_N_SIMULATIONS):
        raise InvalidOrderError(
            f"The number of simulations must be between {settings.MIN_N_SIMULATIONS} "
            f"and {settings.MAX_N_SIMULATIONS}."
        )
    if correlation.shape != (len(currencies), len(currencies)):
        raise InvalidOrderError("The correlation matrix does not match the provided currencies.")

    index_of = {currency: i for i, currency in enumerate(currencies)}
    shocks = _correlated_normals(correlation, n_sims, seed)

    total_revenue = float(sum(p.revenue_domestic for p in positions))
    total_budgeted_cost = 0.0
    expected_cost = 0.0
    total_cost = np.zeros(n_sims)
    undiversified_cvar_weighted = 0.0
    threshold_numerator = 0.0

    for position in positions:
        column = shocks[:, index_of[position.foreign_currency]]
        exponent = (position.drift_annual - 0.5 * position.sigma_annual**2) * position.horizon_years
        exponent = exponent + position.sigma_annual * np.sqrt(position.horizon_years) * column
        np.clip(
            exponent,
            -settings.MAX_LOG_GROWTH_EXPONENT,
            settings.MAX_LOG_GROWTH_EXPONENT,
            out=exponent,
        )
        rate = position.spot * np.exp(exponent)
        cost = position.amount_foreign * rate
        total_cost += cost

        total_budgeted_cost += position.amount_foreign * position.spot
        expected_cost += (
            position.amount_foreign
            * position.spot
            * float(np.exp(position.drift_annual * position.horizon_years))
        )
        standalone_margin = 1.0 - cost / position.revenue_domestic
        weight = position.revenue_domestic / total_revenue
        undiversified_cvar_weighted += weight * conditional_value_at_risk(standalone_margin)
        threshold_numerator += position.min_acceptable_margin_pct * position.revenue_domestic

    margin_domestic = total_revenue - total_cost
    margin_pct = margin_domestic / total_revenue
    aggregate_threshold = threshold_numerator / total_revenue

    budgeted_margin_pct = (total_revenue - total_budgeted_cost) / total_revenue
    portfolio_cvar = conditional_value_at_risk(margin_pct)
    probability_below = probability_below_threshold(margin_pct, aggregate_threshold)
    score = vulnerability_score(probability_below, budgeted_margin_pct, portfolio_cvar)

    return PortfolioResult(
        total_revenue_domestic=total_revenue,
        total_budgeted_cost_domestic=total_budgeted_cost,
        expected_cost_domestic=expected_cost,
        budgeted_margin_pct=budgeted_margin_pct,
        expected_margin_pct=float(margin_pct.mean()),
        margin_pct_percentiles=percentiles(margin_pct),
        cvar_margin_pct=portfolio_cvar,
        undiversified_cvar_margin_pct=undiversified_cvar_weighted,
        diversification_benefit_pct=portfolio_cvar - undiversified_cvar_weighted,
        cvar_margin_domestic=conditional_value_at_risk(margin_domestic),
        probability_below_threshold=probability_below,
        vulnerability_score=score,
        risk_level=RiskLevel.from_score(score),
        net_exposures=net_exposures(positions),
        simulated_margin_pct=margin_pct,
    )
