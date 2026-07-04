from __future__ import annotations

import datetime as dt
from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from core.io.fx.static import StaticFxDataProvider
from core.models.models import OrderInput

SeriesFactory = Callable[..., pd.Series]


def _make_synthetic_series(
    base_rate: float,
    n_days: int,
    annual_sigma: float,
    end_date: dt.date,
    seed: int = 0,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(end_date), periods=n_days)
    daily_sigma = annual_sigma / np.sqrt(252)
    log_returns = rng.normal(loc=0.0, scale=daily_sigma, size=n_days)
    log_returns[0] = 0.0
    values = base_rate * np.exp(np.cumsum(log_returns))
    return pd.Series(values, index=dates, name="USDMAD", dtype="float64")


@pytest.fixture
def make_series() -> SeriesFactory:
    return _make_synthetic_series


@pytest.fixture
def reference_order_date() -> dt.date:
    return dt.date(2026, 1, 15)


@pytest.fixture
def synthetic_series(reference_order_date) -> pd.Series:
    return _make_synthetic_series(
        base_rate=10.0, n_days=200, annual_sigma=0.12, end_date=reference_order_date, seed=42
    )


@pytest.fixture
def static_provider(synthetic_series) -> StaticFxDataProvider:
    return StaticFxDataProvider(synthetic_series)


@pytest.fixture
def sample_order(reference_order_date) -> OrderInput:
    return OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="usd",
        domestic_currency="mad",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=60),
        target_margin_pct=0.30,
        n_simulations=5000,
        lookback_days=180,
        seed=7,
    )
