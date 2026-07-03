from __future__ import annotations

import numpy as np
import pytest

from core.models.enums import ReturnDistribution, SamplingMethod
from core.models.exceptions import SimulationError
from core.models.monte_carlo import JumpParams, simulate_terminal_rates


def _kurtosis(x):
    z = (x - x.mean()) / x.std()
    return float(np.mean(z**4))


def test_student_t_has_fatter_tails_than_normal():
    common = dict(spot=10.0, sigma_annual=0.2, horizon_years=1.0, n_sims=200_000, seed=1)
    normal = simulate_terminal_rates(**common, distribution=ReturnDistribution.NORMAL)
    heavy = simulate_terminal_rates(
        **common, distribution=ReturnDistribution.STUDENT_T, student_t_dof=4.0
    )
    assert _kurtosis(np.log(heavy / 10.0)) > _kurtosis(np.log(normal / 10.0))


def test_student_t_matches_target_volatility():
    result = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.2, horizon_years=1.0, n_sims=200_000, seed=2,
        distribution=ReturnDistribution.STUDENT_T, student_t_dof=6.0,
    )
    assert np.log(result / 10.0).std(ddof=1) == pytest.approx(0.2, rel=0.08)


def test_student_t_requires_valid_dof():
    with pytest.raises(SimulationError):
        simulate_terminal_rates(
            spot=10.0, sigma_annual=0.2, horizon_years=1.0, n_sims=2000,
            distribution=ReturnDistribution.STUDENT_T, student_t_dof=2.0,
        )


def test_student_t_works_with_sobol():
    result = simulate_terminal_rates(
        spot=10.0, sigma_annual=0.2, horizon_years=1.0, n_sims=4096, seed=1,
        method=SamplingMethod.SOBOL, distribution=ReturnDistribution.STUDENT_T, student_t_dof=5.0,
    )
    assert np.all(np.isfinite(result)) and np.all(result > 0)


def test_sobol_student_t_requires_valid_dof():
    with pytest.raises(SimulationError):
        simulate_terminal_rates(
            spot=10.0, sigma_annual=0.2, horizon_years=1.0, n_sims=2048, seed=1,
            method=SamplingMethod.SOBOL, distribution=ReturnDistribution.STUDENT_T, student_t_dof=1.0,
        )


def test_jumps_increase_dispersion():
    common = dict(spot=10.0, sigma_annual=0.15, horizon_years=1.0, n_sims=200_000, seed=3)
    without = simulate_terminal_rates(**common)
    with_jumps = simulate_terminal_rates(
        **common, jumps=JumpParams(intensity_annual=3.0, mean_log_jump=-0.05, std_log_jump=0.08)
    )
    assert with_jumps.std() > without.std()


def test_jump_diffusion_preserves_forward_mean():
    spot, mu, horizon = 10.0, -0.02, 1.0
    result = simulate_terminal_rates(
        spot=spot, sigma_annual=0.15, horizon_years=horizon, n_sims=400_000, mu_annual=mu, seed=4,
        jumps=JumpParams(intensity_annual=2.0, mean_log_jump=-0.04, std_log_jump=0.06),
    )
    assert result.mean() == pytest.approx(spot * np.exp(mu * horizon), rel=0.02)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"intensity_annual": -1.0, "mean_log_jump": 0.0, "std_log_jump": 0.1},
        {"intensity_annual": 1.0, "mean_log_jump": float("nan"), "std_log_jump": 0.1},
        {"intensity_annual": 1.0, "mean_log_jump": 0.0, "std_log_jump": -0.1},
    ],
)
def test_jump_params_validation(kwargs):
    with pytest.raises(SimulationError):
        JumpParams(**kwargs)
