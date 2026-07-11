from __future__ import annotations

import datetime as dt
import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from db import build_auth_repository
from db.records import ApiAuditLogRecord


class AuditLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._repo = build_auth_repository()

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time_ms = (time.time() - start_time) * 1000
        client_id = getattr(request.state, "client_id", "anonymous")

        # Log to db in a fire-and-forget manner (though we block here, normally it's fast)
        import contextlib

        with contextlib.suppress(Exception):
            self._repo.log_audit(
                ApiAuditLogRecord(
                    id=None,
                    timestamp=dt.datetime.now(dt.UTC),
                    client_id=client_id,
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    processing_time_ms=process_time_ms,
                )
            )

        return response


def install_audit_logging(app: FastAPI) -> None:
    app.add_middleware(AuditLogMiddleware)
