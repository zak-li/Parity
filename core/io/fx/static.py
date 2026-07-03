from __future__ import annotations

import datetime as dt

import pandas as pd

from ...models.exceptions import InsufficientDataError, InvalidOrderError
from ...models.validation import validate_currency_code


class StaticFxDataProvider:
    def __init__(self, series: pd.Series) -> None:
        if series.empty:
            raise InsufficientDataError("La série de taux fournie est vide.")
        if not isinstance(series.index, pd.DatetimeIndex):
            raise InvalidOrderError("L'index de la série doit être un DatetimeIndex.")
        if (series <= 0).any() or series.isna().any():
            raise InvalidOrderError("La série de taux contient des valeurs non positives ou manquantes.")
        self._series = series.astype("float64").sort_index()

    def get_historical_series(
        self, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        validate_currency_code(base)
        validate_currency_code(quote)
        if end < start:
            raise InvalidOrderError("La date de fin doit être postérieure ou égale à la date de début.")

        mask = (self._series.index >= pd.Timestamp(start)) & (self._series.index <= pd.Timestamp(end))
        sliced = self._series.loc[mask]
        if sliced.empty:
            raise InsufficientDataError(f"Aucune donnée dans la série statique entre {start} et {end}.")
        return sliced.copy()
