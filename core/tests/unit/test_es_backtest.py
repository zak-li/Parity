from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.models.backtesting import ESBacktestResult, backtest_expected_shortfall
from core.models.exceptions import InsufficientDataError


def _normal_series(sigma=0.01, n=1500, seed=3):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0, sigma, n)
    return pd.Series(100.0 * np.exp(np.cumsum(returns)))


def test_well_calibrated_normal_model_is_not_rejected():
    result = backtest_expected_shortfall(_normal_series(), alpha=0.05, window=250, n_scenarios=400)
    assert isinstance(result, ESBacktestResult)
    assert result.p_value > 0.05
    assert not result.rejected
    assert abs(result.z2_statistic) < 0.5


def test_z2_statistic_signals_underestimated_es():
    from core.models.backtesting import _z2_statistic

    n, alpha = 2000, 0.05
    k = int(alpha * n)
    quantile = np.full(n, -0.02)  # VaR return level
    es = np.full(n, 0.03)  # positive ES magnitude
    realized = np.full(n, 0.001)  # ordinary days: no exception

    calibrated = realized.copy()
    calibrated[:k] = -0.03  # tail losses exactly equal to ES -> statistic ~ 0
    assert _z2_statistic(calibrated, quantile, es, alpha) == pytest.approx(0.0, abs=1e-9)

    underestimated = realized.copy()
    underestimated[:k] = -0.06  # tail losses twice the ES -> strongly negative
    assert _z2_statistic(underestimated, quantile, es, alpha) < -0.5


def test_deterministic_with_seed():
    a = backtest_expected_shortfall(
        _normal_series(), alpha=0.05, window=250, n_scenarios=200, seed=5
    )
    b = backtest_expected_shortfall(
        _normal_series(), alpha=0.05, window=250, n_scenarios=200, seed=5
    )
    assert a.z2_statistic == b.z2_statistic
    assert a.p_value == b.p_value


def test_rejects_bad_alpha_and_short_series():
    with pytest.raises(InsufficientDataError):
        backtest_expected_shortfall(_normal_series(), alpha=1.5, window=250)
    with pytest.raises(InsufficientDataError):
        backtest_expected_shortfall(_normal_series(n=100), alpha=0.05, window=250)
