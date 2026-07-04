from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import settings
from .exceptions import SimulationError


@dataclass(frozen=True, slots=True)
class HestonParams:
    v0: float
    kappa: float
    theta: float
    xi: float
    rho: float

    def __post_init__(self) -> None:
        for name, value in (("v0", self.v0), ("theta", self.theta)):
            if not np.isfinite(value) or value <= 0:
                raise SimulationError(f"Le paramètre Heston {name} doit être strictement positif.")
        if not np.isfinite(self.kappa) or self.kappa <= 0:
            raise SimulationError("La vitesse de retour à la moyenne (kappa) doit être positive.")
        if not np.isfinite(self.xi) or self.xi <= 0:
            raise SimulationError("La volatilité de la volatilité (xi) doit être positive.")
        if not np.isfinite(self.rho) or not (-1.0 <= self.rho <= 1.0):
            raise SimulationError("La corrélation spot/vol (rho) doit être dans [-1, 1].")

    @property
    def satisfies_feller(self) -> bool:
        return 2.0 * self.kappa * self.theta >= self.xi**2


def default_params_from_volatility(
    annualized_volatility: float,
    kappa: float = settings.HESTON_DEFAULT_KAPPA,
    xi: float = settings.HESTON_DEFAULT_XI,
    rho: float = settings.HESTON_DEFAULT_RHO,
) -> HestonParams:
    variance = max(float(annualized_volatility) ** 2, 1e-8)
    return HestonParams(v0=variance, kappa=kappa, theta=variance, xi=xi, rho=rho)


def _resolve_steps(horizon_years: float) -> int:
    target = int(round(horizon_years * settings.HESTON_STEPS_PER_YEAR))
    return int(np.clip(target, settings.HESTON_MIN_STEPS, settings.HESTON_MAX_STEPS))


def simulate_heston_terminal_rates(
    spot: float,
    horizon_years: float,
    n_sims: int,
    params: HestonParams,
    mu_annual: float = 0.0,
    seed: int | None = None,
    n_steps: int | None = None,
    antithetic: bool = True,
) -> np.ndarray:
    if not np.isfinite(spot) or spot <= 0:
        raise SimulationError("Le taux au comptant doit être strictement positif.")
    if not np.isfinite(horizon_years) or horizon_years <= 0:
        raise SimulationError("L'horizon de simulation doit être strictement positif.")
    if not (settings.MIN_N_SIMULATIONS <= n_sims <= settings.MAX_N_SIMULATIONS):
        raise SimulationError(
            f"Le nombre de simulations doit être compris entre {settings.MIN_N_SIMULATIONS} "
            f"et {settings.MAX_N_SIMULATIONS}."
        )

    steps = n_steps if n_steps is not None else _resolve_steps(horizon_years)
    if steps <= 0:
        raise SimulationError("Le nombre de pas de temps doit être strictement positif.")
    dt = horizon_years / steps
    sqrt_dt = np.sqrt(dt)
    rho_comp = np.sqrt(1.0 - params.rho**2)

    rng = np.random.default_rng(seed)
    half = (n_sims + 1) // 2 if antithetic else n_sims

    log_spot = np.full(half, np.log(spot))
    variance = np.full(half, params.v0)
    log_spot_anti = np.full(half, np.log(spot)) if antithetic else None
    variance_anti = np.full(half, params.v0) if antithetic else None

    for _ in range(steps):
        z1 = rng.standard_normal(half)
        z2 = params.rho * z1 + rho_comp * rng.standard_normal(half)
        log_spot, variance = _euler_step(log_spot, variance, z1, z2, mu_annual, params, dt, sqrt_dt)
        if antithetic:
            log_spot_anti, variance_anti = _euler_step(
                log_spot_anti, variance_anti, -z1, -z2, mu_annual, params, dt, sqrt_dt
            )

    terminal = np.exp(log_spot)
    if antithetic:
        assert log_spot_anti is not None
        terminal = np.concatenate((terminal, np.exp(log_spot_anti)))[:n_sims]
    np.clip(terminal, 0.0, spot * np.exp(settings.MAX_LOG_GROWTH_EXPONENT), out=terminal)
    return terminal


def _euler_step(log_spot, variance, z1, z2, mu_annual, params, dt, sqrt_dt):
    v_plus = np.maximum(variance, 0.0)
    sqrt_v = np.sqrt(v_plus)
    next_variance = (
        variance + params.kappa * (params.theta - v_plus) * dt + params.xi * sqrt_v * sqrt_dt * z2
    )
    next_log_spot = log_spot + (mu_annual - 0.5 * v_plus) * dt + sqrt_v * sqrt_dt * z1
    return next_log_spot, next_variance
