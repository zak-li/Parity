from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core.app.risk_engine import MarginRiskEngine
from core.app.tracking import (
    MlflowTracker,
    NullTracker,
    _metrics,
    _params,
    build_tracker,
)
from core.io.fx.static import StaticFxDataProvider
from core.models.models import OrderInput, SimulationResult

ORDER_DATE = dt.date(2026, 1, 15)


def _series(seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(ORDER_DATE), periods=600)
    log_returns = rng.normal(0, 0.1 / np.sqrt(252), 600)
    log_returns[0] = 0.0
    return pd.Series(10.0 * np.exp(np.cumsum(log_returns)), index=dates, dtype="float64")


def _result() -> SimulationResult:
    order = OrderInput(
        amount_foreign=100_000,
        foreign_currency="USD",
        domestic_currency="EUR",
        order_date=ORDER_DATE,
        delivery_date=ORDER_DATE + dt.timedelta(days=90),
        target_margin_pct=0.2,
        min_acceptable_margin_pct=0.05,
        n_simulations=2_000,
        seed=1,
    )
    engine = MarginRiskEngine(fx_provider=StaticFxDataProvider(_series()))
    return engine.run(order)


def test_null_tracker_returns_none():
    assert NullTracker().track(_result()) is None


def test_build_tracker_without_uri_is_null(monkeypatch):
    monkeypatch.delenv("XI_MLFLOW_TRACKING_URI", raising=False)
    assert isinstance(build_tracker(), NullTracker)


def test_build_tracker_with_uri_returns_tracker(monkeypatch):
    # With a URI set, build_tracker either returns MlflowTracker (extra present)
    # or falls back to NullTracker (extra missing) — never raises.
    monkeypatch.setenv("XI_MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    tracker = build_tracker()
    assert hasattr(tracker, "track")


def test_params_and_metrics_shapes():
    result = _result()
    params = _params(result)
    metrics = _metrics(result)
    assert params["foreign_currency"] == "USD"
    assert params["domestic_currency"] == "EUR"
    assert params["horizon_days"] == result.horizon_days
    assert metrics["vulnerability_score"] == float(result.vulnerability_score)
    assert 0.0 <= metrics["optimal_hedge_ratio"] <= 1.0
    assert any(k.startswith("margin_pct_p") for k in metrics)


def test_mlflow_tracker_logs_run(tmp_path, monkeypatch):
    pytest.importorskip("mlflow")
    uri = tmp_path.joinpath("mlruns").as_uri()
    monkeypatch.setenv("XI_MLFLOW_TRACKING_URI", uri)
    tracker = build_tracker()
    assert isinstance(tracker, MlflowTracker)

    run_id = tracker.track(_result())
    assert run_id

    import mlflow

    run = mlflow.get_run(run_id)
    assert run.data.metrics["vulnerability_score"] >= 0
    assert run.data.params["foreign_currency"] == "USD"
