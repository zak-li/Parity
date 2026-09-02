from __future__ import annotations

import pytest

from core.models.instruments import garman_kohlhagen_call
from core.models.smile import FxVolatilitySmile


def test_smile_recovers_atm_vol():
    smile = FxVolatilitySmile(atm_vol=0.10, rr_25=0.02, bf_25=0.005)
    assert smile.vol_by_delta(0.50) == pytest.approx(0.10)


def test_smile_recovers_rr_and_bf():
    atm = 0.12
    rr = 0.025
    bf = 0.008
    smile = FxVolatilitySmile(atm_vol=atm, rr_25=rr, bf_25=bf)

    vol_25c = smile.vol_by_delta(0.25)
    vol_75c = smile.vol_by_delta(0.75)

    assert (vol_25c - vol_75c) == pytest.approx(rr)
    assert (0.5 * (vol_25c + vol_75c) - atm) == pytest.approx(bf)


def test_smile_invalid_parameters():
    with pytest.raises(ValueError):
        FxVolatilitySmile(atm_vol=-0.05)

    with pytest.raises(ValueError):
        FxVolatilitySmile(atm_vol=0.10, bf_25=-0.01)


def test_smile_pricer_reflects_skew():
    spot, rd, rf, t = 1.0, 0.02, 0.03, 0.5
    # High RR25 (skewed towards out-of-the-money calls)
    skewed_smile = FxVolatilitySmile(atm_vol=0.10, rr_25=0.04, bf_25=0.01)
    pricer = skewed_smile.build_pricer(spot, rd, rf, t)

    otm_strike = 1.08
    smile_call_price = pricer("call", otm_strike)
    flat_call_price = garman_kohlhagen_call(spot, otm_strike, rd, rf, 0.10, t)

    # With positive RR25, OTM call vol is higher, so call price is higher
    assert smile_call_price > flat_call_price
