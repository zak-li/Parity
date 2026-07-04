from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests

from core.config.settings import RuntimeConfig
from core.io.cache import TTLCache
from core.io.fx.frankfurter import FrankfurterFxDataProvider
from core.io.fx.static import StaticFxDataProvider
from core.io.rate_limiter import TokenBucketRateLimiter
from core.models.exceptions import (
    FxDataError,
    InsufficientDataError,
    InvalidOrderError,
    RateLimitError,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        if raise_json:
            self.content = b"not-json{"
        else:
            self.content = json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


def _make_provider(session, *, rate_limiter=None, cache=None):
    return FrankfurterFxDataProvider(
        session=session,
        config=RuntimeConfig(),
        cache=cache or TTLCache(ttl_seconds=3600, max_entries=32),
        rate_limiter=rate_limiter or TokenBucketRateLimiter(rate_per_second=1000, capacity=1000),
    )


def test_successful_fetch_returns_series():
    payload = {"rates": {"2026-01-02": {"MAD": 10.1}, "2026-01-05": {"MAD": 10.2}}}
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, payload)
    provider = _make_provider(session)

    result = provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))

    assert isinstance(result, pd.Series)
    assert len(result) == 2
    assert result.iloc[0] == pytest.approx(10.1)


def test_non_200_status_raises_fx_data_error():
    session = MagicMock()
    session.get.return_value = _FakeResponse(500, {})
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_oversized_content_length_header_raises_fx_data_error():
    session = MagicMock()
    session.get.return_value = _FakeResponse(
        200, {"rates": {"2026-01-02": {"MAD": 10.1}}}, headers={"Content-Length": "999999999"}
    )
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_oversized_actual_content_without_header_raises_fx_data_error():
    session = MagicMock()
    response = _FakeResponse(200, {"rates": {"2026-01-02": {"MAD": 10.1}}})
    response.content = b"x" * (RuntimeConfig().http_max_response_bytes + 1)
    session.get.return_value = response
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_malformed_content_length_header_is_ignored():
    payload = {"rates": {"2026-01-02": {"MAD": 10.1}}}
    session = MagicMock()
    session.get.return_value = _FakeResponse(
        200, payload, headers={"Content-Length": "not-a-number"}
    )
    provider = _make_provider(session)

    result = provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    assert len(result) == 1


def test_empty_rates_raises_fx_data_error():
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, {"rates": {}})
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_incomplete_rate_entry_raises_fx_data_error():
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, {"rates": {"2026-01-02": {"EUR": 1.1}}})
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_invalid_json_raises_fx_data_error():
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, {}, raise_json=True)
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_network_exception_raises_fx_data_error():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("boom")
    provider = _make_provider(session)

    with pytest.raises(FxDataError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_rate_limit_exceeded_raises_rate_limit_error():
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, {"rates": {"2026-01-02": {"MAD": 10.1}}})
    limiter = TokenBucketRateLimiter(rate_per_second=0.01, capacity=1)
    cache = TTLCache(ttl_seconds=3600, max_entries=32)
    provider = _make_provider(session, rate_limiter=limiter, cache=cache)

    provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    with pytest.raises(RateLimitError):
        provider.get_historical_series("EUR", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


def test_results_are_cached_between_calls():
    payload = {"rates": {"2026-01-02": {"MAD": 10.1}}}
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, payload)
    provider = _make_provider(session)

    provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))

    assert session.get.call_count == 1


def test_cached_series_is_defensively_copied():
    payload = {"rates": {"2026-01-02": {"MAD": 10.1}}}
    session = MagicMock()
    session.get.return_value = _FakeResponse(200, payload)
    provider = _make_provider(session)

    first = provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    first.iloc[0] = 999.0
    second = provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))

    assert second.iloc[0] == pytest.approx(10.1)


def test_end_date_before_start_date_raises():
    provider = _make_provider(MagicMock())
    with pytest.raises(InvalidOrderError):
        provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 5), dt.date(2026, 1, 1))


def test_invalid_currency_raises_invalid_order_error():
    provider = _make_provider(MagicMock())
    with pytest.raises(InvalidOrderError):
        provider.get_historical_series("US", "MAD", dt.date(2026, 1, 1), dt.date(2026, 1, 5))


class TestStaticFxDataProvider:
    def test_slices_series_within_range(self):
        dates = pd.bdate_range("2026-01-01", periods=10)
        series = pd.Series(range(10, 20), index=dates, dtype="float64")
        provider = StaticFxDataProvider(series)

        result = provider.get_historical_series("USD", "MAD", dates[2].date(), dates[5].date())
        assert len(result) == 4

    def test_empty_series_raises_at_construction(self):
        with pytest.raises(InsufficientDataError):
            StaticFxDataProvider(pd.Series([], dtype="float64"))

    def test_non_datetime_index_raises(self):
        with pytest.raises(InvalidOrderError):
            StaticFxDataProvider(pd.Series([1.0, 2.0]))

    def test_non_positive_values_raise(self):
        dates = pd.bdate_range("2026-01-01", periods=3)
        with pytest.raises(InvalidOrderError):
            StaticFxDataProvider(pd.Series([10.0, -1.0, 10.5], index=dates))

    def test_no_data_in_range_raises(self):
        dates = pd.bdate_range("2026-01-01", periods=3)
        provider = StaticFxDataProvider(pd.Series([10.0, 10.1, 10.2], index=dates))
        with pytest.raises(InsufficientDataError):
            provider.get_historical_series("USD", "MAD", dt.date(2027, 1, 1), dt.date(2027, 1, 5))

    def test_end_date_before_start_date_raises(self):
        dates = pd.bdate_range("2026-01-01", periods=3)
        provider = StaticFxDataProvider(pd.Series([10.0, 10.1, 10.2], index=dates))
        with pytest.raises(InvalidOrderError):
            provider.get_historical_series("USD", "MAD", dt.date(2026, 1, 5), dt.date(2026, 1, 1))
