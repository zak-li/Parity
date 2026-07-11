"""Inbound request guards: per-client rate limiting, concurrency, and timeout.

The compute endpoints (``/simulations``, ``/portfolio``, ``/ladder`` …) run
CPU-bound Monte Carlo work. Without an edge guard a single caller could exhaust
the service, so this middleware applies three defence-in-depth limits:

* a **token-bucket rate limit per client** (identified by API key, else IP),
* a **concurrency cap** on simultaneous requests (asyncio semaphore),
* a **request timeout** returning ``504`` instead of hanging.

All limits are configurable via ``XI_API_*`` environment variables and default
to permissive-but-present values. A reverse proxy (nginx/Traefik) is still
recommended in production for network-level protection.
"""

from __future__ import annotations

import asyncio
import os
from collections import OrderedDict
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_504_GATEWAY_TIMEOUT,
)

from core.io.rate_limiter import TokenBucketRateLimiter

_ENV_PREFIX = "XI_API_"
_EXEMPT_PATHS = frozenset({"/health", "/metrics"})


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    return int(raw) if raw is not None else default


_DEFAULT_RATE_PER_SECOND = 25.0
_DEFAULT_BURST = 50
_DEFAULT_MAX_CONCURRENCY = 8
_DEFAULT_REQUEST_TIMEOUT = 30.0
_DEFAULT_ACQUIRE_TIMEOUT = 2.0
_DEFAULT_MAX_CLIENTS = 10_000


@dataclass(frozen=True, slots=True)
class GuardConfig:
    rate_per_second: float = _DEFAULT_RATE_PER_SECOND
    burst: int = _DEFAULT_BURST
    max_concurrency: int = _DEFAULT_MAX_CONCURRENCY
    request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT
    acquire_timeout_seconds: float = _DEFAULT_ACQUIRE_TIMEOUT
    max_clients_tracked: int = _DEFAULT_MAX_CLIENTS

    @classmethod
    def from_env(cls) -> GuardConfig:
        return cls(
            rate_per_second=_env_float("RATE_LIMIT_PER_SECOND", _DEFAULT_RATE_PER_SECOND),
            burst=_env_int("RATE_LIMIT_BURST", _DEFAULT_BURST),
            max_concurrency=_env_int("MAX_CONCURRENCY", _DEFAULT_MAX_CONCURRENCY),
            request_timeout_seconds=_env_float("REQUEST_TIMEOUT_SECONDS", _DEFAULT_REQUEST_TIMEOUT),
        )


class _ClientBuckets:
    """Bounded LRU of per-client token buckets (caps memory against key flooding)."""

    def __init__(self, config: GuardConfig) -> None:
        self._config = config
        self._buckets: OrderedDict[str, TokenBucketRateLimiter] = OrderedDict()

    def allow(self, client_id: str) -> bool:
        bucket = self._buckets.get(client_id)
        if bucket is None:
            bucket = TokenBucketRateLimiter(self._config.rate_per_second, self._config.burst)
            self._buckets[client_id] = bucket
            if len(self._buckets) > self._config.max_clients_tracked:
                self._buckets.popitem(last=False)
        else:
            self._buckets.move_to_end(client_id)
        return bucket.try_acquire()


def _client_id(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key}"
    return f"ip:{request.client.host}" if request.client else "ip:unknown"


def _json(status_code: int, detail: str, **headers: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"detail": detail}, headers=headers or None
    )


def install_request_guards(app: FastAPI, config: GuardConfig | None = None) -> None:
    config = config or GuardConfig.from_env()
    buckets = _ClientBuckets(config)
    semaphore = asyncio.Semaphore(config.max_concurrency)

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        if not buckets.allow(_client_id(request)):
            return _json(HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded.", **{"Retry-After": "1"})

        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=config.acquire_timeout_seconds)
        except TimeoutError:
            return _json(HTTP_503_SERVICE_UNAVAILABLE, "Server is busy, please retry shortly.")

        try:
            return await asyncio.wait_for(
                call_next(request), timeout=config.request_timeout_seconds
            )
        except TimeoutError:
            return _json(HTTP_504_GATEWAY_TIMEOUT, "Request timed out.")
        finally:
            semaphore.release()
