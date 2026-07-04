from __future__ import annotations

import os
import secrets
from functools import lru_cache

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from ai import Narrator, build_narrator
from core.io.fx import FrankfurterFxDataProvider, FxDataProvider
from db import SimulationRepository, build_repository

_API_KEY_ENV = "XI_API_KEY"
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@lru_cache(maxsize=1)
def get_fx_provider() -> FxDataProvider:
    return FrankfurterFxDataProvider()


@lru_cache(maxsize=1)
def get_repository() -> SimulationRepository:
    return build_repository()


@lru_cache(maxsize=1)
def get_narrator() -> Narrator:
    return build_narrator()


def require_api_key(provided: str | None = Security(_api_key_header)) -> None:
    expected = os.environ.get(_API_KEY_ENV)
    if not expected:
        return
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
