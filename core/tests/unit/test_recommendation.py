from __future__ import annotations

import datetime as dt

import pytest

from core.app.recommendation import build_recommendation
from core.models.enums import RiskLevel
from core.models.hedging import HedgeAnalysis
from core.models.models import OrderInput


def _order(domestic_currency="MAD"):
    return OrderInput(
        amount_foreign=100_000.0,
        foreign_currency="USD",
        domestic_currency=domestic_currency,
        order_date=dt.date(2026, 1, 1),
        delivery_date=dt.date(2026, 3, 1),
        target_margin_pct=0.30,
    )


def _hedge(forward=11.05, points=0.05, hedged_pct=0.28, ratio=0.6, prob=0.45):
    return HedgeAnalysis(
        theoretical_forward_rate=forward,
        forward_points=points,
        hedged_margin_domestic=280_000.0,
        hedged_margin_pct=hedged_pct,
        unhedged_expected_margin_pct=0.30,
        unhedged_cvar_margin_pct=0.10,
        probability_unhedged_beats_hedge=prob,
        optimal_hedge_ratio=ratio,
        optimal_hedge_cvar_margin_pct=0.22,
        cvar_improvement_pct=0.12,
    )


@pytest.mark.parametrize(
    "level,expected_fragment",
    [
        (RiskLevel.LOW, "surveillez le taux"),
        (RiskLevel.MODERATE, "Envisagez de bloquer"),
        (RiskLevel.HIGH, "bloquez le taux de change dès maintenant"),
        (RiskLevel.CRITICAL, "bloquez le taux immédiatement"),
    ],
)
def test_recommendation_action_matches_risk_level(level, expected_fragment):
    text = build_recommendation(_order("EUR"), level, 10.5, 11.0, 0.4, _hedge())
    assert expected_fragment in text


def test_mad_notice_only_appears_for_mad_domestic_currency():
    mad_text = build_recommendation(_order("MAD"), RiskLevel.HIGH, 10.5, 11.0, 0.4, _hedge())
    eur_text = build_recommendation(_order("EUR"), RiskLevel.HIGH, 10.5, 11.0, 0.4, _hedge())
    assert "Office des Changes" in mad_text
    assert "Office des Changes" not in eur_text


def test_recommendation_includes_key_figures():
    text = build_recommendation(_order("MAD"), RiskLevel.MODERATE, 10.1234, 11.4321, 0.37, _hedge())
    assert "10.1234" in text
    assert "11.4321" in text
    assert "37%" in text


def test_recommendation_includes_hedge_advice():
    text = build_recommendation(
        _order("EUR"), RiskLevel.HIGH, 10.5, 11.0, 0.4, _hedge(forward=11.0500, ratio=0.6, prob=0.45)
    )
    assert "11.0500" in text
    assert "60%" in text
    assert "45%" in text


def test_forward_premium_and_discount_wording():
    premium = build_recommendation(_order("EUR"), RiskLevel.LOW, 10.5, 11.0, 0.4, _hedge(points=0.05))
    discount = build_recommendation(_order("EUR"), RiskLevel.LOW, 10.5, 11.0, 0.4, _hedge(points=-0.05))
    assert "prime" in premium
    assert "décote" in discount
