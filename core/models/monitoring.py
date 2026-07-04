from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .enums import AlertSeverity, RiskLevel
from .models import SimulationResult

_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class MonitoringThresholds:
    max_probability_below: float = settings.MONITORING_MAX_PROBABILITY_BELOW
    max_score: int = settings.MONITORING_MAX_SCORE
    spot_move_band: float = settings.MONITORING_SPOT_MOVE_BAND
    delivery_proximity_days: int = settings.MONITORING_DELIVERY_PROXIMITY_DAYS
    score_jump: int = settings.MONITORING_SCORE_JUMP


@dataclass(frozen=True, slots=True)
class Alert:
    code: str
    severity: AlertSeverity
    message: str


def evaluate_result_alerts(
    result: SimulationResult, thresholds: MonitoringThresholds | None = None
) -> tuple[Alert, ...]:
    thresholds = thresholds or MonitoringThresholds()
    alerts: list[Alert] = []

    if result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        severity = (
            AlertSeverity.CRITICAL
            if result.risk_level is RiskLevel.CRITICAL
            else AlertSeverity.WARNING
        )
        alerts.append(Alert("risk_level", severity, f"Risk level {result.risk_level.value}."))

    if result.vulnerability_score >= thresholds.max_score:
        alerts.append(
            Alert(
                "score_threshold",
                AlertSeverity.WARNING,
                f"Vulnerability score {result.vulnerability_score} ≥ {thresholds.max_score}.",
            )
        )

    if result.probability_margin_below_threshold >= thresholds.max_probability_below:
        alerts.append(
            Alert(
                "probability_threshold",
                AlertSeverity.WARNING,
                f"Probability of insufficient margin "
                f"{result.probability_margin_below_threshold * 100:.0f}% ≥ "
                f"{thresholds.max_probability_below * 100:.0f}%.",
            )
        )

    if result.horizon_days <= thresholds.delivery_proximity_days and result.risk_level in (
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ):
        alerts.append(
            Alert(
                "delivery_proximity",
                AlertSeverity.CRITICAL,
                f"Delivery in {result.horizon_days} days with high risk: urgent decision required.",
            )
        )

    return tuple(alerts)


def change_alerts(
    previous_risk_level: RiskLevel,
    previous_score: int,
    previous_spot: float,
    current_risk_level: RiskLevel,
    current_score: int,
    current_spot: float,
    thresholds: MonitoringThresholds | None = None,
) -> tuple[Alert, ...]:
    thresholds = thresholds or MonitoringThresholds()
    alerts: list[Alert] = []

    if _RISK_ORDER[current_risk_level] > _RISK_ORDER[previous_risk_level]:
        alerts.append(
            Alert(
                "risk_escalation",
                AlertSeverity.WARNING,
                f"Risk increasing: {previous_risk_level.value} → {current_risk_level.value}.",
            )
        )

    if current_score - previous_score >= thresholds.score_jump:
        alerts.append(
            Alert(
                "score_jump",
                AlertSeverity.WARNING,
                f"Score +{current_score - previous_score} ({previous_score} → {current_score}).",
            )
        )

    if previous_spot > 0:
        move = current_spot / previous_spot - 1.0
        if abs(move) >= thresholds.spot_move_band:
            alerts.append(
                Alert(
                    "spot_move",
                    AlertSeverity.INFO,
                    f"Spot rate {move * 100:+.1f}% since the last assessment.",
                )
            )

    return tuple(alerts)


def evaluate_change_alerts(
    previous: SimulationResult,
    current: SimulationResult,
    thresholds: MonitoringThresholds | None = None,
) -> tuple[Alert, ...]:
    return change_alerts(
        previous.risk_level,
        previous.vulnerability_score,
        previous.spot_rate_order_date,
        current.risk_level,
        current.vulnerability_score,
        current.spot_rate_order_date,
        thresholds,
    )
