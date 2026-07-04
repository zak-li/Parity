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
        raise InsufficientDataError(
            "Au moins 3 points de données sont nécessaires pour estimer la volatilité."
        )
    log_returns = np.log(series / series.shift(1)).dropna()
    if log_returns.empty:
        raise InsufficientDataError(
            "Impossible de calculer des rendements à partir des données fournies."
        )
    std = float(log_returns.std(ddof=1))
    if not np.isfinite(std) or std <= 0:
        raise InsufficientDataError(
            "Impossible d'estimer une volatilité non nulle à partir des données fournies."
        )
    return std * np.sqrt(trading_days_per_year)


def spot_rate_on_or_before(series: pd.Series, on_date: dt.date) -> float:
    ts = pd.Timestamp(on_date)
    eligible = series.loc[series.index <= ts]
    if eligible.empty:
        raise InsufficientDataError(f"Aucun taux disponible à la date {on_date} ou avant.")
    return float(eligible.iloc[-1])
