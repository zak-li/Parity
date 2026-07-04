from __future__ import annotations

import numpy as np
import pytest

from core.models.enums import HedgeInstrument
from core.models.instruments import (
    compare_instruments,
    garman_kohlhagen_call,
    garman_kohlhagen_put,
    zero_cost_collar_cap,
)


def test_put_call_parity_holds():
    spot, strike, rd, rf, sigma, t = 10.0, 10.5, 0.03, 0.05, 0.2, 0.5
    call = garman_kohlhagen_call(spot, strike, rd, rf, sigma, t)
    put = garman_kohlhagen_put(spot, strike, rd, rf, sigma, t)
    parity = spot * np.exp(-rf * t) - strike * np.exp(-rd * t)
    assert call - put == pytest.approx(parity, abs=1e-9)


def test_option_prices_are_non_negative():
    assert garman_kohlhagen_call(10, 11, 0.02, 0.04, 0.15, 0.25) >= 0
    assert garman_kohlhagen_put(10, 9, 0.02, 0.04, 0.15, 0.25) >= 0


def test_zero_time_gives_intrinsic_value():
    assert garman_kohlhagen_call(11, 10, 0.03, 0.03, 0.2, 0.0) == pytest.approx(1.0)
    assert garman_kohlhagen_put(9, 10, 0.03, 0.03, 0.2, 0.0) == pytest.approx(1.0)


def test_zero_cost_collar_cap_equalizes_premiums():
    spot, floor, rd, rf, sigma, t = 10.0, 9.5, 0.03, 0.05, 0.2, 0.5
    cap = zero_cost_collar_cap(spot, floor, rd, rf, sigma, t)
    call = garman_kohlhagen_call(spot, cap, rd, rf, sigma, t)
    put = garman_kohlhagen_put(spot, floor, rd, rf, sigma, t)
    assert cap > floor
    assert call == pytest.approx(put, abs=1e-6)


def _comparison(sigma=0.25, seed=0, n=40000):
    rng = np.random.default_rng(seed)
    forward = 9.8
    rates = 10.0 * np.exp(rng.normal(-0.02, sigma, n))
    return compare_instruments(
        revenue=1_150_000.0,
        amount_foreign=100_000.0,
        spot=10.0,
        forward=forward,
        sigma_annual=sigma,
        domestic_rate=0.03,
        foreign_rate=0.05,
        horizon_years=0.5,
        simulated_rates=rates,
        min_acceptable_margin_pct=0.0,
    )


def test_comparison_returns_all_four_instruments():
    outcomes = _comparison()
    assert tuple(o.instrument for o in outcomes) == (
        HedgeInstrument.NONE,
        HedgeInstrument.FORWARD,
        HedgeInstrument.OPTION,
        HedgeInstrument.COLLAR,
    )


def test_forward_is_deterministic():
    outcomes = {o.instrument: o for o in _comparison()}
    forward = outcomes[HedgeInstrument.FORWARD]
    assert forward.cvar_margin_pct == pytest.approx(forward.worst_case_margin_pct)
    assert forward.cvar_margin_pct == pytest.approx(forward.expected_margin_pct)


def test_hedges_improve_tail_over_unhedged():
    outcomes = {o.instrument: o for o in _comparison()}
    unhedged = outcomes[HedgeInstrument.NONE]
    for instrument in (HedgeInstrument.FORWARD, HedgeInstrument.OPTION, HedgeInstrument.COLLAR):
        assert outcomes[instrument].cvar_margin_pct > unhedged.cvar_margin_pct


def test_option_charges_premium_but_keeps_upside():
    outcomes = {o.instrument: o for o in _comparison()}
    option = outcomes[HedgeInstrument.OPTION]
    forward = outcomes[HedgeInstrument.FORWARD]
    assert option.upfront_premium_domestic > 0
    assert option.best_case_margin_pct > forward.best_case_margin_pct


def test_mc_pricer_matches_discounted_expected_payoff():
    from core.models.instruments import mc_option_pricer

    rates = np.array([8.0, 9.0, 10.0, 11.0, 12.0])
    pricer = mc_option_pricer(rates, domestic_rate=0.0, horizon_years=1.0)
    assert pricer("call", 10.0) == pytest.approx(np.maximum(rates - 10.0, 0).mean())
    assert pricer("put", 10.0) == pytest.approx(np.maximum(10.0 - rates, 0).mean())


def test_mc_pricer_recovers_smile_from_heavy_tailed_sample():
    from core.models.heston import HestonParams, simulate_heston_terminal_rates
    from core.models.instruments import garman_kohlhagen_call, mc_option_pricer

    spot, rd, rf, t = 10.0, 0.0, 0.0, 1.0
    sample = simulate_heston_terminal_rates(
        spot, t, 200_000, HestonParams(v0=0.04, kappa=2.0, theta=0.04, xi=0.8, rho=-0.6), seed=1
    )
    pricer = mc_option_pricer(sample, rd, t)
    otm_put = pricer("put", 8.0)
    flat_vol_put = garman_kohlhagen_call(spot, 8.0, rd, rf, 0.2, t) - (spot - 8.0)
    assert otm_put > max(flat_vol_put, 0.0)


def test_comparison_accepts_custom_pricer():
    from core.models.instruments import mc_option_pricer

    rng = np.random.default_rng(0)
    rates = 10.0 * np.exp(rng.normal(-0.02, 0.2, 40_000))
    pricer = mc_option_pricer(rates, 0.03, 0.5)
    outcomes = compare_instruments(
        revenue=1_150_000.0,
        amount_foreign=100_000.0,
        spot=10.0,
        forward=9.8,
        sigma_annual=0.2,
        domestic_rate=0.03,
        foreign_rate=0.05,
        horizon_years=0.5,
        simulated_rates=rates,
        option_pricer=pricer,
    )
    option = next(o for o in outcomes if o.instrument is HedgeInstrument.OPTION)
    assert option.upfront_premium_domestic > 0


def test_zero_cost_collar_raises_when_no_solution_in_bounds():
    with pytest.raises(ValueError):
        zero_cost_collar_cap(10.0, 0.001, 0.03, 0.05, 0.2, 0.5)


def test_collar_falls_back_when_zero_cost_unsolvable():
    rng = np.random.default_rng(1)
    rates = 10.0 * np.exp(rng.normal(-0.02, 0.2, 5000))
    outcomes = {
        o.instrument: o
        for o in compare_instruments(
            revenue=1_150_000.0,
            amount_foreign=100_000.0,
            spot=10.0,
            forward=0.02,
            sigma_annual=0.2,
            domestic_rate=0.03,
            foreign_rate=0.05,
            horizon_years=0.5,
            simulated_rates=rates,
        )
    }
    assert HedgeInstrument.COLLAR in outcomes
