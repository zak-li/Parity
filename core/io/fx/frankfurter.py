from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import requests

from ...config import load_runtime_config
from ...config.settings import RuntimeConfig
from ...models.exceptions import FxDataError, InvalidOrderError, RateLimitError
from ...models.validation import validate_currency_code
from ..rate_limiter import TokenBucketRateLimiter
from ..ssrf import HostAllowlist
from ..cache import TTLCache
from ..http import build_secure_session


class FrankfurterFxDataProvider:
    _BASE_URL = "https://api.frankfurter.dev/v1"

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
        self._cache = cache or TTLCache(
            ttl_seconds=self._config.cache_ttl_seconds,
            max_entries=self._config.cache_max_entries,
        )
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter(
            rate_per_second=self._config.rate_limit_per_second,
            capacity=self._config.rate_limit_burst,
        )

    def get_historical_series(
        self, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        base = validate_currency_code(base)
        quote = validate_currency_code(quote)
        if end < start:
            raise InvalidOrderError("La date de fin doit être postérieure ou égale à la date de début.")

        cache_key = (base, quote, start.isoformat(), end.isoformat())
        return self._cache.get_or_set(cache_key, lambda: self._fetch(base, quote, start, end)).copy()

    def _fetch(self, base: str, quote: str, start: dt.date, end: dt.date) -> pd.Series:
        if not self._rate_limiter.try_acquire():
            raise RateLimitError("Limite de débit atteinte pour le fournisseur de taux de change.")

        url = f"{self._BASE_URL}/{start.isoformat()}..{end.isoformat()}"
        try:
            with self._session.get(
                url, params={"base": base, "symbols": quote}, timeout=self._timeout, stream=True
            ) as response:
                if response.status_code != 200:
                    raise FxDataError(
                        f"Le fournisseur de taux de change a retourné une erreur "
                        f"{response.status_code} pour {base}/{quote}."
                    )
                body = self._read_capped(response)
        except requests.RequestException as exc:
            raise FxDataError(f"Échec de connexion au fournisseur de taux de change: {exc}") from exc

        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise FxDataError("Réponse invalide du fournisseur de taux de change.") from exc

        return self._parse_series(payload, base, quote, start, end)

    def _read_capped(self, response: requests.Response) -> bytes:
        declared = response.headers.get("Content-Length")
        if declared is not None and declared.isdigit() and int(declared) > self._max_response_bytes:
            raise FxDataError("Réponse du fournisseur de taux de change trop volumineuse.")
        chunks: list[bytes] = []
        received = 0
        for chunk in response.iter_content(chunk_size=65536):
            received += len(chunk)
            if received > self._max_response_bytes:
                raise FxDataError("Réponse du fournisseur de taux de change trop volumineuse.")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _parse_series(
        payload: object, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
        if not rates:
            raise FxDataError(
                f"Aucune donnée historique disponible pour {base}/{quote} entre {start} et {end}."
            )
        dates = sorted(rates)
        try:
            values = [rates[d][quote] for d in dates]
        except (KeyError, TypeError) as exc:
            raise FxDataError(f"Données incomplètes reçues pour {base}/{quote}.") from exc
        return pd.Series(
            values, index=pd.to_datetime(dates), name=f"{base}{quote}", dtype="float64"
        )
