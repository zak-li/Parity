from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.guards import GuardConfig, install_request_guards


def _app(config: GuardConfig) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/work")
    def work():
        return {"done": True}

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.2)
        return {"done": True}

    install_request_guards(app, config)
    return app


def test_rate_limit_returns_429_after_burst():
    client = TestClient(_app(GuardConfig(rate_per_second=0.01, burst=2, max_concurrency=4)))
    assert client.get("/work").status_code == 200
    assert client.get("/work").status_code == 200
    third = client.get("/work")
    assert third.status_code == 429
    assert third.headers.get("Retry-After") == "1"
    assert third.headers.get("X-RateLimit-Limit") == "2"
    assert third.headers.get("X-RateLimit-Remaining") == "0"
    assert third.headers.get("X-RateLimit-Reset") == "1"


def test_health_is_exempt_from_rate_limit():
    client = TestClient(_app(GuardConfig(rate_per_second=0.01, burst=1, max_concurrency=4)))
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_distinct_api_keys_have_independent_budgets():
    client = TestClient(_app(GuardConfig(rate_per_second=0.01, burst=1, max_concurrency=4)))
    assert client.get("/work", headers={"X-API-Key": "a"}).status_code == 200
    assert client.get("/work", headers={"X-API-Key": "b"}).status_code == 200
    assert client.get("/work", headers={"X-API-Key": "a"}).status_code == 429


def test_request_timeout_returns_504():
    client = TestClient(
        _app(GuardConfig(rate_per_second=100, burst=100, request_timeout_seconds=0.05))
    )
    assert client.get("/slow").status_code == 504
