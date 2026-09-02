from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

import numpy as np
from scipy.special import ndtri
from scipy.stats import qmc
from scipy.stats import t as student_t

from ..config import settings
from .enums import ReturnDistribution, SamplingMethod
from .exceptions import SimulationError


@dataclass(frozen=True, slots=True)
class JumpParams:
    intensity_annual: float
    mean_log_jump: float
    std_log_jump: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.intensity_annual) or self.intensity_annual < 0:
            raise SimulationError("Jump intensity must be finite and non-negative.")
        if not np.isfinite(self.mean_log_jump):
            raise SimulationError("Mean jump size must be finite.")
        if not np.isfinite(self.std_log_jump) or self.std_log_jump < 0:
            raise SimulationError("Jump standard deviation must be finite and non-negative.")

    def compensator(self) -> float:
        return float(np.exp(self.mean_log_jump + 0.5 * self.std_log_jump**2) - 1.0)


def _standardized_shocks(
    n_sims: int,
    rng: np.random.Generator,
    antithetic: bool,
    distribution: ReturnDistribution,
    dof: float | None,
) -> np.ndarray:
    draw: Callable[..., Any]
    if distribution is ReturnDistribution.NORMAL:
        draw = rng.standard_normal
        scale = 1.0
    else:
        if dof is None or dof <= settings.MIN_STUDENT_T_DOF:
            raise SimulationError(
                f"Student-t degrees of freedom must be > {settings.MIN_STUDENT_T_DOF}."
            )
        draw = partial(rng.standard_t, dof)
        scale = np.sqrt((dof - 2.0) / dof)

    if antithetic and n_sims > 1:
        half = (n_sims + 1) // 2
        base = np.asarray(draw(half))
        shocks = np.concatenate((base, -base))[:n_sims]
    else:
        shocks = np.asarray(draw(n_sims))
    return shocks * scale


def _sobol_shocks(
    n_sims: int, seed: int | None, distribution: ReturnDistribution, dof: float | None
) -> np.ndarray:
    sampler = qmc.Sobol(d=1, scramble=True, seed=seed)
    exponent = int(np.ceil(np.log2(max(n_sims, 2))))
    uniforms = sampler.random_base2(m=exponent)[:n_sims, 0]
    np.clip(uniforms, np.finfo(float).tiny, 1.0 - np.finfo(float).eps, out=uniforms)
    if distribution is ReturnDistribution.NORMAL:
        return ndtri(uniforms)
    if dof is None or dof <= settings.MIN_STUDENT_T_DOF:
        raise SimulationError(
            f"Student-t degrees of freedom must be > {settings.MIN_STUDENT_T_DOF}."
        )
    return student_t.ppf(uniforms, dof) * np.sqrt((dof - 2.0) / dof)


def _jump_component(
    jumps: JumpParams, horizon_years: float, n_sims: int, rng: np.random.Generator
) -> tuple[np.ndarray, float]:
    counts = rng.poisson(jumps.intensity_annual * horizon_years, size=n_sims)
    gaussian = rng.standard_normal(n_sims)
    total = counts * jumps.mean_log_jump + np.sqrt(counts) * jumps.std_log_jump * gaussian
    drift_adjustment = -jumps.intensity_annual * jumps.compensator() * horizon_years
    return total, drift_adjustment


def simulate_terminal_rates(
    spot: float,
    sigma_annual: float,
    horizon_years: float,
    n_sims: int,
    mu_annual: float = 0.0,
    seed: int | None = None,
    method: SamplingMethod = SamplingMethod.PSEUDO_RANDOM,
    antithetic: bool = True,
    distribution: ReturnDistribution = ReturnDistribution.NORMAL,
    student_t_dof: float | None = None,
    jumps: JumpParams | None = None,
) -> np.ndarray:
    """Simulate delivery-date FX rates under a risk-neutral GBM.

    ``S_T = spot * exp((mu - 0.5*sigma^2)*T + sigma*sqrt(T)*Z)`` with optional
    Student-t shocks, Merton jumps, antithetic variates, or Sobol sampling.
    Returns an array of ``n_sims`` terminal rates.
    """
    if not np.isfinite(spot) or spot <= 0:
        raise SimulationError("The spot rate must be strictly positive.")
    if not np.isfinite(sigma_annual) or sigma_annual < 0:
        raise SimulationError("Annualized volatility cannot be negative.")
    if not np.isfinite(horizon_years) or horizon_years <= 0:
        raise SimulationError("The simulation horizon must be strictly positive.")
    if not (settings.MIN_N_SIMULATIONS <= n_sims <= settings.MAX_N_SIMULATIONS):
        raise SimulationError(
            f"The number of simulations must be between {settings.MIN_N_SIMULATIONS} "
            f"and {settings.MAX_N_SIMULATIONS}."
        )

    method = SamplingMethod(method)
    distribution = ReturnDistribution(distribution)
    rng = np.random.default_rng(seed)
    if method is SamplingMethod.PSEUDO_RANDOM:
        shocks = _standardized_shocks(n_sims, rng, antithetic, distribution, student_t_dof)
    else:
        shocks = _sobol_shocks(n_sims, seed, distribution, student_t_dof)

    exponent = (mu_annual - 0.5 * sigma_annual**2) * horizon_years
    exponent = exponent + sigma_annual * np.sqrt(horizon_years) * shocks

    if jumps is not None:
        jump_total, drift_adjustment = _jump_component(jumps, horizon_years, n_sims, rng)
        exponent += jump_total + drift_adjustment

    np.clip(
        exponent, -settings.MAX_LOG_GROWTH_EXPONENT, settings.MAX_LOG_GROWTH_EXPONENT, out=exponent
    )
    return spot * np.exp(exponent)


def standard_error(values: np.ndarray) -> float:
    n = values.size
    if n < 2:
        raise SimulationError("At least 2 values are required to estimate the standard error.")
    return float(values.std(ddof=1) / np.sqrt(n))
