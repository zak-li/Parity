from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from ..config import settings
from .rates import forward_points
from .scoring import conditional_value_at_risk


@dataclass(frozen=True, slots=True)
class HedgeAnalysis:
    theoretical_forward_rate: float
    forward_points: float
    hedged_margin_domestic: float
    hedged_margin_pct: float
    unhedged_expected_margin_pct: float
    unhedged_cvar_margin_pct: float
    probability_unhedged_beats_hedge: float
    optimal_hedge_ratio: float
    optimal_hedge_cvar_margin_pct: float
    cvar_improvement_pct: float


def optimal_hedge_ratio(
    unhedged_margin_pct: np.ndarray,
    marginal_hedge_effect: np.ndarray,
    alpha: float = settings.EXPECTED_SHORTFALL_ALPHA,
    grid_step: float = settings.HEDGE_RATIO_GRID_STEP,
) -> tuple[float, float]:
    def cvar_at(ratio: float) -> float:
        return conditional_value_at_risk(
            unhedged_margin_pct + ratio * marginal_hedge_effect, alpha
        )

    grid = np.arange(0.0, 1.0 + 1e-9, grid_step)
    coarse = [cvar_at(float(r)) for r in grid]
    best_index = int(np.argmax(coarse))
    best_ratio, best_cvar = float(grid[best_index]), coarse[best_index]

    lower = float(grid[max(best_index - 1, 0)])
    upper = float(grid[min(best_index + 1, grid.size - 1)])
    if upper > lower:
        refined = minimize_scalar(
            lambda r: -cvar_at(r),
            bounds=(lower, upper),
            method="bounded",
            options={"xatol": 1e-4},
        )
        if refined.success and -refined.fun > best_cvar:
            best_ratio, best_cvar = float(refined.x), float(-refined.fun)
    return best_ratio, best_cvar


def evaluate_hedge(
    revenue: float,
    amount_foreign: float,
    forward_rate: float,
    simulated_rates: np.ndarray,
    simulated_margin_pct: np.ndarray,
    alpha: float = settings.EXPECTED_SHORTFALL_ALPHA,
    grid_step: float = settings.HEDGE_RATIO_GRID_STEP,
    spot_rate: float | None = None,
) -> HedgeAnalysis:
    hedged_margin_domestic = revenue - amount_foreign * forward_rate
    hedged_margin_pct = hedged_margin_domestic / revenue

    probability_unhedged_better = float(np.mean(simulated_rates < forward_rate))
    unhedged_expected = float(simulated_margin_pct.mean())
    unhedged_cvar = conditional_value_at_risk(simulated_margin_pct, alpha)

    marginal_hedge_effect = (amount_foreign / revenue) * (simulated_rates - forward_rate)
    ratio, cvar_optimal = optimal_hedge_ratio(
        simulated_margin_pct, marginal_hedge_effect, alpha, grid_step
    )

    reference_spot = spot_rate if spot_rate is not None else forward_rate
    return HedgeAnalysis(
        theoretical_forward_rate=forward_rate,
        forward_points=forward_points(reference_spot, forward_rate),
        hedged_margin_domestic=hedged_margin_domestic,
        hedged_margin_pct=hedged_margin_pct,
        unhedged_expected_margin_pct=unhedged_expected,
        unhedged_cvar_margin_pct=unhedged_cvar,
        probability_unhedged_beats_hedge=probability_unhedged_better,
        optimal_hedge_ratio=ratio,
        optimal_hedge_cvar_margin_pct=cvar_optimal,
        cvar_improvement_pct=cvar_optimal - unhedged_cvar,
    )
