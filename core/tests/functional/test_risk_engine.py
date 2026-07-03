from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from core.models.enums import (
    HedgeInstrument,
    ReturnDistribution,
    RiskLevel,
    SamplingMethod,
    VolatilityModel,
)
from core.models.exceptions import InsufficientDataError
from core.models.models import OrderInput
from core.models.monte_carlo import JumpParams
from core.io.fx.static import StaticFxDataProvider
from core.app.risk_engine import MarginRiskEngine


def test_result_fields_are_internally_consistent(static_provider, sample_order):
    engine = MarginRiskEngine(static_provider)
    result = engine.run(sample_order)

    assert 0 <= result.vulnerability_score <= 100
    assert isinstance(result.risk_level, RiskLevel)
    assert 0.0 <= result.probability_margin_below_threshold <= 1.0
    assert result.breakeven_rate > 0
    assert result.simulated_rates.shape == (sample_order.n_simulations,)

    ordered = [result.margin_pct_percentiles[f"P{p}"] for p in (5, 10, 25, 50, 75, 90, 95)]
    assert ordered == sorted(ordered)


def test_result_is_reproducible_with_same_seed(static_provider, sample_order):
    engine = MarginRiskEngine(static_provider)
    first = engine.run(sample_order)
    second = engine.run(sample_order)

    assert first.vulnerability_score == second.vulnerability_score
    np.testing.assert_array_equal(first.simulated_rates, second.simulated_rates)


def test_sobol_sampling_method_runs_end_to_end(static_provider, sample_order):
    engine = MarginRiskEngine(static_provider, sampling_method=SamplingMethod.SOBOL)
    result = engine.run(sample_order)
    assert np.all(np.isfinite(result.simulated_rates))


def test_median_rate_close_to_spot_under_low_volatility(make_series, reference_order_date):
    series = make_series(base_rate=10.0, n_days=200, annual_sigma=0.05, end_date=reference_order_date, seed=1)
    provider = StaticFxDataProvider(series)
    order = OrderInput(
        amount_foreign=50_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=30),
        target_margin_pct=0.25,
        n_simulations=50_000,
        seed=11,
    )
    result = MarginRiskEngine(provider).run(order)
    assert result.rate_percentiles["P50"] == pytest.approx(result.spot_rate_order_date, rel=0.02)


def test_higher_volatility_and_longer_horizon_increase_risk(make_series, reference_order_date):
    low_vol = make_series(base_rate=10.0, n_days=200, annual_sigma=0.03, end_date=reference_order_date, seed=5)
    high_vol = make_series(base_rate=10.0, n_days=200, annual_sigma=0.35, end_date=reference_order_date, seed=5)

    def order(offset):
        return OrderInput(
            amount_foreign=100_000.0,
            foreign_currency="USD",
            domestic_currency="MAD",
            order_date=reference_order_date,
            delivery_date=reference_order_date + dt.timedelta(days=offset),
            target_margin_pct=0.10,
            n_simulations=20_000,
            seed=3,
        )

    low_risk = MarginRiskEngine(StaticFxDataProvider(low_vol)).run(order(30))
    high_risk = MarginRiskEngine(StaticFxDataProvider(high_vol)).run(order(180))

    assert high_risk.vulnerability_score > low_risk.vulnerability_score
    assert high_risk.probability_margin_below_threshold >= low_risk.probability_margin_below_threshold


def test_target_margin_path_computes_revenue_from_spot(static_provider, reference_order_date):
    order = OrderInput(
        amount_foreign=10_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=45),
        target_margin_pct=0.20,
        n_simulations=5000,
        seed=1,
    )
    result = MarginRiskEngine(static_provider).run(order)

    expected_revenue = order.amount_foreign * result.spot_rate_order_date * 1.20
    assert result.breakeven_rate == pytest.approx(expected_revenue / order.amount_foreign)
    assert result.budgeted_margin_pct == pytest.approx(0.20 / 1.20, rel=1e-6)


def test_expected_revenue_path_uses_provided_value(static_provider, reference_order_date):
    order = OrderInput(
        amount_foreign=10_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=45),
        expected_revenue_domestic=150_000.0,
        n_simulations=5000,
        seed=1,
    )
    result = MarginRiskEngine(static_provider).run(order)
    assert result.breakeven_rate == pytest.approx(15.0)


def test_propagates_insufficient_data_error(make_series, reference_order_date):
    series = make_series(base_rate=10.0, n_days=200, annual_sigma=0.1, end_date=reference_order_date, seed=1)
    provider = StaticFxDataProvider(series)
    order = OrderInput(
        amount_foreign=10_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date + dt.timedelta(days=3650),
        delivery_date=reference_order_date + dt.timedelta(days=3660),
        target_margin_pct=0.2,
    )
    with pytest.raises(InsufficientDataError):
        MarginRiskEngine(provider).run(order)


def test_mad_recommendation_mentions_office_des_changes(static_provider, sample_order):
    result = MarginRiskEngine(static_provider).run(sample_order)
    assert "Office des Changes" in result.recommendation


