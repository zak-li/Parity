from __future__ import annotations

import contextlib
import datetime as dt
import logging

from ..config import settings
from ..io.fx import FxDataProvider, build_default_fx_provider
from ..models import hedging, instruments, market_stats, monte_carlo, rates, scoring, volatility
from ..models.enums import (
    MarketModel,
    ReturnDistribution,
    RiskLevel,
    SamplingMethod,
    VolatilityModel,
)
from ..models.exceptions import FxDataError, InsufficientDataError, InvalidOrderError
from ..models.heston import (
    HestonParams,
    default_params_from_volatility,
    simulate_heston_terminal_rates,
)
from ..models.models import OrderInput, SimulationResult
from ..models.monte_carlo import JumpParams
from ..models.stress import (
    StressReport,
    StressScenario,
    apply_scenarios,
    canonical_scenarios,
    historical_stress_scenario,
    reverse_stress_test,
)
from .recommendation import build_recommendation

logger = logging.getLogger(__name__)


class MarginRiskEngine:
    def __init__(
        self,
        fx_provider: FxDataProvider | None = None,
        sampling_method: SamplingMethod = SamplingMethod.PSEUDO_RANDOM,
        volatility_model: VolatilityModel = VolatilityModel.HISTORICAL,
        return_distribution: ReturnDistribution = ReturnDistribution.NORMAL,
        student_t_dof: float = settings.DEFAULT_STUDENT_T_DOF,
        jumps: JumpParams | None = None,
        market_model: MarketModel = MarketModel.GBM,
        heston_params: HestonParams | None = None,
        api_key: str | None = None,
    ) -> None:
        from core.licensing import verify_license

        verify_license(api_key)
        self._api_key = api_key
        self._fx_provider = fx_provider or build_default_fx_provider()
        self._sampling_method = SamplingMethod(sampling_method)
        self._volatility_model = VolatilityModel(volatility_model)
        self._return_distribution = ReturnDistribution(return_distribution)
        self._student_t_dof = student_t_dof
        self._jumps = jumps
        self._market_model = MarketModel(market_model)
        self._heston_params = heston_params

    def run(self, order: OrderInput) -> SimulationResult:
        from core.licensing import verify_license

        verify_license(self._api_key)
        lookback_start = order.order_date - dt.timedelta(days=order.lookback_days)
        history = self._fx_provider.get_historical_series(
            order.foreign_currency, order.domestic_currency, lookback_start, order.order_date
        )
        spot = market_stats.spot_rate_on_or_before(history, order.order_date)
        horizon_years = order.horizon_days / settings.CALENDAR_DAYS_PER_YEAR
        sigma = volatility.estimate_volatility(history, self._volatility_model, order.horizon_days)

        revenue = self._resolve_revenue(order, spot)
        breakeven_rate = revenue / order.amount_foreign

        drift = rates.cip_drift(order.domestic_rate, order.foreign_rate)
        forward_rate = rates.theoretical_forward_rate(
            spot, order.domestic_rate, order.foreign_rate, horizon_years
        )

        simulated_rates = self._simulate_rates(order, spot, sigma, horizon_years, drift)
        simulated_margin_pct = 1.0 - (order.amount_foreign / revenue) * simulated_rates

        budgeted_cost_domestic = order.amount_foreign * spot
        budgeted_margin_domestic = revenue - budgeted_cost_domestic
        budgeted_margin_pct = budgeted_margin_domestic / revenue

        probability_below = scoring.probability_below_threshold(
            simulated_margin_pct, order.min_acceptable_margin_pct
        )
        tail_shortfall = scoring.conditional_value_at_risk(simulated_margin_pct)
        score = scoring.vulnerability_score(probability_below, budgeted_margin_pct, tail_shortfall)
        level = RiskLevel.from_score(score)

        hedge = hedging.evaluate_hedge(
            revenue=revenue,
            amount_foreign=order.amount_foreign,
            forward_rate=forward_rate,
            simulated_rates=simulated_rates,
            simulated_margin_pct=simulated_margin_pct,
            spot_rate=spot,
        )

        option_pricer = None
        if self._market_model is MarketModel.HESTON:
            option_pricer = instruments.mc_option_pricer(
                simulated_rates, order.domestic_rate, horizon_years
            )

        instrument_comparison = instruments.compare_instruments(
            revenue=revenue,
            amount_foreign=order.amount_foreign,
            spot=spot,
            forward=forward_rate,
            sigma_annual=sigma,
            domestic_rate=order.domestic_rate,
            foreign_rate=order.foreign_rate,
            horizon_years=horizon_years,
            simulated_rates=simulated_rates,
            min_acceptable_margin_pct=order.min_acceptable_margin_pct,
            option_pricer=option_pricer,
        )

        logger.info(
            "simulation_completed",
            extra={
                "pair": f"{order.foreign_currency}{order.domestic_currency}",
                "horizon_days": order.horizon_days,
                "vulnerability_score": score,
                "risk_level": level.value,
            },
        )

        return SimulationResult(
            order=order,
            spot_rate_order_date=spot,
            horizon_days=order.horizon_days,
            annualized_volatility=sigma,
            cip_drift=drift,
            expected_terminal_rate=forward_rate,
            breakeven_rate=breakeven_rate,
            budgeted_cost_domestic=budgeted_cost_domestic,
            budgeted_margin_domestic=budgeted_margin_domestic,
            budgeted_margin_pct=budgeted_margin_pct,
            rate_percentiles=scoring.percentiles(simulated_rates),
            margin_pct_percentiles=scoring.percentiles(simulated_margin_pct),
            probability_margin_below_threshold=probability_below,
            expected_shortfall_margin_pct=tail_shortfall,
            standard_error_margin_pct=monte_carlo.standard_error(simulated_margin_pct),
            vulnerability_score=score,
            risk_level=level,
            hedge=hedge,
            instrument_comparison=instrument_comparison,
            recommendation=build_recommendation(
                order, level, spot, breakeven_rate, probability_below, hedge
            ),
            simulated_rates=simulated_rates,
            simulated_margin_pct=simulated_margin_pct,
        )

    def _simulate_rates(self, order, spot, sigma, horizon_years, drift):
        if self._market_model is MarketModel.HESTON:
            params = self._heston_params or default_params_from_volatility(sigma)
            return simulate_heston_terminal_rates(
                spot=spot,
                horizon_years=horizon_years,
                n_sims=order.n_simulations,
                params=params,
                mu_annual=drift,
                seed=order.seed,
            )
        return monte_carlo.simulate_terminal_rates(
            spot=spot,
            sigma_annual=sigma,
            horizon_years=horizon_years,
            n_sims=order.n_simulations,
            mu_annual=drift,
            seed=order.seed,
            method=self._sampling_method,
            distribution=self._return_distribution,
            student_t_dof=self._student_t_dof,
            jumps=self._jumps,
        )

    @staticmethod
    def _resolve_revenue(order: OrderInput, spot_rate: float) -> float:
        if order.expected_revenue_domestic is not None:
            return order.expected_revenue_domestic
        budgeted_cost_at_order = order.amount_foreign * spot_rate
        assert order.target_margin_pct is not None
        return budgeted_cost_at_order * (1 + order.target_margin_pct)

    def stress_test(self, order: OrderInput) -> StressReport:
        lookback_start = order.order_date - dt.timedelta(days=order.lookback_days)
        history = self._fx_provider.get_historical_series(
            order.foreign_currency, order.domestic_currency, lookback_start, order.order_date
        )
        spot = market_stats.spot_rate_on_or_before(history, order.order_date)
        revenue = self._resolve_revenue(order, spot)
        budgeted_margin_pct = (revenue - order.amount_foreign * spot) / revenue

        scenarios: list[StressScenario] = list(canonical_scenarios())
        with contextlib.suppress(InsufficientDataError):
            scenarios.append(
                historical_stress_scenario(
                    history, order.horizon_days, "Worst historical move (recent window)"
                )
            )
        scenarios.extend(self._crisis_scenarios(order))

        return StressReport(
            spot=spot,
            budgeted_margin_pct=budgeted_margin_pct,
            scenarios=apply_scenarios(
                revenue, order.amount_foreign, spot, budgeted_margin_pct, tuple(scenarios)
            ),
            reverse_stress=reverse_stress_test(
                revenue, order.amount_foreign, spot, order.min_acceptable_margin_pct
            ),
        )

    def _crisis_scenarios(self, order: OrderInput) -> list[StressScenario]:
        scenarios: list[StressScenario] = []
        for name, start, end in settings.CRISIS_WINDOWS:
            try:
                window = self._fx_provider.get_historical_series(
                    order.foreign_currency,
                    order.domestic_currency,
                    dt.date.fromisoformat(start),
                    dt.date.fromisoformat(end),
                )
                scenarios.append(
                    historical_stress_scenario(window, order.horizon_days, f"Replay {name}")
                )
            except (FxDataError, InsufficientDataError, InvalidOrderError):
                continue
        return scenarios
