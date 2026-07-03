from __future__ import annotations

import numpy as np

from .exceptions import SimulationError


def cip_drift(domestic_rate: float, foreign_rate: float) -> float:
    if not (np.isfinite(domestic_rate) and np.isfinite(foreign_rate)):
        raise SimulationError("Les taux d'intérêt doivent être des nombres finis.")
    return domestic_rate - foreign_rate


def theoretical_forward_rate(
    spot: float, domestic_rate: float, foreign_rate: float, horizon_years: float
) -> float:
    if not np.isfinite(spot) or spot <= 0:
        raise SimulationError("Le taux au comptant doit être strictement positif.")
    if not np.isfinite(horizon_years) or horizon_years <= 0:
        raise SimulationError("L'horizon doit être strictement positif.")
    return spot * float(np.exp(cip_drift(domestic_rate, foreign_rate) * horizon_years))


def forward_points(spot: float, forward: float) -> float:
    return forward - spot
