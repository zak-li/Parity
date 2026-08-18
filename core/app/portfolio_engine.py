from __future__ import annotations

import datetime as dt
import logging

import numpy as np
import pandas as pd

from ..config import settings
from ..io.fx import FxDataProvider, build_default_fx_provider
from ..models import market_stats, rates, volatility
from ..models.dcc import estimate_dcc
from ..models.enums import VolatilityModel
from ..models.exceptions import InsufficientDataError, InvalidOrderError
from ..models.models import OrderInput
from ..models.portfolio import PortfolioPosition, PortfolioResult, simulate_portfolio

logger = logging.getLogger(__name__)


class PortfolioRiskEngine:
    def __init__(
        self,
        fx_provider: FxDataProvider | None = None,
        volatility_model: VolatilityModel = VolatilityModel.HISTORICAL,
        dynamic_correlation: bool = False,
    ) -> None:
        self._fx_provider = fx_provider or build_default_fx_provider()
        self._volatility_model = VolatilityModel(volatility_model)
        self._dynamic_correlation = dynamic_correlation

    def run(self, orders: list[OrderInput], seed: int | None = None) -> PortfolioResult:
        if not orders:
            raise InvalidOrderError("The portfolio must contain at least one order.")
        domestic = orders[0].domestic_currency
        if any(order.domestic_currency != domestic for order in orders):
            raise InvalidOrderError("All orders must share the same domestic currency.")

        positions: list[PortfolioPosition] = []
        return_series: dict[str, pd.Series] = {}
        for index, order in enumerate(orders):
            lookback_start = order.order_date - dt.timedelta(days=order.lookback_days)
            history = self._fx_provider.get_historical_series(
                order.foreign_currency, order.domestic_currency, lookback_start, order.order_date
            )
            spot = market_stats.spot_rate_on_or_before(history, order.order_date)
            sigma = volatility.estimate_volatility(
                history, self._volatility_model, order.horizon_days
            )
            drift = rates.cip_drift(order.domestic_rate, order.foreign_rate)
            revenue = self._resolve_revenue(order, spot)
            positions.append(
                PortfolioPosition(
                    label=f"order_{index + 1}",
                    foreign_currency=order.foreign_currency,
                    amount_foreign=order.amount_foreign,
                    revenue_domestic=revenue,
                    spot=spot,
                    sigma_annual=sigma,
                    drift_annual=drift,
                    horizon_years=order.horizon_days / settings.CALENDAR_DAYS_PER_YEAR,
                    min_acceptable_margin_pct=order.min_acceptable_margin_pct,
                )
            )
            if order.foreign_currency not in return_series:
                return_series[order.foreign_currency] = np.log(history / history.shift(1)).dropna()

        currencies = sorted(return_series)
        correlation = self._correlation_matrix(return_series, currencies)
        max_sims = max(order.n_simulations for order in orders)

        result = simulate_portfolio(positions, correlation, currencies, max_sims, seed)
        logger.info(
            "portfolio_simulation_completed",
            extra={
                "positions": len(positions),
                "currencies": len(currencies),
                "vulnerability_score": result.vulnerability_score,
            },
        )
        return result

    def _correlation_matrix(
        self, return_series: dict[str, pd.Series], currencies: list[str]
    ) -> np.ndarray:
        if len(currencies) == 1:
            return np.ones((1, 1))
        frame = pd.DataFrame({c: return_series[c] for c in currencies}).dropna()
        if len(frame) < 3:
            raise InsufficientDataError(
                "Insufficient overlapping history to estimate correlations."
            )
        if self._dynamic_correlation:
            try:
                return estimate_dcc(frame).correlation
            except InsufficientDataError:
                logger.warning("dcc_fallback_to_static")
        matrix = frame.corr().to_numpy()
        return np.nan_to_num(matrix, nan=0.0)

    @staticmethod
    def _resolve_revenue(order: OrderInput, spot_rate: float) -> float:
        if order.expected_revenue_domestic is not None:
            return order.expected_revenue_domestic
        assert order.target_margin_pct is not None
        return order.amount_foreign * spot_rate * (1 + order.target_margin_pct)
