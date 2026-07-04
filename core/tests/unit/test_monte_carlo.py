from __future__ import annotations

import numpy as np
import pytest

from core.models.enums import SamplingMethod
from core.models.exceptions import SimulationError
from core.models.monte_carlo import simulate_terminal_rates, standard_error


def test_returns_array_of_requested_length():
    result = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.15, horizon_years=0.5, n_sims=5000, seed=1
    )
    assert result.shape == (5000,)
    assert np.all(result > 0)
    assert np.all(np.isfinite(result))


def test_reproducible_with_same_seed():
    a = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.15, horizon_years=0.5, n_sims=2000, seed=99
    )
    b = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.15, horizon_years=0.5, n_sims=2000, seed=99
    )
    np.testing.assert_array_equal(a, b)


def test_different_seeds_produce_different_paths():
    a = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.15, horizon_years=0.5, n_sims=2000, seed=1
    )
    b = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.15, horizon_years=0.5, n_sims=2000, seed=2
    )
    assert not np.array_equal(a, b)


def test_mean_log_return_converges_to_drift():
    spot, sigma, horizon = 10.0, 0.2, 1.0
    result = simulate_terminal_rates(
        spot=spot, sigma_annual=sigma, horizon_years=horizon, n_sims=200_000, seed=123
    )
    log_returns = np.log(result / spot)
    assert log_returns.mean() == pytest.approx(-0.5 * sigma**2 * horizon, abs=0.01)
    assert log_returns.std(ddof=1) == pytest.approx(sigma * np.sqrt(horizon), rel=0.03)


def test_nonzero_drift_shifts_expected_terminal_rate_to_forward():
    spot, sigma, horizon, mu = 10.0, 0.2, 1.0, -0.02
    result = simulate_terminal_rates(
        spot=spot, sigma_annual=sigma, horizon_years=horizon, n_sims=400_000, mu_annual=mu, seed=7
    )
    assert result.mean() == pytest.approx(spot * np.exp(mu * horizon), rel=0.01)


def test_sobol_method_accepts_enum_and_string():
    from_enum = simulate_terminal_rates(
        spot=10.0,
        sigma_annual=0.2,
        horizon_years=1.0,
        n_sims=4096,
        seed=1,
        method=SamplingMethod.SOBOL,
    )
    from_string = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.2, horizon_years=1.0, n_sims=4096, seed=1, method="sobol"
    )
    np.testing.assert_array_equal(from_enum, from_string)


def test_sobol_mean_is_accurate():
    spot, sigma, horizon, n = 10.0, 0.2, 1.0, 4096
    sobol = simulate_terminal_rates(
        spot=spot,
        sigma_annual=sigma,
        horizon_years=horizon,
        n_sims=n,
        seed=1,
        method=SamplingMethod.SOBOL,
    )
    assert sobol.mean() == pytest.approx(spot, rel=0.02)


def test_antithetic_variates_reduce_variance_of_mean_estimate():
    spot, sigma, horizon, n, trials = 10.0, 0.25, 1.0, 1000, 300
    plain_means = []
    anti_means = []
    for trial in range(trials):
        plain = simulate_terminal_rates(
            spot=spot,
            sigma_annual=sigma,
            horizon_years=horizon,
            n_sims=n,
            seed=trial,
            antithetic=False,
        )
        anti = simulate_terminal_rates(
            spot=spot,
            sigma_annual=sigma,
            horizon_years=horizon,
            n_sims=n,
            seed=trial,
            antithetic=True,
        )
        plain_means.append(plain.mean())
        anti_means.append(anti.mean())

    assert np.var(anti_means) < np.var(plain_means)


def test_extreme_parameters_stay_finite_due_to_clipping():
    result = simulate_terminal_rates(
        spot=10.0,
        sigma_annual=5.0,
        horizon_years=5.0,
        n_sims=10_000,
        seed=3,
        method=SamplingMethod.SOBOL,
    )
    assert np.all(np.isfinite(result))
    assert np.all(result > 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"spot": 0, "sigma_annual": 0.1, "horizon_years": 1, "n_sims": 1000},
        {"spot": -5, "sigma_annual": 0.1, "horizon_years": 1, "n_sims": 1000},
        {"spot": 10, "sigma_annual": -0.1, "horizon_years": 1, "n_sims": 1000},
        {"spot": 10, "sigma_annual": 0.1, "horizon_years": 0, "n_sims": 1000},
        {"spot": 10, "sigma_annual": 0.1, "horizon_years": -1, "n_sims": 1000},
        {"spot": 10, "sigma_annual": 0.1, "horizon_years": 1, "n_sims": 1},
        {"spot": 10, "sigma_annual": 0.1, "horizon_years": 1, "n_sims": 2_000_000},
    ],
)
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(SimulationError):
        simulate_terminal_rates(**kwargs)


def test_rejects_unknown_sampling_method():
    with pytest.raises(ValueError):
        simulate_terminal_rates(
            spot=10.0, sigma_annual=0.1, horizon_years=1.0, n_sims=1000, method="unknown"
        )


def test_standard_error_matches_manual_computation():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    expected = values.std(ddof=1) / np.sqrt(5)
    assert standard_error(values) == pytest.approx(expected)


def test_standard_error_requires_at_least_two_values():
    with pytest.raises(SimulationError):
        standard_error(np.array([1.0]))
