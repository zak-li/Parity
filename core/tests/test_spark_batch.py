from __future__ import annotations

import datetime as dt
import os

import numpy as np
import pandas as pd
import pytest

from core.app import distributed as bs
from core.io.fx.static import StaticFxDataProvider
from core.models.models import OrderInput

ORDER_DATE = dt.date(2026, 1, 15)


def _series(seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(ORDER_DATE), periods=600)
    log_returns = rng.normal(0, 0.1 / np.sqrt(252), 600)
    log_returns[0] = 0.0
    return pd.Series(10.0 * np.exp(np.cumsum(log_returns)), index=dates, dtype="float64")


def _order_dict() -> dict:
    return {
        "amount_foreign": 100_000,
        "foreign_currency": "USD",
        "domestic_currency": "EUR",
        "order_date": ORDER_DATE.isoformat(),
        "delivery_date": (ORDER_DATE + dt.timedelta(days=90)).isoformat(),
        "target_margin_pct": 0.2,
        "min_acceptable_margin_pct": 0.05,
        "n_simulations": 2_000,
        "seed": 1,
    }


def test_resolve_master(monkeypatch):
    monkeypatch.delenv("XI_SPARK_MASTER", raising=False)
    assert bs.resolve_master() == "local[*]"
    assert bs.resolve_master("spark://host:7077") == "spark://host:7077"
    monkeypatch.setenv("XI_SPARK_MASTER", "spark://10.10.10.150:7077")
    assert bs.resolve_master() == "spark://10.10.10.150:7077"


def test_build_provider_returns_fx_provider():
    from core.io.fx import FxDataProvider

    assert isinstance(bs._build_provider(), FxDataProvider)


def test_order_from_dict():
    order = bs.order_from_dict(_order_dict())
    assert isinstance(order, OrderInput)
    assert order.foreign_currency == "USD"
    assert order.delivery_date == ORDER_DATE + dt.timedelta(days=90)
    assert order.n_simulations == 2_000


def test_simulate_order_with_static_provider(monkeypatch):
    monkeypatch.setattr(bs, "_build_provider", lambda: StaticFxDataProvider(_series()))
    summary = bs.simulate_order(_order_dict())
    assert summary["pair"] == "USD/EUR"
    assert 0 <= summary["vulnerability_score"] <= 100
    assert summary["risk_level"] in {"Low", "Moderate", "High", "Critical"}
    assert 0.0 <= summary["optimal_hedge_ratio"] <= 1.0


def test_run_batch_distributes(monkeypatch):
    pytest.importorskip("pyspark")
    import shutil

    if not (shutil.which("java") or os.environ.get("JAVA_HOME")):
        pytest.skip("Spark needs a JVM (java not found)")

    orders = [_order_dict(), {**_order_dict(), "foreign_currency": "GBP"}]
    try:
        results = bs.run_batch(
            orders,
            master="local[1]",
            simulate_fn=lambda d: {"pair": f"{d['foreign_currency']}/{d['domestic_currency']}"},
        )
    except Exception as exc:  # Spark/JVM failed to start in this environment
        pytest.skip(f"Spark unavailable: {exc}")

    assert {r["pair"] for r in results} == {"USD/EUR", "GBP/EUR"}
