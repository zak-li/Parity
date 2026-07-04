from __future__ import annotations

import logging
from dataclasses import dataclass

from core.app.risk_engine import MarginRiskEngine
from core.models.models import OrderInput
from core.models.monitoring import (
    MonitoringThresholds,
    change_alerts,
    evaluate_result_alerts,
)
from db import SimulationRepository, record_from_result

from .sinks import AlertSink

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MonitoringOutcome:
    order: OrderInput
    dispatched: bool
    alert_count: int


class MonitoringScheduler:
    def __init__(
        self,
        engine: MarginRiskEngine,
        repository: SimulationRepository,
        sinks: list[AlertSink],
        thresholds: MonitoringThresholds | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._sinks = sinks
        self._thresholds = thresholds or MonitoringThresholds()

    def run_once(self, orders: list[OrderInput]) -> list[MonitoringOutcome]:
        outcomes: list[MonitoringOutcome] = []
        for order in orders:
            outcomes.append(self._process(order))
        return outcomes

    def _process(self, order: OrderInput) -> MonitoringOutcome:
        previous = self._repository.latest_for_pair(order.foreign_currency, order.domestic_currency)
        result = self._engine.run(order)

        alerts = list(evaluate_result_alerts(result, self._thresholds))
        if previous is not None:
            alerts.extend(
                change_alerts(
                    previous.risk_level,
                    previous.vulnerability_score,
                    previous.spot_rate,
                    result.risk_level,
                    result.vulnerability_score,
                    result.spot_rate_order_date,
                    self._thresholds,
                )
            )

        self._repository.save(record_from_result(result))

        dispatched = False
        if alerts:
            subject = (
                f"[{result.risk_level.value}] {order.foreign_currency}/{order.domestic_currency} "
                f"score {result.vulnerability_score}"
            )
            for sink in self._sinks:
                try:
                    sink.dispatch(subject, alerts)
                    dispatched = True
                except Exception as exc:
                    logger.warning("sink_dispatch_failed", extra={"error": str(exc)})

        return MonitoringOutcome(order=order, dispatched=dispatched, alert_count=len(alerts))
