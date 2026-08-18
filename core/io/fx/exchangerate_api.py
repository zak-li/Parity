from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import requests

from ...config import load_runtime_config
from ...config.settings import RuntimeConfig
from ...models.exceptions import FxDataError, InvalidOrderError, RateLimitError
from ...models.validation import validate_currency_code
from ..cache import TTLCache
from ..http import build_secure_session
from ..rate_limiter import TokenBucketRateLimiter
from ..ssrf import HostAllowlist


class ExchangeRateApiFxDataProvider:
    """FX data provider using ExchangeRate-API (open endpoint or key-authenticated)."""

    def __init__(
        self,
        session: requests.Session | None = None,
        config: RuntimeConfig | None = None,
        cache: TTLCache | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self._config = config or load_runtime_config()
        allowlist = HostAllowlist(self._config.allowed_fx_hosts)
        self._session = session or build_secure_session(self._config, allowlist)
        self._timeout = self._config.http_timeout_seconds
        self._max_response_bytes = self._config.http_max_response_bytes
        self._api_key = self._config.exchangerate_api_key

        self._cache = (
            cache
            if cache is not None
            else TTLCache(
                ttl_seconds=self._config.cache_ttl_seconds,
                max_entries=self._config.cache_max_entries,
            )
        )
        self._rate_limiter = (
            rate_limiter
            if rate_limiter is not None
            else TokenBucketRateLimiter(
                rate_per_second=self._config.rate_limit_per_second,
                capacity=self._config.rate_limit_burst,
            )
        )

    def get_historical_series(
        self, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        base = validate_currency_code(base)
        quote = validate_currency_code(quote)
        if end < start:
            raise InvalidOrderError("The end date must be on or after the start date.")

        cache_key = ("exchangerate_api", base, quote, start.isoformat(), end.isoformat())
        return self._cache.get_or_set(
            cache_key, lambda: self._fetch(base, quote, start, end)
        ).copy()

    def _fetch(self, base: str, quote: str, start: dt.date, end: dt.date) -> pd.Series:
        if not self._rate_limiter.try_acquire():
            raise RateLimitError("Rate limit reached for ExchangeRate-API provider.")

        if self._api_key:
            url = f"https://v6.exchangerate-api.com/v6/{self._api_key}/history/{base}/{start.year}/{start.month}/{start.day}"
        else:
            url = f"https://open.er-api.com/v6/latest/{base}"

        try:
            with self._session.get(url, timeout=self._timeout, stream=True) as response:
                if response.status_code != 200:
                    raise FxDataError(
                        f"ExchangeRate-API returned status {response.status_code} for {base}/{quote}."
                    )
                body = self._read_capped(response)
        except requests.RequestException as exc:
            raise FxDataError(f"Failed to connect to ExchangeRate-API provider: {exc}") from exc

        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise FxDataError("Invalid JSON response from ExchangeRate-API provider.") from exc

        return self._parse_response(payload, base, quote, start, end)

    def _read_capped(self, response: requests.Response) -> bytes:
        declared = response.headers.get("Content-Length")
        if declared is not None and declared.isdigit() and int(declared) > self._max_response_bytes:
            raise FxDataError("ExchangeRate-API response too large.")
        chunks: list[bytes] = []
        received = 0
        for chunk in response.iter_content(chunk_size=65536):
            received += len(chunk)
            if received > self._max_response_bytes:
                raise FxDataError("ExchangeRate-API response too large.")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _parse_response(
        payload: object, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        if not isinstance(payload, dict) or payload.get("result") == "error":
            error_type = payload.get("error-type") if isinstance(payload, dict) else "unknown"
            raise FxDataError(f"ExchangeRate-API error: {error_type}")

        rates = payload.get("rates", payload.get("conversion_rates", {}))
        if not rates or quote not in rates:
            raise FxDataError(
                f"No historical rate available for {base}/{quote} between {start} and {end}."
            )

        val = float(rates[quote])
        # Construct a synthetic daily series if latest rate endpoint or single point was returned
        date_range = pd.date_range(start=pd.Timestamp(start), end=pd.Timestamp(end), freq="D")
        return pd.Series(
            [val] * len(date_range), index=date_range, name=f"{base}{quote}", dtype="float64"
        )
