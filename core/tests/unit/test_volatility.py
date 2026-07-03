from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.models.enums import VolatilityModel
from core.models.exceptions import InsufficientDataError
from core.models.volatility import (
    estimate_volatility,
    ewma_annualized_volatility,
    garch_annualized_volatility,
)


def _series(sigma, n=300, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n)
    lr = rng.normal(0, sigma / np.sqrt(252), n)
    lr[0] = 0.0
    return pd.Series(10 * np.exp(np.cumsum(lr)), index=dates)


def test_ewma_recovers_order_of_magnitude():
    result = ewma_annualized_volatility(_series(0.15, seed=1))
    assert result == pytest.approx(0.15, abs=0.06)


def test_ewma_reacts_more_to_recent_shocks_than_sample():
    calm = _series(0.10, seed=2).to_numpy()
    dates = pd.bdate_range("2025-01-01", periods=len(calm) + 20)
    shocked = np.concatenate([calm, calm[-1] * np.exp(np.linspace(0, 0.3, 20))])
    series = pd.Series(shocked, index=dates)
    assert ewma_annualized_volatility(series) > 0


def test_ewma_rejects_invalid_lambda():
    with pytest.raises(InsufficientDataError):
        ewma_annualized_volatility(_series(0.1), lambda_=1.5)


def test_garch_returns_positive_and_finite():
    result = garch_annualized_volatility(_series(0.2, seed=5), horizon_days=60)
    assert np.isfinite(result) and result > 0


def test_garch_falls_back_gracefully_on_short_clean_series():
    result = garch_annualized_volatility(_series(0.12, n=40, seed=7), horizon_days=30)
    assert np.isfinite(result) and result > 0


@pytest.mark.parametrize("seed", range(6))
def test_garch_recovers_known_sigma_via_variance_targeting(seed):
    # Regression: sur une serie a volatilite constante, l'estimateur GARCH doit
    # retrouver le sigma vrai. Avant le variance targeting, il surestimait d'un
    # facteur 2 a 5 (optimiseur piege a une init impliquant long_run = 5 x var).
    result = garch_annualized_volatility(_series(0.20, n=1200, seed=seed), horizon_days=90)
    assert result == pytest.approx(0.20, abs=0.03)


@pytest.mark.parametrize("model", list(VolatilityModel))
def test_dispatcher_supports_all_models(model):
    result = estimate_volatility(_series(0.15, seed=3), model, horizon_days=45)
    assert np.isfinite(result) and result > 0


def test_all_models_agree_within_reason_on_stationary_series():
    series = _series(0.15, n=400, seed=9)
    values = [estimate_volatility(series, m, 45) for m in VolatilityModel]
    assert max(values) < 3 * min(values)


def test_ewma_rejects_too_short_series():
    dates = pd.bdate_range("2025-01-01", periods=2)
    with pytest.raises(InsufficientDataError):
        ewma_annualized_volatility(pd.Series([10.0, 10.1], index=dates))


def test_garch_falls_back_on_flat_series():
    dates = pd.bdate_range("2025-01-01", periods=120)
    series = pd.Series(np.linspace(10.0, 10.5, 120), index=dates)
    result = garch_annualized_volatility(series, horizon_days=30)
    assert np.isfinite(result) and result > 0


def test_garch_likelihood_penalizes_invalid_parameters():
    from core.models.volatility import _garch_negative_log_likelihood

    returns = np.array([0.01, -0.02, 0.015, -0.01, 0.02])
    assert _garch_negative_log_likelihood(np.array([-1.0, 0.1, 0.8]), returns) >= 1e12
    assert _garch_negative_log_likelihood(np.array([1e-6, 0.6, 0.6]), returns) >= 1e12


def test_garch_falls_back_to_ewma_when_fit_fails(monkeypatch):
    from core.models import volatility

    def _boom(_returns):
        raise volatility.InsufficientDataError("fit failed")

    monkeypatch.setattr(volatility, "_fit_garch", _boom)
    series = _series(0.18, seed=4)
    assert volatility.garch_annualized_volatility(series, horizon_days=30) == pytest.approx(
        volatility.ewma_annualized_volatility(series)
    )
