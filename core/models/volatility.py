from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.signal import lfilter

from ..config import settings
from .enums import VolatilityModel
from .exceptions import InsufficientDataError
from .market_stats import annualized_volatility


def _log_returns(series: pd.Series) -> np.ndarray:
    returns = np.log(series / series.shift(1)).dropna().to_numpy()
    if returns.size < 3:
        raise InsufficientDataError(
            "Au moins 3 points de données sont nécessaires pour estimer la volatilité."
        )
    return returns


def ewma_annualized_volatility(
    series: pd.Series,
    lambda_: float = settings.EWMA_LAMBDA,
    trading_days_per_year: int = settings.TRADING_DAYS_PER_YEAR,
) -> float:
    if not (0.0 < lambda_ < 1.0):
        raise InsufficientDataError("Le facteur de lissage EWMA doit être dans (0, 1).")
    returns = _log_returns(series)
    n = returns.size
    weights = lambda_ ** np.arange(n - 1, -1, -1)
    variance = float(
        lambda_**n * np.var(returns, ddof=1) + (1.0 - lambda_) * weights @ (returns * returns)
    )
    if not np.isfinite(variance) or variance <= 0:
        raise InsufficientDataError("Volatilité EWMA non estimable à partir des données fournies.")
    return float(np.sqrt(variance * trading_days_per_year))


def _garch_variance_path(returns: np.ndarray, omega: float, alpha: float, beta: float) -> np.ndarray:
    driver = np.empty_like(returns)
    driver[0] = returns.var()
    driver[1:] = omega + alpha * returns[:-1] ** 2
    return lfilter([1.0], [1.0, -beta], driver)


def _garch_negative_log_likelihood(params: np.ndarray, returns: np.ndarray) -> float:
    omega, alpha, beta = params
    if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1.0:
        return 1e12
    variance = _garch_variance_path(returns, omega, alpha, beta)
    if not np.all(np.isfinite(variance)) or np.any(variance <= 0):
        return 1e12
    return 0.5 * float(np.sum(np.log(2 * np.pi * variance) + returns**2 / variance))


def _fit_garch(returns: np.ndarray) -> tuple[float, float, float, float]:
    sample_var = returns.var()
    initial = np.array([sample_var * 0.1, 0.08, 0.90])
    bounds = ((1e-12, None), (0.0, 1.0), (0.0, 1.0))
    constraint = {"type": "ineq", "fun": lambda p: 0.999 - p[1] - p[2]}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = minimize(
            _garch_negative_log_likelihood,
            initial,
            args=(returns,),
            method="SLSQP",
            bounds=bounds,
            constraints=(constraint,),
            options={"maxiter": settings.GARCH_MAX_ITER, "ftol": 1e-9},
        )
    omega, alpha, beta = result.x
    if not result.success or alpha + beta >= 1.0 or omega <= 0:
        raise InsufficientDataError("Ajustement GARCH non convergent.")
    last_variance = _garch_variance_path(returns, omega, alpha, beta)[-1]
    return float(omega), float(alpha), float(beta), float(last_variance)


def garch_annualized_volatility(
    series: pd.Series,
    horizon_days: int,
    trading_days_per_year: int = settings.TRADING_DAYS_PER_YEAR,
) -> float:
    returns = _log_returns(series)
    horizon_days = max(1, int(horizon_days))
    try:
        omega, alpha, beta, last_variance = _fit_garch(returns)
    except (InsufficientDataError, ValueError, FloatingPointError):
        return ewma_annualized_volatility(series, trading_days_per_year=trading_days_per_year)

    persistence = alpha + beta
    long_run = omega / (1.0 - persistence)
    steps = np.arange(horizon_days)
    next_variance = omega + alpha * returns[-1] ** 2 + beta * last_variance
    forecasts = long_run + (persistence**steps) * (next_variance - long_run)
    average_variance = float(np.mean(forecasts))
    if not np.isfinite(average_variance) or average_variance <= 0:
        return ewma_annualized_volatility(series, trading_days_per_year=trading_days_per_year)
    return float(np.sqrt(average_variance * trading_days_per_year))


def estimate_volatility(
    series: pd.Series,
    model: VolatilityModel,
    horizon_days: int,
    trading_days_per_year: int = settings.TRADING_DAYS_PER_YEAR,
) -> float:
    model = VolatilityModel(model)
    if model is VolatilityModel.HISTORICAL:
        return annualized_volatility(series, trading_days_per_year)
    if model is VolatilityModel.EWMA:
        return ewma_annualized_volatility(series, trading_days_per_year=trading_days_per_year)
    return garch_annualized_volatility(series, horizon_days, trading_days_per_year)
