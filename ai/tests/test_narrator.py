from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from ai import build_narrator
from ai.groq_narrator import GroqNarrator, NullNarrator, _build_prompt
from core.app.risk_engine import MarginRiskEngine
from core.io.fx.static import StaticFxDataProvider
from core.models.models import OrderInput


@pytest.fixture
def result():
    rng = np.random.default_rng(3)
    end = dt.date(2026, 1, 15)
    dates = pd.bdate_range(end=pd.Timestamp(end), periods=200)
    lr = rng.normal(0, 0.15 / np.sqrt(252), 200)
    lr[0] = 0.0
    series = pd.Series(10 * np.exp(np.cumsum(lr)), index=dates)
    order = OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency="MAD",
        order_date=end,
        delivery_date=end + dt.timedelta(days=90),
        target_margin_pct=0.15,
        domestic_rate=0.03,
        foreign_rate=0.05,
        n_simulations=5_000,
        seed=7,
    )
    return MarginRiskEngine(StaticFxDataProvider(series)).run(order)


def test_prompt_contains_key_indicators(result):
    prompt = _build_prompt(result)
    assert "USD/MAD" in prompt
    assert "Vulnerability score" in prompt
    assert "Recommended optimal hedge" in prompt


def test_null_narrator_returns_none(result):
    assert NullNarrator().narrate(result) is None


def test_build_narrator_without_key_returns_null(monkeypatch):
    monkeypatch.delenv("XI_GROQ_API_KEY", raising=False)
    assert isinstance(build_narrator(), NullNarrator)


class _StubCompletion:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


def test_groq_narrator_returns_completion_text(result):
    narrator = object.__new__(GroqNarrator)
    narrator._model = "stub"

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs["model"] == "stub"
                    return _StubCompletion("Moderate risk, full hedge recommended.")

    narrator._client = _Client()
    assert narrator.narrate(result).startswith("Moderate risk")


def test_groq_narrator_swallows_errors(result):
    narrator = object.__new__(GroqNarrator)
    narrator._model = "stub"

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("api down")

    narrator._client = _Client()
    assert narrator.narrate(result) is None
