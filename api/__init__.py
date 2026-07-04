from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

import core
from core.models.exceptions import (
    FxDataError,
    InsufficientDataError,
    InvalidOrderError,
    MarginProtectorError,
    RateLimitError,
    SecurityError,
)

from .routes import health_router, router

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}

_ERROR_STATUS: tuple[tuple[type[MarginProtectorError], int], ...] = (
    (InvalidOrderError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (InsufficientDataError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (RateLimitError, status.HTTP_429_TOO_MANY_REQUESTS),
    (SecurityError, status.HTTP_502_BAD_GATEWAY),
    (FxDataError, status.HTTP_502_BAD_GATEWAY),
    (MarginProtectorError, status.HTTP_500_INTERNAL_SERVER_ERROR),
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Parity API",
        description="FX risk simulation API for importers and e-commerce merchants.",
        version=core.__version__,
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
    return app


def _make_handler(status_code: int):
    async def handler(request: Request, exc: MarginProtectorError) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


__all__ = ["create_app"]
