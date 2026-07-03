from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.models.dcc import estimate_dcc
from core.models.exceptions import InsufficientDataError


def _frame(n=400, seed=0, coupling=0.0):
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 0.01, n)
    b = coupling * a + (1 - coupling) * rng.normal(0, 0.01, n)
    return pd.DataFrame({"USD": a, "EUR": b})


def test_returns_valid_correlation_matrix():
    result = estimate_dcc(_frame(coupling=0.5))
    corr = result.correlation
    assert corr.shape == (2, 2)
    assert np.allclose(np.diag(corr), 1.0)
    assert np.allclose(corr, corr.T)
    assert np.all(np.linalg.eigvalsh(corr) > -1e-9)


def test_parameters_are_stationary():
    result = estimate_dcc(_frame(coupling=0.4))
    assert result.a >= 0
    assert result.b >= 0
    assert result.a + result.b < 1.0


def test_captures_stronger_correlation_for_more_coupled_series():
    weak = estimate_dcc(_frame(coupling=0.1, seed=1)).correlation[0, 1]
    strong = estimate_dcc(_frame(coupling=0.9, seed=1)).correlation[0, 1]
    assert strong > weak


def test_reacts_to_recent_comovement_regime():
    rng = np.random.default_rng(3)
    n = 500
    a = rng.normal(0, 0.01, n)
    independent = rng.normal(0, 0.01, n)
    b = independent.copy()
    b[n // 2 :] = 0.85 * a[n // 2 :] + 0.15 * independent[n // 2 :]
    result = estimate_dcc(pd.DataFrame({"USD": a, "EUR": b}))
    assert result.correlation[0, 1] > 0.5


def test_currencies_preserved_in_order():
    result = estimate_dcc(_frame(coupling=0.3))
    assert result.currencies == ["USD", "EUR"]


def test_rejects_insufficient_history():
    with pytest.raises(InsufficientDataError):
        estimate_dcc(_frame(n=5))


def test_rejects_single_series():
    rng = np.random.default_rng(0)
    with pytest.raises(InsufficientDataError):
        estimate_dcc(pd.DataFrame({"USD": rng.normal(0, 0.01, 400)}))
