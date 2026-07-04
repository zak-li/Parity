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
from core.models.exceptions import RateLimitError
from db.memory import InMemorySimulationRepository

ORDER_DATE = dt.date(2026, 1, 15)


def _series(end_date: dt.date, n_days: int = 700, sigma: float = 0.12, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(end_date), periods=n_days)
    log_returns = rng.normal(0, sigma / np.sqrt(252), n_days)
    log_returns[0] = 0.0
    return pd.Series(10.0 * np.exp(np.cumsum(log_returns)), index=dates, dtype="float64")


@pytest.fixture
def repository():
    return InMemorySimulationRepository()


@pytest.fixture
def client(repository):
    app = create_app()
    provider = StaticFxDataProvider(_series(ORDER_DATE))
    app.dependency_overrides[get_fx_provider] = lambda: provider
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_narrator] = lambda: NullNarrator()
    with TestClient(app) as test_client:
        yield test_client


def _order_payload(**overrides):
    payload = {
        "amount_foreign": 100_000.0,
        "foreign_currency": "USD",
        "domestic_currency": "MAD",
        "order_date": ORDER_DATE.isoformat(),
        "delivery_date": (ORDER_DATE + dt.timedelta(days=90)).isoformat(),
        "target_margin_pct": 0.15,
        "domestic_rate": 0.03,
        "foreign_rate": 0.05,
        "n_simulations": 5_000,
        "seed": 7,
    }
    payload.update(overrides)
    return payload


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_main_entrypoint_exposes_app():
    from api.main import app

    assert app.title == "Parity API"


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_simulation_returns_full_analysis(client):
    response = client.post("/api/v1/simulations", json={"order": _order_payload()})
    assert response.status_code == 200
    body = response.json()

    assert 0 <= body["vulnerability_score"] <= 100
    assert body["risk_level"] in ("Faible", "Modéré", "Élevé", "Critique")
    assert body["expected_terminal_rate"] < body["spot_rate_order_date"]
    assert len(body["instruments"]) == 4
    assert 0.0 <= body["hedge"]["optimal_hedge_ratio"] <= 1.0
    assert body["compliance"]["applicable"] is True
    assert "Office des Changes" in body["recommendation"]
    assert isinstance(body["alerts"], list)


def test_simulation_is_deterministic_with_seed(client):
    payload = {"order": _order_payload()}
    first = client.post("/api/v1/simulations", json=payload).json()
    second = client.post("/api/v1/simulations", json=payload).json()
    assert first["vulnerability_score"] == second["vulnerability_score"]
    assert first["margin_pct_percentiles"] == second["margin_pct_percentiles"]


def test_simulation_with_advanced_options(client):
    payload = {
        "order": _order_payload(),
        "options": {
            "volatility_model": "ewma",
            "return_distribution": "student_t",
            "student_t_dof": 4.0,
            "jumps": {"intensity_annual": 2.0, "mean_log_jump": -0.03, "std_log_jump": 0.05},
        },
    }
    response = client.post("/api/v1/simulations", json=payload)
    assert response.status_code == 200


def test_simulation_rejects_unknown_fields(client):
    response = client.post("/api/v1/simulations", json={"order": _order_payload(hacker_field="x")})
    assert response.status_code == 422


def test_simulation_rejects_simulations_above_api_cap(client):
    response = client.post(
        "/api/v1/simulations", json={"order": _order_payload(n_simulations=1_000_000)}
    )
    assert response.status_code == 422


def test_simulation_rejects_missing_revenue_and_margin(client):
    payload = _order_payload()
    del payload["target_margin_pct"]
    response = client.post("/api/v1/simulations", json={"order": payload})
    assert response.status_code == 422


def test_domain_validation_error_maps_to_422(client):
    payload = _order_payload(delivery_date=ORDER_DATE.isoformat())
    response = client.post("/api/v1/simulations", json={"order": payload})
    assert response.status_code == 422


def test_rate_limit_error_maps_to_429(client):
    class ThrottledProvider:
        def get_historical_series(self, *args, **kwargs):
            raise RateLimitError("limite atteinte")

    app = create_app()
    app.dependency_overrides[get_fx_provider] = lambda: ThrottledProvider()
    with TestClient(app) as throttled_client:
        response = throttled_client.post("/api/v1/simulations", json={"order": _order_payload()})
    assert response.status_code == 429


def test_stress_test_endpoint(client):
    response = client.post("/api/v1/stress-tests", json={"order": _order_payload()})
    assert response.status_code == 200
    body = response.json()
    assert body["spot"] > 0
    assert len(body["scenarios"]) >= 4
    assert body["reverse_stress"]["required_rate_move_pct"] > 0


