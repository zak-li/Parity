"""Fallback FX data provider with a per-provider circuit breaker.

Wraps an ordered list of providers behind the :class:`FxDataProvider` port and
tries them in turn: on a provider/data error it moves to the next source and
trips that provider's circuit breaker after repeated failures, so a persistently
down source is skipped (until a cooldown) instead of being retried every call.

Caller errors (e.g. :class:`InvalidOrderError`) are *not* caught — they would
fail identically on every provider — and propagate immediately.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable, Sequence

import pandas as pd

from ...models.exceptions import FxDataError, SecurityError
from .base import FxDataProvider

_FALLBACK_ERRORS = (FxDataError, SecurityError)


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout_seconds: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1.")
        self._threshold = failure_threshold
        self._reset = reset_timeout_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            # Half-open: allow one trial once the cooldown has elapsed.
            return self._clock() - self._opened_at >= self._reset

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = self._clock()


class FallbackFxDataProvider:
    def __init__(
        self,
        providers: Sequence[FxDataProvider],
        *,
        failure_threshold: int = 3,
        reset_timeout_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not providers:
            raise ValueError("At least one FX data provider is required.")
        self._entries = [
            (provider, CircuitBreaker(failure_threshold, reset_timeout_seconds, clock=clock))
            for provider in providers
        ]

    def get_historical_series(
        self, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        last_error: Exception | None = None
        for provider, breaker in self._entries:
            if not breaker.allow():
                continue
            try:
                series = provider.get_historical_series(base, quote, start, end)
            except _FALLBACK_ERRORS as exc:
                breaker.record_failure()
                last_error = exc
                continue
            breaker.record_success()
            return series
        if last_error is not None:
            raise last_error
        raise FxDataError("All FX data providers are unavailable (circuit breakers open).")
