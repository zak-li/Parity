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


@dataclass(frozen=True, slots=True)
class ChristoffersenResult:
    n_observations: int
    n00: int
    n01: int
    n10: int
    n11: int
    pi0: float
    pi1: float
    likelihood_ratio: float
    p_value: float
    rejected: bool


def christoffersen_independence_test(
    exceedance_indicator: np.ndarray,
    significance: float = settings.KUPIEC_SIGNIFICANCE,
) -> ChristoffersenResult:
    """Christoffersen (1998) test for independence of VaR exceedances.

    Tests whether exceedances are unclustered in time (H0: pi0 == pi1).
    """
    ind = np.asarray(exceedance_indicator, dtype=int)
    if ind.ndim != 1 or len(ind) < 2:
        raise InsufficientDataError("Indicator series must have at least 2 observations.")

    i_prev = ind[:-1]
    i_curr = ind[1:]

    n00 = int(np.sum((i_prev == 0) & (i_curr == 0)))
    n01 = int(np.sum((i_prev == 0) & (i_curr == 1)))
    n10 = int(np.sum((i_prev == 1) & (i_curr == 0)))
    n11 = int(np.sum((i_prev == 1) & (i_curr == 1)))

    n0 = n00 + n01
    n1 = n10 + n11

    pi0 = n01 / n0 if n0 > 0 else 0.0
    pi1 = n11 / n1 if n1 > 0 else 0.0
    pi = (n01 + n11) / (n0 + n1) if (n0 + n1) > 0 else 0.0

    # Log-likelihood under null (independence)
    log_l0 = (n00 + n10) * np.log(max(1.0 - pi, 1e-12)) + (n01 + n11) * np.log(max(pi, 1e-12))

    # Log-likelihood under alternative (first-order Markov dependence)
    log_l1 = (
        n00 * np.log(max(1.0 - pi0, 1e-12))
        + n01 * np.log(max(pi0, 1e-12))
        + n10 * np.log(max(1.0 - pi1, 1e-12))
        + n11 * np.log(max(pi1, 1e-12))
    )

    lr_stat = float(max(2.0 * (log_l1 - log_l0), 0.0))
    p_value = float(chi2.sf(lr_stat, df=1))

    return ChristoffersenResult(
        n_observations=len(ind),
        n00=n00,
        n01=n01,
        n10=n10,
        n11=n11,
        pi0=pi0,
        pi1=pi1,
        likelihood_ratio=lr_stat,
        p_value=p_value,
        rejected=p_value < significance,
    )


def kupiec_pof_test(
    n_observations: int,
    n_exceedances: int,
    alpha: float,
    significance: float = settings.KUPIEC_SIGNIFICANCE,
) -> KupiecResult:
    """Kupiec proportion-of-failures test for VaR calibration.

    Likelihood-ratio test that the observed exceedance rate matches ``alpha``;
    ``rejected`` is True when the p-value falls below ``significance``.
    """
    if n_observations <= 0:
        raise InsufficientDataError("The number of observations must be strictly positive.")
    if not (0 <= n_exceedances <= n_observations):
        raise InsufficientDataError("The number of exceedances is inconsistent.")
    if not (0.0 < alpha < 1.0):
        raise InsufficientDataError("The alpha level must be in (0, 1).")

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
        raise InsufficientDataError("The series is too short for the requested backtest window.")
    z = norm.ppf(alpha)
    rolling = returns.rolling(window)
    threshold = (rolling.mean() + z * rolling.std(ddof=1)).shift(1)
    valid = threshold.notna()
    exceedances = int((returns[valid] < threshold[valid]).sum())
    return kupiec_pof_test(int(valid.sum()), exceedances, alpha, significance)


@dataclass(frozen=True, slots=True)
class ESBacktestResult:
    n_observations: int
    n_exceedances: int
    alpha: float
    z2_statistic: float
    p_value: float
    rejected: bool


def _z2_statistic(
    realized: np.ndarray, quantile: np.ndarray, es_magnitude: np.ndarray, alpha: float
) -> float:
    """Acerbi-Szekely (2014) Test 2 statistic on realized returns.

    ``quantile`` is the (negative) VaR return level used to flag exceptions;
    ``es_magnitude`` is the positive Expected Shortfall loss. Under the null the
    statistic is centred on zero; it turns negative when realized tail losses
    exceed the forecast Expected Shortfall.
    """
    exceptions = realized < quantile
    if not exceptions.any():
        return 0.0
    contributions = np.where(exceptions, realized / es_magnitude, 0.0)
    return float(contributions.sum() / (realized.size * alpha) + 1.0)


def backtest_expected_shortfall(
    series: pd.Series,
    alpha: float,
    window: int,
    n_scenarios: int = 1000,
    significance: float = settings.KUPIEC_SIGNIFICANCE,
    seed: int | None = 0,
) -> ESBacktestResult:
    """Acerbi-Szekely Test 2 for the Expected Shortfall of a rolling normal model.

    The null distribution of the statistic is obtained by Monte Carlo under the
    predictive (rolling normal) model; the p-value is the left-tail probability,
    so a small p-value flags an ES that understates realized tail losses.
    """
    if not (0.0 < alpha < 1.0):
        raise InsufficientDataError("The alpha level must be in (0, 1).")
    log_returns = np.log(series / series.shift(1)).dropna()
    if len(log_returns) <= window:
        raise InsufficientDataError("The series is too short for the requested backtest window.")

    rolling = log_returns.rolling(window)
    mean = rolling.mean().shift(1)
    std = rolling.std(ddof=1).shift(1)
    valid = mean.notna() & std.notna() & (std > 0)
    mu = mean[valid].to_numpy()
    sigma = std[valid].to_numpy()
    realized = log_returns[valid].to_numpy()
    if realized.size == 0:
        raise InsufficientDataError("No valid forecast window for the ES backtest.")

    z = float(norm.ppf(alpha))
    quantile = mu + z * sigma
    es_magnitude = -(mu - sigma * float(norm.pdf(z)) / alpha)

    observed = _z2_statistic(realized, quantile, es_magnitude, alpha)
    n_exceptions = int((realized < quantile).sum())

    rng = np.random.default_rng(seed)
    null_stats = np.empty(n_scenarios)
    for i in range(n_scenarios):
        sample = rng.normal(mu, sigma)
        null_stats[i] = _z2_statistic(sample, quantile, es_magnitude, alpha)
    p_value = float((null_stats <= observed).mean())

    return ESBacktestResult(
        n_observations=int(realized.size),
        n_exceedances=n_exceptions,
        alpha=alpha,
        z2_statistic=observed,
        p_value=p_value,
        rejected=p_value < significance,
    )
