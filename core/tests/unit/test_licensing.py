from __future__ import annotations

import datetime as dt

import pytest

import core.licensing
from core.licensing import (
    ParityLicenseError,
    get_active_api_key,
    init,
    verify_license,
)
from db.memory import InMemoryAuthRepository
from db.records import ApiKeyRecord


@pytest.fixture(autouse=True)
def reset_global_api_key():
    core.licensing._GLOBAL_API_KEY = None
    yield
    core.licensing._GLOBAL_API_KEY = None


def test_licensing_empty_init():
    with pytest.raises(ParityLicenseError, match="Invalid API key"):
        init("")
    with pytest.raises(ParityLicenseError, match="Invalid API key"):
        init("   ")


def test_licensing_active_key(monkeypatch):
    monkeypatch.setenv("PARITY_API_KEY", "test-key-123")
    assert get_active_api_key() == "test-key-123"


def test_licensing_verify_master(monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "master-secret-key")
    assert verify_license("master-secret-key") is True

    with pytest.raises(ParityLicenseError, match="Invalid API Key"):
        verify_license("wrong-key")


def test_licensing_open_dev_mode(monkeypatch):
    monkeypatch.delenv("XI_API_KEY", raising=False)
    monkeypatch.delenv("PARITY_MASTER_KEY", raising=False)
    monkeypatch.delenv("PARITY_API_KEY", raising=False)
    monkeypatch.setenv("XI_ENV", "development")
    assert verify_license(None) is True


def test_licensing_production_requires_key(monkeypatch):
    monkeypatch.delenv("XI_API_KEY", raising=False)
    monkeypatch.delenv("PARITY_MASTER_KEY", raising=False)
    monkeypatch.delenv("PARITY_API_KEY", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("XI_ENV", "production")
    with pytest.raises(ParityLicenseError, match="COMMERCIAL ACCESS RESTRICTED"):
        verify_license(None)


def test_licensing_auth_repo_validation(monkeypatch):
    from api.security import hash_api_key

    auth_repo = InMemoryAuthRepository()
    raw_key = "client-valid-key"
    hashed = hash_api_key(raw_key)

    record = ApiKeyRecord(
        id="rec-1",
        client_id="acme",
        prefix="clie",
        hashed_key=hashed,
        created_at=dt.datetime.now(dt.UTC),
    )
    auth_repo.save_api_key(record)

    monkeypatch.setattr("db.build_auth_repository", lambda: auth_repo)

    # Valid key
    assert verify_license(raw_key) is True

    # Revoked key
    auth_repo.revoke_api_key("rec-1")
    with pytest.raises(ParityLicenseError, match="revoked"):
        verify_license(raw_key)


def test_licensing_expired_key(monkeypatch):
    from api.security import hash_api_key

    auth_repo = InMemoryAuthRepository()
    raw_key = "client-expired-key"
    hashed = hash_api_key(raw_key)

    expired_record = ApiKeyRecord(
        id="rec-exp",
        client_id="acme",
        prefix="clie",
        hashed_key=hashed,
        created_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=40),
        expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=10),
    )
    auth_repo.save_api_key(expired_record)
    monkeypatch.setattr("db.build_auth_repository", lambda: auth_repo)

    with pytest.raises(ParityLicenseError, match="expired"):
        verify_license(raw_key)


def test_licensing_init_flow(monkeypatch):
    monkeypatch.setenv("XI_API_KEY", "valid-init-key")
    init("valid-init-key")
    assert get_active_api_key() == "valid-init-key"
