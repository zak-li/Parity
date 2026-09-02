from __future__ import annotations

import numpy as np
import pytest

from core.models.enums import HedgeInstrument
from core.models.instruments import (
    compare_instruments,
    garman_kohlhagen_call,
    garman_kohlhagen_put,
    participating_forward_alpha,
    participating_forward_strike,
)


def test_participating_forward_strike_zero_cost():
    spot = 1.05
    rd = 0.02
    rf = 0.04
    sigma = 0.12
    t = 0.5
    forward = spot * np.exp((rd - rf) * t)
    participation_rate = 0.50

    strike = participating_forward_strike(
        spot=spot,
        forward=forward,
        rd=rd,
        rf=rf,
        sigma=sigma,
        t=t,
        participation_rate=participation_rate,
    )

    assert strike > forward
    call_prem = garman_kohlhagen_call(spot, strike, rd, rf, sigma, t)
    put_prem = garman_kohlhagen_put(spot, strike, rd, rf, sigma, t)
    net_cost = call_prem - (1.0 - participation_rate) * put_prem
    assert abs(net_cost) < 1e-6


def test_participating_forward_alpha_recovery():
    spot = 1.05
    rd = 0.02
    rf = 0.04
    sigma = 0.12
    t = 0.5
    forward = spot * np.exp((rd - rf) * t)

    strike = participating_forward_strike(
        spot=spot,
        forward=forward,
        rd=rd,
        rf=rf,
        sigma=sigma,
        t=t,
        participation_rate=0.60,
    )

    recovered_alpha = participating_forward_alpha(spot, strike, rd, rf, sigma, t)
    assert recovered_alpha == pytest.approx(0.60, abs=1e-5)


def test_participating_forward_invalid_participation():
    with pytest.raises(ValueError):
        participating_forward_strike(1.0, 1.0, 0.02, 0.04, 0.1, 0.5, participation_rate=0.0)

    with pytest.raises(ValueError):
        participating_forward_strike(1.0, 1.0, 0.02, 0.04, 0.1, 0.5, participation_rate=1.0)


def test_participating_forward_outcome_in_compare_instruments():
    rates = np.array([0.90, 0.95, 1.00, 1.05, 1.10, 1.20, 1.30])
    outcomes = compare_instruments(
        revenue=120_000.0,
        amount_foreign=100_000.0,
        spot=1.0,
        forward=1.0,
        sigma_annual=0.15,
        domestic_rate=0.02,
        foreign_rate=0.02,
        horizon_years=0.5,
        simulated_rates=rates,
        participation_rate=0.50,
    )

    par = next(o for o in outcomes if o.instrument is HedgeInstrument.PARTICIPATING_FORWARD)
    assert par.upfront_premium_domestic == 0.0
    # Worst case margin is capped by the strike, strictly better than unhedged worst case
    unhedged = next(o for o in outcomes if o.instrument is HedgeInstrument.NONE)
    assert par.worst_case_margin_pct > unhedged.worst_case_margin_pct
    assert par.cvar_margin_pct > unhedged.cvar_margin_pct
