from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import create_app


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/api/v1/simulations",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )


def test_cors_allows_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XI_CORS_ALLOW_ORIGINS", "http://localhost:4200, http://example.test")
    client = TestClient(create_app())

    response = _preflight(client, "http://localhost:4200")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_cors_rejects_unlisted_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XI_CORS_ALLOW_ORIGINS", "http://localhost:4200")
    client = TestClient(create_app())

    response = _preflight(client, "http://evil.test")

    assert "access-control-allow-origin" not in response.headers


def test_cors_disabled_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Empty (or unset) disables CORS. Set empty explicitly so a local .env with
    # a value doesn't leak in via dotenv (CI has no .env; the result is the same).
    monkeypatch.setenv("XI_CORS_ALLOW_ORIGINS", "")
    client = TestClient(create_app())

    response = _preflight(client, "http://localhost:4200")

    assert "access-control-allow-origin" not in response.headers
