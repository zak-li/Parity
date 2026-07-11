from __future__ import annotations

import datetime as dt
import logging
import os
import secrets
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from ai import Narrator, build_narrator
from api.auth0_auth import Auth0Authenticator
from api.security import hash_api_key
from core.config import load_runtime_config
from core.io.fx import FrankfurterFxDataProvider, FxDataProvider
from core.models.exceptions import SecurityError
from db import (
    AuthRepository,
    JobRepository,
    SimulationRepository,
    build_auth_repository,
    build_job_repository,
    build_repository,
)
from db.records import ApiKeyRecord

logger = logging.getLogger(__name__)

_API_KEY_ENV = "XI_API_KEY"
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_auth = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_auth0_authenticator() -> Auth0Authenticator:
    return Auth0Authenticator(load_runtime_config())


@lru_cache(maxsize=1)
def get_auth_repository() -> AuthRepository:
    return build_auth_repository()


@lru_cache(maxsize=1)
def get_job_repository() -> JobRepository:
    return build_job_repository()


@lru_cache(maxsize=1)
def get_fx_provider() -> FxDataProvider:
    config = load_runtime_config()
    cache = None
    rate_limiter = None

    redis_url = os.environ.get("XI_REDIS_URL")
    if redis_url:
        try:
            from redis import Redis

            from core.io.redis_cache import RedisTTLCache
            from core.io.redis_rate_limiter import RedisTokenBucketRateLimiter

            r = Redis.from_url(redis_url)
            cache = RedisTTLCache(r, "fx:cache", config.cache_ttl_seconds)
            rate_limiter = RedisTokenBucketRateLimiter(
                r, "fx:rl", config.rate_limit_per_second, config.rate_limit_burst
            )
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s); falling back to in-process cache and rate limiter.", exc
            )
            cache = None
            rate_limiter = None

    return FrankfurterFxDataProvider(cache=cache, rate_limiter=rate_limiter)


@lru_cache(maxsize=1)
def get_repository() -> SimulationRepository:
    return build_repository()


@lru_cache(maxsize=1)
def get_narrator() -> Narrator:
    return build_narrator()


def require_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_auth),
    repo: AuthRepository = Depends(get_auth_repository),
    auth0_auth: Auth0Authenticator = Depends(get_auth0_authenticator),
) -> ApiKeyRecord | None:
    expected = os.environ.get(_API_KEY_ENV)

    # 1. Auth0 Bearer Auth (if enabled and provided)
    if bearer and auth0_auth.is_enabled():
        try:
            payload = auth0_auth.verify_token(bearer.credentials)
            # Use 'sub' or 'uid' as client_id from Auth0
            client_id = payload.get("sub", "auth0_user")
            request.state.client_id = client_id

            # Return a virtual ApiKeyRecord so the rest of the app doesn't break
            return ApiKeyRecord(
                id=f"auth0_{client_id}",
                client_id=client_id,
                prefix="auth0",
                hashed_key="",
                created_at=dt.datetime.now(dt.UTC),
            )
        except SecurityError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # 2. API Key Auth
    if expected and api_key and secrets.compare_digest(api_key, expected):
        request.state.client_id = "master"
        return ApiKeyRecord(
            id="master",
            client_id="master",
            prefix="mast",
            hashed_key="",
            created_at=dt.datetime.now(dt.UTC),
        )

    if not expected and not api_key:
        return None

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key or Auth0 Bearer token.",
        )

    key_record = repo.get_api_key(hash_api_key(api_key))

    if not key_record or key_record.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    if key_record.expires_at and key_record.expires_at < dt.datetime.now(dt.UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired.",
        )

    request.state.client_id = key_record.client_id
    return key_record
