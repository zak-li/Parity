from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from core.io.fx.fallback import CircuitBreaker, FallbackFxDataProvider
from core.models.exceptions import FxDataError, InvalidOrderError

_SERIES = pd.Series([1.0, 1.1], index=pd.bdate_range("2026-01-01", periods=2))
_ARGS = ("USD", "EUR", dt.date(2026, 1, 1), dt.date(2026, 1, 2))


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Provider:
    def __init__(self, *, series=None, error=None):
        self.series = series
        self.error = error
        self.calls = 0

    def get_historical_series(self, base, quote, start, end):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.series


def test_falls_back_to_next_provider_on_error():
    primary = _Provider(error=FxDataError("down"))
    secondary = _Provider(series=_SERIES)
    provider = FallbackFxDataProvider([primary, secondary])
    result = provider.get_historical_series(*_ARGS)
    assert result.equals(_SERIES)
    assert primary.calls == 1 and secondary.calls == 1


def test_circuit_opens_and_skips_failing_provider():
    primary = _Provider(error=FxDataError("down"))
    secondary = _Provider(series=_SERIES)
    provider = FallbackFxDataProvider([primary, secondary], failure_threshold=2)
    for _ in range(4):
        provider.get_historical_series(*_ARGS)
    # After 2 failures the primary's breaker opens and it is no longer called.
    assert primary.calls == 2


def test_circuit_recovers_after_cooldown():
    clock = _FakeClock()
    primary = _Provider(error=FxDataError("down"))
    secondary = _Provider(series=_SERIES)
    provider = FallbackFxDataProvider(
        [primary, secondary], failure_threshold=1, reset_timeout_seconds=30.0, clock=clock
    )
    provider.get_historical_series(*_ARGS)  # trips the breaker
    provider.get_historical_series(*_ARGS)  # breaker open -> primary skipped
    assert primary.calls == 1
    clock.now = 31.0  # cooldown elapsed -> half-open trial
    provider.get_historical_series(*_ARGS)
    assert primary.calls == 2


def test_caller_error_is_not_caught():
    primary = _Provider(error=InvalidOrderError("bad currency"))
    secondary = _Provider(series=_SERIES)
    provider = FallbackFxDataProvider([primary, secondary])
    with pytest.raises(InvalidOrderError):
        provider.get_historical_series(*_ARGS)
    assert secondary.calls == 0


def test_all_providers_failing_raises_last_error():
    provider = FallbackFxDataProvider(
        [_Provider(error=FxDataError("a")), _Provider(error=FxDataError("b"))]
    )
    with pytest.raises(FxDataError):
        provider.get_historical_series(*_ARGS)


def test_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        FallbackFxDataProvider([])


def test_circuit_breaker_rejects_bad_threshold():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
