from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ai.groq_narrator import NullNarrator
from api import create_app
from api.dependencies import (
    get_auth_repository,
    get_fx_provider,
    get_narrator,
    get_repository,
)
from api.security import generate_api_key
from core.io.fx.static import StaticFxDataProvider
from db.memory import InMemoryAuthRepository, InMemorySimulationRepository

ORDER_DATE = dt.date(2026, 1, 15)


def _series(end_date: dt.date, n_days: int = 700, sigma: float = 0.12, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(end_date), periods=n_days)
    log_returns = rng.normal(0, sigma / np.sqrt(252), n_days)
    log_returns[0] = 0.0
    return pd.Series(10.0 * np.exp(np.cumsum(log_returns)), index=dates, dtype="float64")


@pytest.fixture
def tenant_client(monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "")  # per-client key path; no master
    monkeypatch.setenv("XI_API_KEY_PEPPER", "test-pepper")
    auth_repo = InMemoryAuthRepository()
    sim_repo = InMemorySimulationRepository()
    app = create_app()
    app.dependency_overrides[get_fx_provider] = lambda: StaticFxDataProvider(_series(ORDER_DATE))
    app.dependency_overrides[get_repository] = lambda: sim_repo
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    app.dependency_overrides[get_narrator] = lambda: NullNarrator()
    with TestClient(app) as client:
        yield client, auth_repo


def _key(auth_repo, client_id: str) -> str:
    plaintext, record = generate_api_key(client_id)
    auth_repo.save_api_key(record)
    return plaintext


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


def test_history_and_record_are_isolated_per_tenant(tenant_client):
    client, auth_repo = tenant_client
    key_a = _key(auth_repo, "acme")
    key_b = _key(auth_repo, "globex")

    created = client.post("/api/v1/simulations", json=_ORDER, headers={"X-API-Key": key_a})
    assert created.status_code == 200
    record_id = created.json()["record_id"]
    assert record_id is not None

    # Owner sees the run.
    hist_a = client.get("/api/v1/simulations/history", headers={"X-API-Key": key_a}).json()
    assert any(r["id"] == record_id for r in hist_a)
    assert (
        client.get(f"/api/v1/simulations/{record_id}", headers={"X-API-Key": key_a}).status_code
        == 200
    )

    # A different tenant sees nothing and cannot read the record.
    hist_b = client.get("/api/v1/simulations/history", headers={"X-API-Key": key_b}).json()
    assert hist_b == []
    assert (
        client.get(f"/api/v1/simulations/{record_id}", headers={"X-API-Key": key_b}).status_code
        == 404
    )
