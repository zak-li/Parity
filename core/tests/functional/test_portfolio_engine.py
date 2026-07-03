from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core.app.portfolio_engine import PortfolioRiskEngine
from core.io.fx.static import StaticFxDataProvider
from core.models.exceptions import InvalidOrderError
from core.models.models import OrderInput


class MultiPairProvider:
    def __init__(self, series_by_quote):
        self._series = series_by_quote

    def get_historical_series(self, base, quote, start, end):
        series = self._series[base]
        mask = (series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))
        return series.loc[mask].copy()


def _series(base_rate, sigma, end_date, seed):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(end_date), periods=220)
    lr = rng.normal(0, sigma / np.sqrt(252), 220)
    lr[0] = 0.0
    return pd.Series(base_rate * np.exp(np.cumsum(lr)), index=dates)


@pytest.fixture
def provider():
    end = dt.date(2026, 1, 15)
    return MultiPairProvider(
        {"USD": _series(10.0, 0.15, end, 1), "EUR": _series(11.0, 0.12, end, 2)}
    )


def _order(currency, amount, seed_days=90):
    return OrderInput(
        amount_foreign=amount,
        foreign_currency=currency,
        domestic_currency="MAD",
        order_date=dt.date(2026, 1, 15),
        delivery_date=dt.date(2026, 1, 15) + dt.timedelta(days=seed_days),
        target_margin_pct=0.15,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=20_000,
        seed=7,
    )


def test_portfolio_engine_aggregates_multiple_currencies(provider):
    orders = [_order("USD", 100_000.0), _order("EUR", 80_000.0)]
    result = PortfolioRiskEngine(provider).run(orders, seed=5)

    assert set(result.net_exposures) == {"USD", "EUR"}
    assert result.net_exposures["USD"] == pytest.approx(100_000.0)
    assert 0 <= result.vulnerability_score <= 100
    assert result.total_revenue_domestic > 0


def test_portfolio_engine_rejects_mixed_domestic_currencies(provider):
    order_mad = _order("USD", 100_000.0)
    order_eur_domestic = OrderInput(
        amount_foreign=50_000.0,
        foreign_currency="USD",
        domestic_currency="EUR",
        order_date=dt.date(2026, 1, 15),
        delivery_date=dt.date(2026, 3, 1),
        target_margin_pct=0.1,
    )
    with pytest.raises(InvalidOrderError):
        PortfolioRiskEngine(provider).run([order_mad, order_eur_domestic])


def test_portfolio_engine_rejects_empty(provider):
    with pytest.raises(InvalidOrderError):
        PortfolioRiskEngine(provider).run([])


def test_single_currency_portfolio_runs(provider):
    result = PortfolioRiskEngine(provider).run([_order("USD", 100_000.0)], seed=1)
    assert result.risk_level is not None


def test_dynamic_correlation_portfolio_runs(provider):
    orders = [_order("USD", 100_000.0), _order("EUR", 80_000.0)]
    result = PortfolioRiskEngine(provider, dynamic_correlation=True).run(orders, seed=5)
    assert 0 <= result.vulnerability_score <= 100
    assert set(result.net_exposures) == {"USD", "EUR"}


def test_portfolio_engine_uses_expected_revenue_when_provided(provider):
    order = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=dt.date(2026, 1, 15),
        delivery_date=dt.date(2026, 4, 15),
        expected_revenue_domestic=1_300_000.0,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=20_000,
        seed=1,
    )
    result = PortfolioRiskEngine(provider).run([order], seed=1)
    assert result.total_revenue_domestic == pytest.approx(1_300_000.0)


def test_correlation_matrix_raises_on_insufficient_common_history():
    from core.models.exceptions import InsufficientDataError

    idx_a = pd.bdate_range("2026-01-01", periods=5)
    idx_b = pd.bdate_range("2020-01-01", periods=5)
    series = {"USD": pd.Series(range(5), index=idx_a, dtype="float64"),
              "EUR": pd.Series(range(5), index=idx_b, dtype="float64")}
    with pytest.raises(InsufficientDataError):
        PortfolioRiskEngine()._correlation_matrix(series, ["EUR", "USD"])
