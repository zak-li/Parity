from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..config import settings
from .exceptions import InsufficientDataError
from .volatility import _fit_garch, _garch_variance_path


@dataclass(frozen=True, slots=True)
class DccResult:
    correlation: np.ndarray
    a: float
    b: float
    currencies: list[str]


def _standardized_residuals(returns: np.ndarray) -> np.ndarray:
    try:
        omega, alpha, beta, _ = _fit_garch(returns)
        variance = _garch_variance_path(returns, omega, alpha, beta)
    except (InsufficientDataError, ValueError, FloatingPointError):
        variance = np.full_like(returns, returns.var())
    variance = np.where(variance > 0, variance, returns.var())
    return returns / np.sqrt(variance)


def _dcc_negative_log_likelihood(
    params: np.ndarray, residuals: np.ndarray, q_bar: np.ndarray
) -> float:
    a, b = params
    if a < 0 or b < 0 or a + b >= 0.999:
        return 1e12
    n_obs, dimension = residuals.shape
    q = q_bar.copy()
    log_likelihood = 0.0
    for t in range(n_obs):
        diag = np.sqrt(np.diag(q))
        r = q / np.outer(diag, diag)
        try:
            sign, logdet = np.linalg.slogdet(r)
            if sign <= 0:
                return 1e12
            solved = np.linalg.solve(r, residuals[t])
        except np.linalg.LinAlgError:
            return 1e12
        log_likelihood += logdet + residuals[t] @ solved
        outer = np.outer(residuals[t], residuals[t])
        q = (1.0 - a - b) * q_bar + a * outer + b * q
    return 0.5 * float(log_likelihood)


def estimate_dcc(returns: pd.DataFrame) -> DccResult:
    currencies = list(returns.columns)
    frame = returns.dropna()
    if len(frame) < 10 or len(currencies) < 2:
        raise InsufficientDataError("Insufficient overlapping history to fit a DCC-GARCH.")

    residuals = np.column_stack([_standardized_residuals(frame[c].to_numpy()) for c in currencies])
    q_bar = np.corrcoef(residuals, rowvar=False)
    if not np.all(np.isfinite(q_bar)):
        raise InsufficientDataError("Unconditional correlation cannot be estimated.")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = minimize(
            _dcc_negative_log_likelihood,
            np.array([settings.DCC_DEFAULT_A, settings.DCC_DEFAULT_B]),
            args=(residuals, q_bar),
            method="SLSQP",
            bounds=((0.0, 0.5), (0.0, 0.98)),
            constraints=({"type": "ineq", "fun": lambda p: 0.999 - p[0] - p[1]},),
            options={"maxiter": settings.GARCH_MAX_ITER, "ftol": 1e-8},
        )
    a, b = result.x if result.success else (settings.DCC_DEFAULT_A, settings.DCC_DEFAULT_B)

    q = q_bar.copy()
    for t in range(residuals.shape[0]):
        outer = np.outer(residuals[t], residuals[t])
        q = (1.0 - a - b) * q_bar + a * outer + b * q
    diag = np.sqrt(np.diag(q))
    correlation = q / np.outer(diag, diag)
    np.fill_diagonal(correlation, 1.0)
    return DccResult(correlation=correlation, a=float(a), b=float(b), currencies=currencies)
