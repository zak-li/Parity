from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core.models.exceptions import InsufficientDataError
from core.models.market_stats import annualized_volatility, spot_rate_on_or_before


def test_annualized_volatility_matches_known_std():
    dates = pd.bdate_range("2026-01-01", periods=252)
    log_returns = np.zeros(252)
    log_returns[1:] = 0.01
    series = pd.Series(100 * np.exp(np.cumsum(log_returns)), index=dates)

    result = annualized_volatility(series)

    expected_daily_std = pd.Series(log_returns[1:]).std(ddof=1)
    assert result == pytest.approx(expected_daily_std * np.sqrt(252), rel=1e-9)


def test_raises_on_fewer_than_three_points():
    series = pd.Series([10.0, 10.1], index=pd.bdate_range("2026-01-01", periods=2))
    with pytest.raises(InsufficientDataError):
        annualized_volatility(series)


def test_raises_on_constant_series():
    series = pd.Series([10.0] * 10, index=pd.bdate_range("2026-01-01", periods=10))
    with pytest.raises(InsufficientDataError):
        annualized_volatility(series)


def test_spot_rate_on_or_before_returns_latest_eligible_value():
    dates = pd.bdate_range("2026-01-01", periods=5)
    series = pd.Series([10.0, 10.1, 10.2, 10.3, 10.4], index=dates)

    assert spot_rate_on_or_before(series, dates[2].date()) == pytest.approx(10.2)


def test_spot_rate_on_or_before_raises_when_no_data():
    dates = pd.bdate_range("2026-02-01", periods=3)
    series = pd.Series([10.0, 10.1, 10.2], index=dates)

    with pytest.raises(InsufficientDataError):
        spot_rate_on_or_before(series, dt.date(2026, 1, 1))
