from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import settings
from .exceptions import InsufficientDataError, SimulationError


@dataclass(frozen=True, slots=True)
class StressScenario:
    name: str
    rate_shock_pct: float


@dataclass(frozen=True, slots=True)
class StressOutcome:
    scenario: str
    rate_shock_pct: float
    shocked_rate: float
    margin_domestic: float
    margin_pct: float
    margin_pct_change: float


@dataclass(frozen=True, slots=True)
class ReverseStressResult:
    target_margin_pct: float
    breaking_rate: float
    required_rate_move_pct: float


@dataclass(frozen=True, slots=True)
class StressReport:
    spot: float
    budgeted_margin_pct: float
    scenarios: tuple[StressOutcome, ...]
    reverse_stress: ReverseStressResult


def margin_at_rate(revenue: float, amount_foreign: float, rate: float) -> tuple[float, float]:
    if revenue <= 0:
        raise SimulationError("Revenue must be strictly positive.")
    margin_domestic = revenue - amount_foreign * rate
    return margin_domestic, margin_domestic / revenue


def apply_scenarios(
    revenue: float,
    amount_foreign: float,
    spot: float,
    budgeted_margin_pct: float,
    scenarios: tuple[StressScenario, ...],
) -> tuple[StressOutcome, ...]:
    outcomes = []
    for scenario in scenarios:
        shocked_rate = spot * (1.0 + scenario.rate_shock_pct)
        margin_domestic, margin_pct = margin_at_rate(revenue, amount_foreign, shocked_rate)
        outcomes.append(
            StressOutcome(
                scenario=scenario.name,
                rate_shock_pct=scenario.rate_shock_pct,
                shocked_rate=shocked_rate,
                margin_domestic=margin_domestic,
                margin_pct=margin_pct,
                margin_pct_change=margin_pct - budgeted_margin_pct,
            )
        )
    return tuple(outcomes)


def reverse_stress_test(
    revenue: float, amount_foreign: float, spot: float, target_margin_pct: float = 0.0
) -> ReverseStressResult:
    if spot <= 0 or amount_foreign <= 0 or revenue <= 0:
        raise SimulationError("Parameters must be strictly positive.")
    breaking_rate = revenue * (1.0 - target_margin_pct) / amount_foreign
    return ReverseStressResult(
        target_margin_pct=target_margin_pct,
        breaking_rate=breaking_rate,
        required_rate_move_pct=breaking_rate / spot - 1.0,
    )


def worst_adverse_move(series: pd.Series, horizon_days: int) -> float:
    values = series.to_numpy()
    horizon = max(1, int(horizon_days))
    if values.size <= horizon:
        raise InsufficientDataError("Insufficient history for the requested horizon.")
    ratios = values[horizon:] / values[:-horizon]
    return float(np.max(ratios) - 1.0)


def historical_stress_scenario(series: pd.Series, horizon_days: int, name: str) -> StressScenario:
    return StressScenario(name=name, rate_shock_pct=worst_adverse_move(series, horizon_days))


def canonical_scenarios() -> tuple[StressScenario, ...]:
    return tuple(StressScenario(name, shock) for name, shock in settings.CANONICAL_STRESS_SHOCKS)
