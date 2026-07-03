from __future__ import annotations

import numpy as np
import pytest

from core.models.exceptions import SimulationError
from core.models.heston import (
    HestonParams,
    default_params_from_volatility,
    simulate_heston_terminal_rates,
)
from core.models.monte_carlo import simulate_terminal_rates


def _kurtosis(sample):
    z = (sample - sample.mean()) / sample.std()
    return float(np.mean(z**4))


def _params(**overrides):
    base = dict(v0=0.04, kappa=2.0, theta=0.04, xi=0.4, rho=-0.3)
    base.update(overrides)
    return HestonParams(**base)


def test_terminal_rates_positive_and_finite():
    result = simulate_heston_terminal_rates(10.0, 0.5, 20_000, _params(), seed=1)
    assert result.shape == (20_000,)
    assert np.all(result > 0)
    assert np.all(np.isfinite(result))


def test_martingale_mean_matches_forward():
    spot, mu, horizon = 10.0, -0.02, 0.5
    result = simulate_heston_terminal_rates(spot, horizon, 200_000, _params(), mu_annual=mu, seed=2)
    assert result.mean() == pytest.approx(spot * np.exp(mu * horizon), rel=0.01)


def test_realized_volatility_tracks_initial_variance():
    spot, horizon = 10.0, 1.0
    result = simulate_heston_terminal_rates(spot, horizon, 200_000, _params(v0=0.04, theta=0.04), seed=3)
    realized = np.log(result / spot).std(ddof=1) / np.sqrt(horizon)
    assert realized == pytest.approx(0.20, rel=0.1)


def test_stochastic_volatility_produces_fatter_tails_than_gbm():
    spot, horizon = 10.0, 1.0
    heston = simulate_heston_terminal_rates(spot, horizon, 200_000, _params(xi=0.6), seed=4)
    gbm = simulate_terminal_rates(
        spot=spot, sigma_annual=0.2, horizon_years=horizon, n_sims=200_000, seed=4
    )
    assert _kurtosis(np.log(heston / spot)) > _kurtosis(np.log(gbm / spot))


def test_negative_rho_skews_distribution():
    result = simulate_heston_terminal_rates(10.0, 1.0, 200_000, _params(rho=-0.7, xi=0.6), seed=5)
    log_returns = np.log(result / 10.0)
    z = (log_returns - log_returns.mean()) / log_returns.std()
    assert float(np.mean(z**3)) < 0


def test_reproducible_with_seed():
    a = simulate_heston_terminal_rates(10.0, 0.5, 10_000, _params(), seed=9)
    b = simulate_heston_terminal_rates(10.0, 0.5, 10_000, _params(), seed=9)
    np.testing.assert_array_equal(a, b)


def test_default_params_from_volatility_uses_variance():
    params = default_params_from_volatility(0.25)
    assert params.v0 == pytest.approx(0.0625)
    assert params.theta == pytest.approx(0.0625)


def test_feller_condition_flag():
    assert _params(kappa=3.0, theta=0.04, xi=0.2).satisfies_feller
    assert not _params(kappa=0.5, theta=0.02, xi=0.6).satisfies_feller


def test_explicit_steps_override():
    result = simulate_heston_terminal_rates(10.0, 0.5, 5_000, _params(), seed=1, n_steps=10)
    assert np.all(result > 0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"v0": 0.0}, {"v0": -0.1}, {"theta": 0.0}, {"kappa": 0.0},
        {"kappa": -1.0}, {"xi": 0.0}, {"rho": 1.5}, {"rho": -1.5},
    ],
)
def test_params_validation(overrides):
    with pytest.raises(SimulationError):
        _params(**overrides)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"spot": 0.0, "horizon_years": 0.5, "n_sims": 5000},
        {"spot": 10.0, "horizon_years": 0.0, "n_sims": 5000},
        {"spot": 10.0, "horizon_years": 0.5, "n_sims": 10},
    ],
)
def test_simulate_rejects_invalid_inputs(kwargs):
    with pytest.raises(SimulationError):
        simulate_heston_terminal_rates(params=_params(), **kwargs)
