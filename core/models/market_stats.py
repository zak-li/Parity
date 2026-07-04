from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ..config import settings
from .exceptions import InsufficientDataError


def annualized_volatility(
    series: pd.Series, trading_days_per_year: int = settings.TRADING_DAYS_PER_YEAR
) -> float:
    if len(series) < 3:
        raise InsufficientDataError("At least 3 data points are required to estimate volatility.")
    log_returns = np.log(series / series.shift(1)).dropna()
    if log_returns.empty:
        raise InsufficientDataError("Unable to compute returns from the provided data.")
    std = float(log_returns.std(ddof=1))
    if not np.isfinite(std) or std <= 0:
        raise InsufficientDataError(
            "Unable to estimate a non-zero volatility from the provided data."
        )
    return std * np.sqrt(trading_days_per_year)


def spot_rate_on_or_before(series: pd.Series, on_date: dt.date) -> float:
    ts = pd.Timestamp(on_date)
    eligible = series.loc[series.index <= ts]
    if eligible.empty:
        raise InsufficientDataError(f"No rate available on {on_date} or earlier.")
    return float(eligible.iloc[-1])
