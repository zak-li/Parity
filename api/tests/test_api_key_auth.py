from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from api import create_app
from api.dependencies import get_auth_repository, get_repository
from api.security import _KEY_PREFIX, generate_api_key, hash_api_key
from db.memory import InMemoryAuthRepository, InMemorySimulationRepository


def test_hash_is_deterministic_and_pepper_dependent(monkeypatch):
    monkeypatch.setenv("XI_API_KEY_PEPPER", "pepper-one")
    h1 = hash_api_key("pk_secret")
    assert h1 == hash_api_key("pk_secret")
    monkeypatch.setenv("XI_API_KEY_PEPPER", "pepper-two")
    assert hash_api_key("pk_secret") != h1  # a different pepper changes the hash


def test_generate_api_key_shape(monkeypatch):
    monkeypatch.setenv("XI_API_KEY_PEPPER", "p")
    plaintext, record = generate_api_key("acme")
    assert plaintext.startswith(_KEY_PREFIX)
    assert record.client_id == "acme"
    assert record.prefix == plaintext[:11]
    assert record.hashed_key == hash_api_key(plaintext)
    assert record.hashed_key != plaintext  # never stored in clear


@pytest.fixture
def keyed_client(monkeypatch):
    monkeypatch.delenv("XI_API_KEY", raising=False)  # force the per-client key path
    monkeypatch.setenv("XI_API_KEY_PEPPER", "test-pepper")
    auth_repo = InMemoryAuthRepository()
    app = create_app()
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    app.dependency_overrides[get_repository] = lambda: InMemorySimulationRepository()
    with TestClient(app) as client:
        yield client, auth_repo


def test_minted_key_authorizes(keyed_client):
    client, auth_repo = keyed_client
    plaintext, record = generate_api_key("acme")
    auth_repo.save_api_key(record)
    assert client.get("/api/v1/exposure", headers={"X-API-Key": plaintext}).status_code == 200


def test_unknown_key_is_rejected(keyed_client):
    client, _ = keyed_client
    assert client.get("/api/v1/exposure", headers={"X-API-Key": "pk_bogus"}).status_code == 401


def test_revoked_key_is_rejected(keyed_client):
    client, auth_repo = keyed_client
    plaintext, record = generate_api_key("acme")
    auth_repo.save_api_key(record)
    auth_repo.revoke_api_key(record.id)
    assert client.get("/api/v1/exposure", headers={"X-API-Key": plaintext}).status_code == 401


def test_expired_key_is_rejected(keyed_client):
    client, auth_repo = keyed_client
    plaintext, record = generate_api_key(
        "acme", expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
    )
    auth_repo.save_api_key(record)
    assert client.get("/api/v1/exposure", headers={"X-API-Key": plaintext}).status_code == 401
