from __future__ import annotations

import numpy as np

from ..config import settings


def percentiles(
    values: np.ndarray, points: tuple[int, ...] = settings.PERCENTILE_POINTS
) -> dict[str, float]:
    computed = np.percentile(values, points)
    return {f"P{p}": float(v) for p, v in zip(points, np.atleast_1d(computed), strict=False)}


def probability_below_threshold(values: np.ndarray, threshold: float) -> float:
    return float(np.mean(values < threshold))


def conditional_value_at_risk(
    values: np.ndarray, alpha: float = settings.EXPECTED_SHORTFALL_ALPHA
) -> float:
    """Expected Shortfall: the mean of the worst ``alpha`` fraction of ``values``.

    On a margin distribution this is the average margin in the worst ``alpha``
    tail (α = 0.05 by default) and is always <= the expected margin.
    """
    n = values.size
    if n == 0:
        raise ValueError("The value series cannot be empty.")
    k = min(n, max(1, int(np.ceil(alpha * n))))
    tail = np.partition(values, k - 1)[:k]
    return float(tail.mean())


def vulnerability_score(
    probability_below: float, budgeted_margin_pct: float, expected_shortfall_pct: float
) -> int:
    """0-100 risk score blending loss probability and tail severity.

    ``severity`` is the fraction of the budgeted margin eroded in the CVaR tail;
    the score is a weighted average of that and ``probability_below``, scaled to
    0-100 (higher = more vulnerable).
    """
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
