from __future__ import annotations

import datetime as dt

import pandas as pd

from ...models.exceptions import InsufficientDataError, InvalidOrderError
from ...models.validation import validate_currency_code


class StaticFxDataProvider:
    def __init__(self, series: pd.Series) -> None:
        if series.empty:
            raise InsufficientDataError("The provided rate series is empty.")
        if not isinstance(series.index, pd.DatetimeIndex):
            raise InvalidOrderError("The series index must be a DatetimeIndex.")
        if (series <= 0).any() or series.isna().any():
            raise InvalidOrderError("The rate series contains non-positive or missing values.")
        self._series = series.astype("float64").sort_index()

    def get_historical_series(
        self, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series:
        validate_currency_code(base)
        validate_currency_code(quote)
        if end < start:
            raise InvalidOrderError("The end date must be on or after the start date.")

        mask = (self._series.index >= pd.Timestamp(start)) & (
            self._series.index <= pd.Timestamp(end)
        )
        sliced = self._series.loc[mask]
        if sliced.empty:
            raise InsufficientDataError(f"No data in the static series between {start} and {end}.")
        return sliced.copy()
