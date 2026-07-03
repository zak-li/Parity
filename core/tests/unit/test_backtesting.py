from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.models.backtesting import KupiecResult, backtest_parametric_var, kupiec_pof_test
from core.models.exceptions import InsufficientDataError


def test_well_calibrated_model_is_not_rejected():
    result = kupiec_pof_test(n_observations=1000, n_exceedances=50, alpha=0.05)
    assert isinstance(result, KupiecResult)
    assert result.likelihood_ratio == pytest.approx(0.0, abs=1e-6)
    assert not result.rejected


def test_too_many_exceedances_is_rejected():
    result = kupiec_pof_test(n_observations=1000, n_exceedances=150, alpha=0.05)
    assert result.observed_exceedance_rate == pytest.approx(0.15)
    assert result.rejected


def test_zero_exceedances_branch():
    result = kupiec_pof_test(n_observations=500, n_exceedances=0, alpha=0.05)
    assert result.likelihood_ratio > 0
    assert result.p_value >= 0.0


def test_all_exceedances_branch():
    result = kupiec_pof_test(n_observations=100, n_exceedances=100, alpha=0.05)
    assert result.likelihood_ratio > 0


@pytest.mark.parametrize(
    "n,x,alpha",
    [(0, 0, 0.05), (100, 150, 0.05), (100, 5, 0.0), (100, 5, 1.0), (100, -1, 0.05)],
)
def test_rejects_invalid_inputs(n, x, alpha):
    with pytest.raises(InsufficientDataError):
        kupiec_pof_test(n, x, alpha)


def test_backtest_parametric_var_on_synthetic_series():
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2024-01-01", periods=800)
    lr = rng.normal(0, 0.01, 800)
    lr[0] = 0.0
    series = pd.Series(10 * np.exp(np.cumsum(lr)), index=dates)

    result = backtest_parametric_var(series, alpha=0.05, window=250)
    assert result.n_observations == 800 - 1 - 250
    assert 0.0 <= result.observed_exceedance_rate <= 1.0


def test_backtest_rejects_too_short_series():
    dates = pd.bdate_range("2024-01-01", periods=50)
    series = pd.Series(np.linspace(10, 11, 50), index=dates)
    with pytest.raises(InsufficientDataError):
        backtest_parametric_var(series, alpha=0.05, window=250)
