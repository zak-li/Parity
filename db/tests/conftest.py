from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core.app.risk_engine import MarginRiskEngine
from core.io.fx.static import StaticFxDataProvider
from core.models.models import OrderInput


@pytest.fixture
def simulation_result():
    rng = np.random.default_rng(7)
    end = dt.date(2026, 1, 15)
    dates = pd.bdate_range(end=pd.Timestamp(end), periods=220)
    log_returns = rng.normal(0, 0.12 / np.sqrt(252), 220)
    log_returns[0] = 0.0
    series = pd.Series(10.0 * np.exp(np.cumsum(log_returns)), index=dates)
    order = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=end,
        delivery_date=end + dt.timedelta(days=90),
        target_margin_pct=0.15,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=5_000,
        seed=7,
    )
    return MarginRiskEngine(StaticFxDataProvider(series)).run(order)
