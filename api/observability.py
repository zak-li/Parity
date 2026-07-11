"""Observability: request-id propagation, JSON logs, and Prometheus metrics.

* Every request gets an ``X-Request-ID`` (echoed from the caller or generated),
  bound to a context variable so all log lines carry it.
* ``configure_logging`` installs a stdlib JSON formatter (no extra dependency).
* A middleware records request count and latency; ``GET /metrics`` exposes them
  in Prometheus text format. Metric labels use the **route template** (not the
  raw path) to avoid high-cardinality series.

``/metrics`` should be network-restricted (internal scrape) in production.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import PlainTextResponse

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_COUNT = Counter(
    "parity_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "parity_request_duration_seconds", "HTTP request latency (seconds)", ["method", "path"]
)


def current_request_id() -> str:
    return _request_id.get()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None) -> None:
    """Install a JSON log formatter on the root logger (call once at startup)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level or os.environ.get("XI_LOG_LEVEL", "INFO"))


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = _request_id.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - start
            path = _route_template(request)
            REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
            REQUEST_COUNT.labels(request.method, path, str(status_code)).inc()
            _request_id.reset(token)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
