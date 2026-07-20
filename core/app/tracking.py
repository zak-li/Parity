"""MLflow experiment tracking — an engine capability.

Any engine run that yields a :class:`SimulationResult` can be logged as an
MLflow run (order/engine parameters + risk metrics) for comparison and audit.
Optional and import-guarded: active only when ``XI_MLFLOW_TRACKING_URI`` is set
and the ``[mlflow]`` extra is installed. Tracking never affects a simulation.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

from core.models.models import SimulationResult

logger = logging.getLogger(__name__)

DEFAULT_EXPERIMENT = "parity-simulations"


class SimulationTracker(Protocol):
    def track(self, result: SimulationResult) -> str | None: ...


class NullTracker:
    """No-op tracker used when MLflow is not configured."""

    def track(self, result: SimulationResult) -> str | None:
        return None


def _params(result: SimulationResult) -> dict[str, object]:
    order = result.order
    return {
        "foreign_currency": order.foreign_currency,
        "domestic_currency": order.domestic_currency,
        "amount_foreign": order.amount_foreign,
        "order_date": str(order.order_date),
        "delivery_date": str(order.delivery_date),
        "horizon_days": result.horizon_days,
        "n_simulations": order.n_simulations,
        "lookback_days": order.lookback_days,
        "domestic_rate": order.domestic_rate,
        "foreign_rate": order.foreign_rate,
        "target_margin_pct": order.target_margin_pct,
        "min_acceptable_margin_pct": order.min_acceptable_margin_pct,
    }


def _metrics(result: SimulationResult) -> dict[str, float]:
    metrics = {
        "vulnerability_score": float(result.vulnerability_score),
        "annualized_volatility": result.annualized_volatility,
        "spot_rate": result.spot_rate_order_date,
        "expected_terminal_rate": result.expected_terminal_rate,
        "breakeven_rate": result.breakeven_rate,
        "budgeted_margin_pct": result.budgeted_margin_pct,
        "probability_margin_below_threshold": result.probability_margin_below_threshold,
        "expected_shortfall_margin_pct": result.expected_shortfall_margin_pct,
        "standard_error_margin_pct": result.standard_error_margin_pct,
        "optimal_hedge_ratio": result.hedge.optimal_hedge_ratio,
        "hedged_margin_pct": result.hedge.hedged_margin_pct,
        "cvar_improvement_pct": result.hedge.cvar_improvement_pct,
    }
    for pct, value in result.margin_pct_percentiles.items():
        metrics[f"margin_pct_p{pct}"] = value
    return metrics


class MlflowTracker:  # pragma: no cover - requires the optional mlflow extra
    def __init__(self, tracking_uri: str, experiment: str = DEFAULT_EXPERIMENT) -> None:
        import mlflow

        self._mlflow = mlflow
        # set_tracking_uri is local (no network); the experiment is resolved
        # lazily in track() so constructing the tracker never contacts the
        # server (track() runs in a background task, so it can't block a request).
        mlflow.set_tracking_uri(tracking_uri)
        self._experiment = experiment
        self._experiment_ready = False

    def track(self, result: SimulationResult) -> str | None:
        try:
            if not self._experiment_ready:
                self._mlflow.set_experiment(self._experiment)
                self._experiment_ready = True
            order = result.order
            run_name = f"{order.foreign_currency}{order.domestic_currency}-{order.order_date}"
            with self._mlflow.start_run(run_name=run_name) as run:
                self._mlflow.set_tag("risk_level", result.risk_level.value)
                self._mlflow.set_tag("pair", f"{order.foreign_currency}/{order.domestic_currency}")
                self._mlflow.log_params(_params(result))
                self._mlflow.log_metrics(_metrics(result))
                return run.info.run_id
        except Exception as exc:  # never let tracking break a simulation
            logger.warning("mlflow_track_failed", extra={"error": str(exc)})
            return None


def build_tracker() -> SimulationTracker:
    """Build the configured tracker (``XI_MLFLOW_TRACKING_URI``) or a no-op."""
    tracking_uri = os.environ.get("XI_MLFLOW_TRACKING_URI")
    if not tracking_uri:
        return NullTracker()
    experiment = os.environ.get("XI_MLFLOW_EXPERIMENT", DEFAULT_EXPERIMENT)
    try:
        return MlflowTracker(tracking_uri, experiment)
    except Exception as exc:  # mlflow missing or server unreachable
        logger.warning("mlflow_unavailable", extra={"error": str(exc)})
        return NullTracker()