def test_compliance_endpoint_mad_applicable(client):
    response = client.post("/api/v1/compliance", json=_order_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is True
    assert len(body["required_documents"]) >= 1


def test_compliance_endpoint_eur_not_applicable(client):
    response = client.post("/api/v1/compliance", json=_order_payload(domestic_currency="EUR"))
    assert response.status_code == 200
    assert response.json()["applicable"] is False


def test_portfolio_endpoint(client):
    payload = {
        "orders": [_order_payload(), _order_payload(amount_foreign=50_000.0)],
        "seed": 3,
    }
    response = client.post("/api/v1/portfolio/simulations", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["net_exposures"]["USD"] == pytest.approx(150_000.0)
    assert 0 <= body["vulnerability_score"] <= 100


def test_portfolio_rejects_empty_orders(client):
    response = client.post("/api/v1/portfolio/simulations", json={"orders": []})
    assert response.status_code == 422


def test_backtest_endpoint(client):
    payload = {
        "foreign_currency": "USD",
        "domestic_currency": "MAD",
        "alpha": 0.05,
        "window": 250,
        "lookback_days": 1000,
    }
    response = client.post("/api/v1/backtests/var", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["n_observations"] > 0
    assert 0.0 <= body["observed_exceedance_rate"] <= 1.0


def test_api_key_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "secret-key")

    denied = client.post("/api/v1/simulations", json={"order": _order_payload()})
    assert denied.status_code == 401

    wrong = client.post(
        "/api/v1/simulations",
        json={"order": _order_payload()},
        headers={"X-API-Key": "wrong"},
    )
    assert wrong.status_code == 401

    granted = client.post(
        "/api/v1/simulations",
        json={"order": _order_payload()},
        headers={"X-API-Key": "secret-key"},
    )
    assert granted.status_code == 200


def test_health_does_not_require_api_key(client, monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "secret-key")
    assert client.get("/health").status_code == 200


def test_simulation_persists_and_returns_record_id(client, repository):
    response = client.post("/api/v1/simulations", json={"order": _order_payload()})
    record_id = response.json()["record_id"]
    assert record_id is not None
    assert repository.get(record_id) is not None


def test_simulation_can_skip_persistence(client, repository):
    payload = {"order": _order_payload(), "persist": False}
    response = client.post("/api/v1/simulations", json=payload)
    assert response.json()["record_id"] is None
    assert repository.history() == []


def test_inter_run_change_alerts_detected(client):
    calm = _order_payload(seed=1)
    first = client.post("/api/v1/simulations", json={"order": calm})
    assert first.json()["change_alerts"] == []

    risky = _order_payload(
        seed=1, foreign_rate=0.30, min_acceptable_margin_pct=0.10, target_margin_pct=0.05
    )
    second = client.post("/api/v1/simulations", json={"order": risky})
    codes = {alert["code"] for alert in second.json()["change_alerts"]}
    assert codes  # au moins une alerte de variation entre les deux runs


def test_history_endpoint_returns_saved_runs(client):
    client.post("/api/v1/simulations", json={"order": _order_payload()})
    client.post("/api/v1/simulations", json={"order": _order_payload(amount_foreign=50_000.0)})

    response = client.get("/api/v1/simulations/history", params={"foreign_currency": "USD"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["foreign_currency"] == "USD"


def test_get_single_record(client):
    created = client.post("/api/v1/simulations", json={"order": _order_payload()}).json()
    response = client.get(f"/api/v1/simulations/{created['record_id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["record_id"]


def test_get_unknown_record_returns_404(client):
    assert client.get("/api/v1/simulations/does-not-exist").status_code == 404


def test_narrative_included_when_requested(client):
    class StubNarrator:
        def narrate(self, result):
            return "Analyse: risque maîtrisé, couverture conseillée."

    app = create_app()
    provider = StaticFxDataProvider(_series(ORDER_DATE))
    app.dependency_overrides[get_fx_provider] = lambda: provider
    app.dependency_overrides[get_repository] = lambda: InMemorySimulationRepository()
    app.dependency_overrides[get_narrator] = lambda: StubNarrator()
    with TestClient(app) as narrated_client:
        response = narrated_client.post(
            "/api/v1/simulations", json={"order": _order_payload(), "narrative": True}
        )
    assert response.json()["narrative"].startswith("Analyse")


def test_exposure_endpoint_returns_list(client):
    assert client.get("/api/v1/exposure").json() == []
