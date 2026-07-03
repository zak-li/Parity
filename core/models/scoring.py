from __future__ import annotations

import numpy as np

from ..config import settings


def percentiles(
    values: np.ndarray, points: tuple[int, ...] = settings.PERCENTILE_POINTS
) -> dict[str, float]:
    computed = np.percentile(values, points)
    return {f"P{p}": float(v) for p, v in zip(points, np.atleast_1d(computed))}


def probability_below_threshold(values: np.ndarray, threshold: float) -> float:
    return float(np.mean(values < threshold))


def conditional_value_at_risk(
    values: np.ndarray, alpha: float = settings.EXPECTED_SHORTFALL_ALPHA
) -> float:
    n = values.size
    if n == 0:
        raise ValueError("La série de valeurs ne peut pas être vide.")
    k = min(n, max(1, int(np.ceil(alpha * n))))
    tail = np.partition(values, k - 1)[:k]
    return float(tail.mean())


def vulnerability_score(
    probability_below: float, budgeted_margin_pct: float, expected_shortfall_pct: float
) -> int:
    if budgeted_margin_pct > 0:
        severity = (budgeted_margin_pct - expected_shortfall_pct) / budgeted_margin_pct
    else:
        severity = 1.0 if expected_shortfall_pct < budgeted_margin_pct else 0.0
    severity = min(max(severity, 0.0), 1.0)
    probability_below = min(max(probability_below, 0.0), 1.0)

    raw = (
        settings.VULNERABILITY_SCORE_PROBABILITY_WEIGHT * probability_below
        + settings.VULNERABILITY_SCORE_SEVERITY_WEIGHT * severity
    )
    return int(round(min(max(raw, 0.0), 1.0) * 100))
