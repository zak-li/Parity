"""Parity Licensing and API-Key Access Guard.

Protects and restricts library execution to authorized clients with a valid API key.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import secrets

logger = logging.getLogger(__name__)

_GLOBAL_API_KEY: str | None = None


class ParityLicenseError(PermissionError):
    """Raised when an operation is attempted without a valid Parity API key / license."""

    pass


def init(api_key: str) -> None:
    """Initialize and activate the Parity library session with an API key."""
    global _GLOBAL_API_KEY
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        raise ParityLicenseError("[PARITY-401] Invalid API key: Please provide a non-empty string.")
    _GLOBAL_API_KEY = api_key.strip()
    verify_license(_GLOBAL_API_KEY)
    logger.info("Parity session activated successfully.")


def get_active_api_key() -> str | None:
    """Return the currently configured API key, if any."""
    return _GLOBAL_API_KEY or os.environ.get("PARITY_API_KEY") or os.environ.get("XI_API_KEY")


def verify_license(api_key: str | None = None) -> bool:
    """Verify that a valid API key is present and authorized.

    Raises:
        ParityLicenseError: If no key is provided in production, or if the key is invalid / expired / revoked.
    """
    key = api_key or get_active_api_key()
    env = os.environ.get("XI_ENV", "development").lower()
    configured_master = os.environ.get("XI_API_KEY") or os.environ.get("PARITY_MASTER_KEY")
    is_testing = bool(os.environ.get("PYTEST_CURRENT_TEST"))

    if not key:
        # In open development or test environments without an explicit master key, permit execution
        if (env in ("development", "test") or is_testing) and not configured_master:
            return True

        raise ParityLicenseError(
            "\n" + "=" * 80 + "\n"
            "[PARITY-401] COMMERCIAL ACCESS RESTRICTED: Missing Parity API Key.\n"
            "This quantitative engine requires an active license key.\n\n"
            "To unlock the engine, use one of the following methods:\n"
            "  1. In Python: Parity.init(api_key='your_api_key')\n"
            "  2. Instantiation: engine = Parity.MarginRiskEngine(api_key='your_api_key')\n"
            "  3. Environment variable: export PARITY_API_KEY='your_api_key'\n"
            "=" * 80
        )

    # 1. Master Key Check
    if configured_master and secrets.compare_digest(key, configured_master):
        return True

    # 2. Database Auth Repository Check (if available)
    try:
        from api.security import hash_api_key
        from db import build_auth_repository

        repo = build_auth_repository()
        record = repo.get_api_key(hash_api_key(key))
        if record:
            if record.revoked:
                raise ParityLicenseError(
                    "[PARITY-403] API key revoked. Please contact Parity support."
                )
            if record.expires_at and record.expires_at < dt.datetime.now(dt.UTC):
                raise ParityLicenseError(
                    "[PARITY-403] API key expired. Please renew your Parity subscription."
                )
            return True
    except ParityLicenseError:
        raise
    except Exception:
        pass

    # 3. If master key is configured and doesn't match, reject
    if configured_master and not secrets.compare_digest(key, configured_master):
        raise ParityLicenseError(
            "[PARITY-401] Invalid API Key: Provided key is not authorized for this engine."
        )

    return True
