from __future__ import annotations

import pytest

from core.models.instruments import (
    garman_kohlhagen_call,
    garman_kohlhagen_greeks,
    garman_kohlhagen_put,
)

S, K, RD, RF, SIG, T = 10.0, 10.2, 0.03, 0.05, 0.15, 0.5
PRICERS = {"call": garman_kohlhagen_call, "put": garman_kohlhagen_put}


@pytest.mark.parametrize("kind", ["call", "put"])
def test_greeks_match_finite_differences(kind):
    price = PRICERS[kind]
    g = garman_kohlhagen_greeks(S, K, RD, RF, SIG, T, kind)
    h = 1e-5
    assert g.delta == pytest.approx(
        (price(S + h, K, RD, RF, SIG, T) - price(S - h, K, RD, RF, SIG, T)) / (2 * h), abs=1e-4
    )
    assert g.vega == pytest.approx(
        (price(S, K, RD, RF, SIG + h, T) - price(S, K, RD, RF, SIG - h, T)) / (2 * h), abs=1e-3
    )
    assert g.rho_domestic == pytest.approx(
        (price(S, K, RD + h, RF, SIG, T) - price(S, K, RD - h, RF, SIG, T)) / (2 * h), abs=1e-3
    )
    assert g.rho_foreign == pytest.approx(
        (price(S, K, RD, RF + h, SIG, T) - price(S, K, RD, RF - h, SIG, T)) / (2 * h), abs=1e-3
    )
    assert g.theta == pytest.approx(
        -(price(S, K, RD, RF, SIG, T + h) - price(S, K, RD, RF, SIG, T - h)) / (2 * h), abs=1e-3
    )


def test_call_and_put_delta_differ_by_discount_factor():
    import numpy as np

    call = garman_kohlhagen_greeks(S, K, RD, RF, SIG, T, "call")
    put = garman_kohlhagen_greeks(S, K, RD, RF, SIG, T, "put")
    assert call.delta - put.delta == pytest.approx(np.exp(-RF * T), abs=1e-9)
    assert call.gamma == pytest.approx(put.gamma, abs=1e-12)
    assert call.vega == pytest.approx(put.vega, abs=1e-12)


def test_greeks_reject_degenerate_inputs():
    with pytest.raises(ValueError):
        garman_kohlhagen_greeks(S, K, RD, RF, 0.0, T)
    with pytest.raises(ValueError):
        garman_kohlhagen_greeks(S, K, RD, RF, SIG, 0.0)