def test_cip_drift_makes_expected_terminal_rate_match_forward(make_series, reference_order_date):
    series = make_series(base_rate=10.0, n_days=200, annual_sigma=0.08, end_date=reference_order_date, seed=4)
    provider = StaticFxDataProvider(series)
    order = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=180),
        target_margin_pct=0.15,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=100_000,
        seed=9,
    )
    result = MarginRiskEngine(provider).run(order)

    assert result.cip_drift == pytest.approx(-0.02)
    assert result.expected_terminal_rate < result.spot_rate_order_date
    assert result.simulated_rates.mean() == pytest.approx(result.expected_terminal_rate, rel=0.01)


def test_hedge_analysis_is_populated_and_consistent(static_provider, sample_order):
    result = MarginRiskEngine(static_provider).run(sample_order)
    hedge = result.hedge

    assert 0.0 <= hedge.optimal_hedge_ratio <= 1.0
    assert 0.0 <= hedge.probability_unhedged_beats_hedge <= 1.0
    assert hedge.optimal_hedge_cvar_margin_pct >= hedge.unhedged_cvar_margin_pct
    reconstructed = 1.0 - (sample_order.amount_foreign / (result.breakeven_rate * sample_order.amount_foreign)) * hedge.theoretical_forward_rate
    assert hedge.hedged_margin_pct == pytest.approx(reconstructed)


def test_instrument_comparison_is_populated(static_provider, sample_order):
    result = MarginRiskEngine(static_provider).run(sample_order)
    instruments = {o.instrument: o for o in result.instrument_comparison}

    assert set(instruments) == {
        HedgeInstrument.NONE,
        HedgeInstrument.FORWARD,
        HedgeInstrument.OPTION,
        HedgeInstrument.COLLAR,
    }
    forward = instruments[HedgeInstrument.FORWARD]
    assert forward.cvar_margin_pct == pytest.approx(forward.worst_case_margin_pct)
    for hedged in (HedgeInstrument.FORWARD, HedgeInstrument.OPTION, HedgeInstrument.COLLAR):
        assert instruments[hedged].cvar_margin_pct >= instruments[HedgeInstrument.NONE].cvar_margin_pct


@pytest.mark.parametrize("model", list(VolatilityModel))
def test_engine_runs_with_each_volatility_model(static_provider, sample_order, model):
    result = MarginRiskEngine(static_provider, volatility_model=model).run(sample_order)
    assert result.annualized_volatility > 0


def test_student_t_engine_widens_downside_tail(make_series, reference_order_date):
    series = make_series(base_rate=10.0, n_days=220, annual_sigma=0.2, end_date=reference_order_date, seed=8)
    provider = StaticFxDataProvider(series)
    order = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=180),
        target_margin_pct=0.10,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=100_000,
        seed=5,
    )
    normal = MarginRiskEngine(provider).run(order)
    heavy = MarginRiskEngine(
        provider, return_distribution=ReturnDistribution.STUDENT_T, student_t_dof=4.0
    ).run(order)
    assert heavy.expected_shortfall_margin_pct < normal.expected_shortfall_margin_pct


def test_jump_diffusion_engine_runs(static_provider, sample_order):
    engine = MarginRiskEngine(
        static_provider, jumps=JumpParams(intensity_annual=2.0, mean_log_jump=-0.03, std_log_jump=0.05)
    )
    result = engine.run(sample_order)
    assert np.all(np.isfinite(result.simulated_rates))


def test_heston_market_model_runs_end_to_end(static_provider, sample_order):
    from core.models.enums import MarketModel

    result = MarginRiskEngine(static_provider, market_model=MarketModel.HESTON).run(sample_order)
    assert np.all(np.isfinite(result.simulated_rates))
    assert np.all(result.simulated_rates > 0)
    assert len(result.instrument_comparison) == 4
    assert 0 <= result.vulnerability_score <= 100


def test_heston_produces_fatter_tails_than_gbm(make_series, reference_order_date):
    from core.models.enums import MarketModel
    from core.models.heston import HestonParams

    series = make_series(base_rate=10.0, n_days=220, annual_sigma=0.2, end_date=reference_order_date, seed=8)
    provider = StaticFxDataProvider(series)
    order = OrderInput(
        amount_foreign=100_000.0, foreign_currency="USD", domestic_currency="MAD",
        order_date=reference_order_date, delivery_date=reference_order_date + dt.timedelta(days=180),
        target_margin_pct=0.10, domestic_rate=0.03, foreign_rate=0.05, n_simulations=100_000, seed=5,
    )

    def kurtosis(rates):
        z = (rates - rates.mean()) / rates.std()
        return float(np.mean(z**4))

    gbm = MarginRiskEngine(provider).run(order)
    heston = MarginRiskEngine(
        provider,
        market_model=MarketModel.HESTON,
        heston_params=HestonParams(v0=0.04, kappa=2.0, theta=0.04, xi=0.8, rho=-0.5),
    ).run(order)
    assert kurtosis(heston.simulated_rates) > kurtosis(gbm.simulated_rates)


def test_full_hedge_recommended_under_high_risk(make_series, reference_order_date):
    series = make_series(base_rate=10.0, n_days=200, annual_sigma=0.40, end_date=reference_order_date, seed=6)
    provider = StaticFxDataProvider(series)
    order = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=180),
        target_margin_pct=0.10,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=40_000,
        seed=2,
    )
    result = MarginRiskEngine(provider).run(order)

    assert result.hedge.optimal_hedge_ratio == pytest.approx(1.0)
    assert result.hedge.cvar_improvement_pct > 0
