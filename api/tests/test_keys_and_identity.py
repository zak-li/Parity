from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import create_app
from api.dependencies import get_auth_repository
from api.security import generate_api_key
from db.memory import InMemoryAuthRepository


@pytest.fixture
def admin_client(monkeypatch):
    # Empty XI_API_KEY -> open dev mode, which require_admin permits. (Set empty
    # rather than delete so a local .env value can't leak back in from dotenv.)
    monkeypatch.setenv("XI_API_KEY", "")
    monkeypatch.setenv("XI_API_KEY_PEPPER", "test-pepper")
    auth_repo = InMemoryAuthRepository()
    app = create_app()
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    with TestClient(app) as client:
        yield client, auth_repo


# ---- /api/v1/me ----------------------------------------------------------


def test_me_open_mode(admin_client):
    client, _ = admin_client
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "client_id": None, "prefix": None}


def test_me_master_key(monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "master-secret")
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/me", headers={"X-API-Key": "master-secret"})
        assert response.status_code == 200
        body = response.json()
        assert body["authenticated"] is True
        assert body["client_id"] == "master"


# ---- /api/v1/keys --------------------------------------------------------


def test_create_list_revoke_key(admin_client):
    client, _ = admin_client

    created = client.post("/api/v1/keys", json={"client_id": "acme"})
    assert created.status_code == 201
    body = created.json()
    assert body["client_id"] == "acme"
    assert body["api_key"].startswith(body["prefix"])  # plaintext shown once
    key_id = body["id"]

    listed = client.get("/api/v1/keys")
    assert listed.status_code == 200
    rows = listed.json()
    assert any(k["id"] == key_id for k in rows)
    assert all("api_key" not in k for k in rows)  # secret never listed

    assert client.delete(f"/api/v1/keys/{key_id}").status_code == 204
    after = {k["id"]: k for k in client.get("/api/v1/keys").json()}
    assert after[key_id]["revoked"] is True

    assert client.delete("/api/v1/keys/does-not-exist").status_code == 404


def test_key_management_requires_admin(monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "master-secret")
    monkeypatch.setenv("XI_API_KEY_PEPPER", "test-pepper")
    auth_repo = InMemoryAuthRepository()
    app = create_app()
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo

    with TestClient(app) as client:
        plaintext, record = generate_api_key("acme")
        auth_repo.save_api_key(record)

        # A per-client key cannot manage keys.
        assert client.get("/api/v1/keys", headers={"X-API-Key": plaintext}).status_code == 403
        # The master key can.
        assert client.get("/api/v1/keys", headers={"X-API-Key": "master-secret"}).status_code == 200
