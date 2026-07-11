from __future__ import annotations

import numpy as np

from .exceptions import SimulationError


def cip_drift(domestic_rate: float, foreign_rate: float) -> float:
    """Risk-neutral FX drift under covered interest rate parity (``r_d - r_f``)."""
    if not (np.isfinite(domestic_rate) and np.isfinite(foreign_rate)):
        raise SimulationError("Interest rates must be finite numbers.")
    return domestic_rate - foreign_rate


def theoretical_forward_rate(
    spot: float, domestic_rate: float, foreign_rate: float, horizon_years: float
) -> float:
    """CIP forward rate ``S · exp((r_d - r_f) · T)`` for ``horizon_years`` T."""
    if not np.isfinite(spot) or spot <= 0:
        raise SimulationError("The spot rate must be strictly positive.")
    if not np.isfinite(horizon_years) or horizon_years <= 0:
        raise SimulationError("The horizon must be strictly positive.")
    return spot * float(np.exp(cip_drift(domestic_rate, foreign_rate) * horizon_years))


def forward_points(spot: float, forward: float) -> float:
    return forward - spot
