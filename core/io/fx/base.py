from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class FxDataProvider(Protocol):
    def get_historical_series(
        self, base: str, quote: str, start: dt.date, end: dt.date
    ) -> pd.Series: ...
