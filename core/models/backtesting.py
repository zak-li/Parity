from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

from ..config import settings
from .exceptions import InsufficientDataError


@dataclass(frozen=True, slots=True)
class KupiecResult:
    n_observations: int
    n_exceedances: int
    expected_exceedance_rate: float
    observed_exceedance_rate: float
    likelihood_ratio: float
    p_value: float
    rejected: bool


def kupiec_pof_test(
    n_observations: int,
    n_exceedances: int,
    alpha: float,
    significance: float = settings.KUPIEC_SIGNIFICANCE,
) -> KupiecResult:
    if n_observations <= 0:
        raise InsufficientDataError("Le nombre d'observations doit être strictement positif.")
    if not (0 <= n_exceedances <= n_observations):
        raise InsufficientDataError("Le nombre de dépassements est incohérent.")
    if not (0.0 < alpha < 1.0):
        raise InsufficientDataError("Le niveau alpha doit être dans (0, 1).")

    n, x, p = n_observations, n_exceedances, alpha
    observed = x / n

    if x == 0:
        likelihood_ratio = -2.0 * n * np.log(1.0 - p)
    elif x == n:
        likelihood_ratio = -2.0 * n * np.log(p)
    else:
        log_null = (n - x) * np.log(1.0 - p) + x * np.log(p)
        log_alt = (n - x) * np.log(1.0 - observed) + x * np.log(observed)
        likelihood_ratio = -2.0 * (log_null - log_alt)

    likelihood_ratio = float(max(likelihood_ratio, 0.0))
    p_value = float(chi2.sf(likelihood_ratio, df=1))
    return KupiecResult(
        n_observations=n,
        n_exceedances=x,
        expected_exceedance_rate=p,
        observed_exceedance_rate=observed,
        likelihood_ratio=likelihood_ratio,
        p_value=p_value,
        rejected=p_value < significance,
    )


def backtest_parametric_var(
    series: pd.Series,
    alpha: float,
    window: int,
    significance: float = settings.KUPIEC_SIGNIFICANCE,
) -> KupiecResult:
    returns = pd.Series(np.log(series / series.shift(1)).dropna().to_numpy())
    if len(returns) <= window:
        raise InsufficientDataError(
            "La série est trop courte pour la fenêtre de backtest demandée."
        )
    z = norm.ppf(alpha)
    rolling = returns.rolling(window)
    threshold = (rolling.mean() + z * rolling.std(ddof=1)).shift(1)
    valid = threshold.notna()
    exceedances = int((returns[valid] < threshold[valid]).sum())
    return kupiec_pof_test(int(valid.sum()), exceedances, alpha, significance)
