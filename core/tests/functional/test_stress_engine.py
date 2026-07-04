from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core.app.risk_engine import MarginRiskEngine
from core.models.models import OrderInput
from core.models.stress import StressReport, canonical_scenarios


@pytest.fixture
def order(reference_order_date):
    return OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=90),
        target_margin_pct=0.15,
        min_acceptable_margin_pct=0.0,
        domestic_rate=0.03,
        foreign_rate=0.05,
        seed=1,
    )


def test_stress_report_structure(static_provider, order):
    result = MarginRiskEngine(static_provider).stress_test(order)

    assert isinstance(result, StressReport)
    assert len(result.scenarios) >= len(canonical_scenarios())
    names = [s.scenario for s in result.scenarios]
    assert any("Choc" in n for n in names)


def test_adverse_shock_reduces_margin_below_budget(static_provider, order):
    result = MarginRiskEngine(static_provider).stress_test(order)
    severe = next(s for s in result.scenarios if "sévère" in s.scenario)
    assert severe.margin_pct < result.budgeted_margin_pct
    assert severe.margin_pct_change < 0


def test_reverse_stress_is_consistent(static_provider, order):
    result = MarginRiskEngine(static_provider).stress_test(order)
    reverse = result.reverse_stress
    assert reverse.breaking_rate > result.spot
    assert reverse.required_rate_move_pct > 0


def test_crisis_replay_included_when_history_available(reference_order_date, order):
    class CrisisProvider:
        def __init__(self):
            np.random.default_rng(0)

        def get_historical_series(self, base, quote, start, end):
            dates = pd.bdate_range(start=pd.Timestamp(start), end=pd.Timestamp(end))
            if len(dates) < 5:
                dates = pd.bdate_range(end=pd.Timestamp(end), periods=200)
            rng = np.random.default_rng(abs(hash((start.year,))) % 1000)
            lr = rng.normal(0, 0.2 / np.sqrt(252), len(dates))
            lr[0] = 0.0
            return pd.Series(10 * np.exp(np.cumsum(lr)), index=dates)

    report = MarginRiskEngine(CrisisProvider()).stress_test(order)
    names = [s.scenario for s in report.scenarios]
    assert any("Rejeu" in n for n in names)


def test_crisis_replay_skipped_gracefully_when_unavailable(static_provider, order):
    report = MarginRiskEngine(static_provider).stress_test(order)
    assert isinstance(report, StressReport)
    assert len(report.scenarios) >= 4


def test_recent_history_scenario_skipped_when_window_too_short(
    static_provider, reference_order_date
):
    short = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=reference_order_date,
        delivery_date=reference_order_date + dt.timedelta(days=200),
        target_margin_pct=0.15,
        lookback_days=30,
        seed=1,
    )
    report = MarginRiskEngine(static_provider).stress_test(short)
    names = [s.scenario for s in report.scenarios]
    assert all("Pire mouvement historique" not in n for n in names)
    assert len(report.scenarios) == len(canonical_scenarios())
