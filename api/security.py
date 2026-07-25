"""API-key hashing and minting.

API keys are high-entropy random tokens, so a **fast keyed hash** (HMAC-SHA256
with a secret pepper) is both sufficient and correct — unlike a slow per-request
password KDF, which needlessly burns CPU on every call, and unlike a hard-coded
public salt, which lets a leaked key table be brute-forced offline. The hash is
deterministic so the store can index by it.

The pepper is read from ``XI_API_KEY_PEPPER``; set it in production.
"""

from __future__ import annotations

import datetime as dt
import hmac
import logging
import os
import secrets
from hashlib import sha256

from core.models.exceptions import SecurityError
from db.records import ApiKeyRecord

logger = logging.getLogger(__name__)

_PEPPER_ENV = "XI_API_KEY_PEPPER"
_DEV_PEPPER = b"parity-insecure-development-pepper"
_KEY_PREFIX = "pk_"
_PREFIX_LEN = 11  # "pk_" + 8 chars, safe to store/display in clear


def _pepper() -> bytes:
    raw = os.environ.get(_PEPPER_ENV)
    if raw:
        return raw.encode()
    # Fail closed in production: a missing pepper makes the key table brute-forceable.
    if os.environ.get("XI_ENV", "development").strip().lower() == "production":
        raise SecurityError(
            f"{_PEPPER_ENV} must be set when XI_ENV=production (API keys cannot be hashed securely)."
        )
    logger.warning(
        "%s is not set; using an insecure development pepper. Set it in production.", _PEPPER_ENV
    )
    return _DEV_PEPPER


def hash_api_key(key: str) -> str:
    """Deterministic keyed hash of an API key for storage and lookup."""
    return hmac.new(_pepper(), key.encode(), sha256).hexdigest()


def generate_api_key(
    client_id: str, expires_at: dt.datetime | None = None
) -> tuple[str, ApiKeyRecord]:
    """Mint a new API key. Returns ``(plaintext, record)``; the plaintext is
    shown to the caller once and only its hash is persisted."""
    plaintext = _KEY_PREFIX + secrets.token_urlsafe(32)
    record = ApiKeyRecord(
        id=secrets.token_hex(8),
        client_id=client_id,
        prefix=plaintext[:_PREFIX_LEN],
        hashed_key=hash_api_key(plaintext),
        created_at=dt.datetime.now(dt.UTC),
        expires_at=expires_at,
    )
    return plaintext, record
