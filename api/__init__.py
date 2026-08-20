from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import core
from core.config import load_runtime_config
from core.models.exceptions import (
    FxDataError,
    InsufficientDataError,
    InvalidOrderError,
    MarginProtectorError,
    RateLimitError,
    SecurityError,
)

from .guards import install_request_guards
from .middleware import install_audit_logging
from .observability import install_observability
from .routers import connectors
from .routes import health_router, keys_router, router

# Comprehensive security headers to prevent sniffing, framing, caching, and unauthorized scripting
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; sandbox",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    "X-Permitted-Cross-Domain-Policies": "none",
}

_ERROR_STATUS: tuple[tuple[type[MarginProtectorError], int], ...] = (
    (InvalidOrderError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (InsufficientDataError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (RateLimitError, status.HTTP_429_TOO_MANY_REQUESTS),
    (SecurityError, status.HTTP_401_UNAUTHORIZED),
    (FxDataError, status.HTTP_502_BAD_GATEWAY),
    (MarginProtectorError, status.HTTP_500_INTERNAL_SERVER_ERROR),
)


def create_app() -> FastAPI:
    # Completely disable /docs, /redoc, and /openapi.json to protect proprietary algorithms
    app = FastAPI(
        title="Parity API",
        version=core.__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    cors_origins = load_runtime_config().cors_allow_origins
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
            allow_credentials=False,
            max_age=3600,
        )

    for exception_type, status_code in _ERROR_STATUS:
        app.add_exception_handler(exception_type, _make_handler(status_code))

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    app.include_router(health_router)
    app.include_router(router)
    app.include_router(keys_router)
    app.include_router(connectors.router)
    install_request_guards(app)
    install_audit_logging(app)
    install_observability(app)
    return app


def _make_handler(status_code: int):
    async def handler(request: Request, exc: MarginProtectorError) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


__all__ = ["create_app"]
