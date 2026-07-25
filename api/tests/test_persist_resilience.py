from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ai.groq_narrator import NullNarrator
from api import create_app
from api.dependencies import get_fx_provider, get_narrator, get_repository
from core.io.fx.static import StaticFxDataProvider
from db.records import SimulationRecord

ORDER_DATE = dt.date(2026, 1, 15)


def _series(end_date: dt.date, n_days: int = 700, sigma: float = 0.12, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(end_date), periods=n_days)
    log_returns = rng.normal(0, sigma / np.sqrt(252), n_days)
    log_returns[0] = 0.0
    return pd.Series(10.0 * np.exp(np.cumsum(log_returns)), index=dates, dtype="float64")


class _FailingRepo:
    """A repository whose reads/writes raise, simulating a down database."""

    def save(self, record: SimulationRecord) -> SimulationRecord:
        raise RuntimeError("database is down")

    def get(self, record_id: str, client_id: str | None = None) -> SimulationRecord | None:
        return None

    def latest_for_pair(self, foreign, domestic, client_id=None):
        raise RuntimeError("database is down")

    def history(self, foreign=None, domestic=None, limit=50, client_id=None):
        return []

    def close(self) -> None:
        return None


_ORDER = {
    "order": {
        "amount_foreign": 100000,
        "foreign_currency": "USD",
        "domestic_currency": "EUR",
        "order_date": ORDER_DATE.isoformat(),
        "delivery_date": (ORDER_DATE + dt.timedelta(days=90)).isoformat(),
        "target_margin_pct": 0.15,
        "n_simulations": 2000,
    },
    "persist": True,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "")
    monkeypatch.delenv("XI_DB_STRICT", raising=False)
    app = create_app()
    app.dependency_overrides[get_fx_provider] = lambda: StaticFxDataProvider(_series(ORDER_DATE))
    app.dependency_overrides[get_repository] = lambda: _FailingRepo()
    app.dependency_overrides[get_narrator] = lambda: NullNarrator()
    with TestClient(app) as c:
        yield c


def test_persist_failure_does_not_break_the_result(client):
    # A down database must not fail the computed simulation; the result comes
    # back with record_id = null instead of a 500.
    response = client.post("/api/v1/simulations", json=_ORDER)
    assert response.status_code == 200
    body = response.json()
    assert body["record_id"] is None
    assert body["vulnerability_score"] >= 0  # the real engine result is still present


def test_strict_persistence_propagates_the_error(client, monkeypatch):
    monkeypatch.setenv("XI_DB_STRICT", "1")
    # In strict mode the save error is not swallowed; TestClient re-raises it.
    with pytest.raises(RuntimeError):
        client.post("/api/v1/simulations", json=_ORDER)
