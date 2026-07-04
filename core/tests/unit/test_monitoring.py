from __future__ import annotations

import dataclasses

import pytest

from core.app.risk_engine import MarginRiskEngine
from core.models.enums import AlertSeverity, RiskLevel
from core.models.monitoring import (
    MonitoringThresholds,
    evaluate_change_alerts,
    evaluate_result_alerts,
)


@pytest.fixture
def base_result(static_provider, sample_order):
    return MarginRiskEngine(static_provider).run(sample_order)


def _codes(alerts):
    return {a.code for a in alerts}


def test_high_risk_triggers_risk_level_alert(base_result):
    result = dataclasses.replace(base_result, risk_level=RiskLevel.CRITICAL)
    alerts = evaluate_result_alerts(result)
    risk_alert = next(a for a in alerts if a.code == "risk_level")
    assert risk_alert.severity is AlertSeverity.CRITICAL


def test_low_risk_snapshot_has_no_alerts(base_result):
    result = dataclasses.replace(
        base_result,
        risk_level=RiskLevel.LOW,
        vulnerability_score=5,
        probability_margin_below_threshold=0.0,
    )
    assert evaluate_result_alerts(result) == ()


def test_score_and_probability_thresholds_trigger(base_result):
    result = dataclasses.replace(
        base_result,
        risk_level=RiskLevel.MODERATE,
        vulnerability_score=90,
        probability_margin_below_threshold=0.5,
    )
    codes = _codes(evaluate_result_alerts(result))
    assert "score_threshold" in codes
    assert "probability_threshold" in codes


def test_imminent_delivery_with_high_risk_is_critical(base_result):
    result = dataclasses.replace(base_result, risk_level=RiskLevel.HIGH, horizon_days=7)
    alerts = {a.code: a for a in evaluate_result_alerts(result)}
    assert alerts["delivery_proximity"].severity is AlertSeverity.CRITICAL


def test_risk_escalation_change_alert(base_result):
    previous = dataclasses.replace(base_result, risk_level=RiskLevel.LOW, vulnerability_score=10)
    current = dataclasses.replace(base_result, risk_level=RiskLevel.HIGH, vulnerability_score=70)
    codes = _codes(evaluate_change_alerts(previous, current))
    assert "risk_escalation" in codes
    assert "score_jump" in codes


def test_spot_move_change_alert(base_result):
    previous = dataclasses.replace(base_result, spot_rate_order_date=10.0)
    current = dataclasses.replace(base_result, spot_rate_order_date=10.5)
    move_alert = next(a for a in evaluate_change_alerts(previous, current) if a.code == "spot_move")
    assert "+5.0%" in move_alert.message


def test_no_change_alerts_when_stable(base_result):
    assert evaluate_change_alerts(base_result, base_result) == ()


def test_custom_thresholds_are_respected(base_result):
    result = dataclasses.replace(
        base_result,
        risk_level=RiskLevel.LOW,
        vulnerability_score=40,
        probability_margin_below_threshold=0.05,
    )
    strict = MonitoringThresholds(max_score=30)
    assert "score_threshold" in _codes(evaluate_result_alerts(result, strict))
