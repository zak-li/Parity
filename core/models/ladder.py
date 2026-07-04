"""Cashflow ladder: multi-date FX exposure and layered (per-tranche) hedging.

An importer rarely pays on a single date; payments fall due on a schedule. This
models a series of same-currency-pair tranches at different horizons, simulates
their delivery-date rates from one shared Brownian path (so longer horizons carry
the shorter ones' moves), and compares the unhedged margin against a layered
hedge that locks each tranche at its own theoretical forward.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import settings
from . import rates
from .enums import RiskLevel
from .exceptions import InvalidOrderError
from .scoring import (
    conditional_value_at_risk,
    percentiles,
    probability_below_threshold,
    vulnerability_score,
)


@dataclass(frozen=True, slots=True)
class CashflowTranche:
    label: str
    horizon_days: int
    amount_foreign: float


@dataclass(frozen=True, slots=True)
class LadderTrancheResult:
    label: str
    horizon_days: int
    amount_foreign: float
    forward_rate: float
    expected_rate: float


@dataclass(frozen=True, slots=True)
class LadderResult:
    total_amount_foreign: float
    total_revenue_domestic: float
    budgeted_margin_pct: float
    unhedged_expected_margin_pct: float
    unhedged_cvar_margin_pct: float
    layered_hedged_margin_pct: float
    cvar_improvement_pct: float
    probability_below_threshold: float
    vulnerability_score: int
    risk_level: RiskLevel
    margin_pct_percentiles: dict[str, float]
    tranches: tuple[LadderTrancheResult, ...]
    simulated_margin_pct: np.ndarray = field(repr=False)


def simulate_ladder(
    tranches: list[CashflowTranche],
    spot: float,
    sigma_annual: float,
    domestic_rate: float,
    foreign_rate: float,
    target_margin_pct: float,
    n_sims: int,
    seed: int | None = None,
    min_acceptable_margin_pct: float = 0.0,
) -> LadderResult:
    if not tranches:
        raise InvalidOrderError("The ladder must contain at least one tranche.")
    if not (settings.MIN_N_SIMULATIONS <= n_sims <= settings.MAX_N_SIMULATIONS):
        raise InvalidOrderError(
            f"The number of simulations must be between {settings.MIN_N_SIMULATIONS} "
            f"and {settings.MAX_N_SIMULATIONS}."
        )
    if spot <= 0 or sigma_annual < 0:
        raise InvalidOrderError("Spot must be positive and volatility non-negative.")

    ordered = sorted(tranches, key=lambda tranche: tranche.horizon_days)
    horizons = np.array([t.horizon_days for t in ordered], dtype=float)
    horizons_years = horizons / settings.CALENDAR_DAYS_PER_YEAR
    amounts = np.array([t.amount_foreign for t in ordered], dtype=float)

    mu = rates.cip_drift(domestic_rate, foreign_rate)

    # Shared Brownian path evaluated at each horizon: increments have variance
    # equal to the time gap, so W(t_k) correctly correlates the tranches.
    dt = np.diff(horizons_years, prepend=0.0)
    rng = np.random.default_rng(seed)
    increments = rng.standard_normal((n_sims, len(ordered))) * np.sqrt(dt)
    brownian = np.cumsum(increments, axis=1)
    exponents = (mu - 0.5 * sigma_annual**2) * horizons_years + sigma_annual * brownian
    np.clip(
        exponents,
        -settings.MAX_LOG_GROWTH_EXPONENT,
        settings.MAX_LOG_GROWTH_EXPONENT,
        out=exponents,
    )
    simulated_rates = spot * np.exp(exponents)

    revenues = amounts * spot * (1.0 + target_margin_pct)
    total_revenue = float(revenues.sum())

    simulated_cost = simulated_rates @ amounts
    margin_pct = 1.0 - simulated_cost / total_revenue

    total_budgeted_cost = float((amounts * spot).sum())
    budgeted_margin_pct = (total_revenue - total_budgeted_cost) / total_revenue

    forwards = np.array(
        [
            rates.theoretical_forward_rate(spot, domestic_rate, foreign_rate, t)
            for t in horizons_years
        ]
    )
    layered_hedged_cost = float((amounts * forwards).sum())
    layered_hedged_margin_pct = (total_revenue - layered_hedged_cost) / total_revenue

    unhedged_cvar = conditional_value_at_risk(margin_pct)
    probability_below = probability_below_threshold(margin_pct, min_acceptable_margin_pct)
    score = vulnerability_score(probability_below, budgeted_margin_pct, unhedged_cvar)

    tranche_results = tuple(
        LadderTrancheResult(
            label=tranche.label,
            horizon_days=tranche.horizon_days,
            amount_foreign=tranche.amount_foreign,
            forward_rate=float(forwards[i]),
            expected_rate=float(simulated_rates[:, i].mean()),
        )
        for i, tranche in enumerate(ordered)
    )

    return LadderResult(
        total_amount_foreign=float(amounts.sum()),
        total_revenue_domestic=total_revenue,
        budgeted_margin_pct=budgeted_margin_pct,
        unhedged_expected_margin_pct=float(margin_pct.mean()),
        unhedged_cvar_margin_pct=unhedged_cvar,
        layered_hedged_margin_pct=layered_hedged_margin_pct,
        cvar_improvement_pct=layered_hedged_margin_pct - unhedged_cvar,
        probability_below_threshold=probability_below,
        vulnerability_score=score,
        risk_level=RiskLevel.from_score(score),
        margin_pct_percentiles=percentiles(margin_pct),
        tranches=tranche_results,
        simulated_margin_pct=margin_pct,
    )
